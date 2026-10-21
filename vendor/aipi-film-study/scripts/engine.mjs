#!/usr/bin/env node
// AIπ｜AI圆周派 — independent film-study engine. Node standard library only.
import { createHash } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';
import { closeSync, existsSync, mkdirSync, openSync, readFileSync, readSync, realpathSync, renameSync, statSync, writeFileSync } from 'node:fs';
import { basename, dirname, extname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const EPS = 1e-6;
const SCHEMA = 'aipi.film-study/v1';
const finite = n => typeof n === 'number' && Number.isFinite(n);
const filled = s => typeof s === 'string' && s.trim().length > 0;
const json = file => JSON.parse(readFileSync(file, 'utf8'));
const unixPath = path => path.replaceAll('\\', '/');
const absolute = (base, path) => isAbsolute(path) ? path : resolve(base, path);
const digest = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const safeId = id => typeof id === 'string' && /^[A-Za-z][A-Za-z0-9_-]*$/.test(id);

export function fileHash(file) {
  const fd = openSync(file, 'r'), hash = createHash('sha256'), chunk = Buffer.allocUnsafe(1024 * 1024);
  try { for (;;) { const n = readSync(fd, chunk, 0, chunk.length, null); if (!n) break; hash.update(chunk.subarray(0, n)); } }
  finally { closeSync(fd); }
  return hash.digest('hex');
}

function saveJson(file, value) {
  mkdirSync(dirname(resolve(file)), { recursive: true });
  const temp = `${file}.writing-${process.pid}`;
  writeFileSync(temp, `${JSON.stringify(value, null, 2)}\n`);
  renameSync(temp, file);
}

function run(binary, args) {
  try { return execFileSync(binary, args, { encoding: 'utf8', maxBuffer: 256 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] }); }
  catch (error) { throw new Error(`${binary} failed: ${String(error.stderr || error.message).slice(-6000)}`); }
}

function ratio(value) {
  const [a, b = '1'] = String(value || '0/1').split('/');
  const n = Number(a), d = Number(b);
  return Number.isFinite(n) && d > 0 ? n / d : 0;
}

function mediaHeader(video) {
  const data = JSON.parse(run('ffprobe', ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', video]));
  const stream = data.streams?.find(s => s.codec_type === 'video');
  if (!stream) throw new Error('源文件没有可解码视频流。');
  return { data, stream, audio: data.streams.filter(s => s.codec_type === 'audio') };
}

/** Uses decoded frame timestamps, not packet count or a guessed nominal frame grid. */
export function probeMedia(video) {
  video = resolve(video);
  const { data, stream, audio } = mediaHeader(video);
  const tick = ratio(stream.time_base);
  if (!(tick > 0)) throw new Error('源流缺少有效时间基。');
  const decoded = JSON.parse(run('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_frames', '-show_entries',
    'frame=best_effort_timestamp,best_effort_timestamp_time,pts,pts_time,duration,pkt_duration,pkt_duration_time', '-of', 'json', video])).frames || [];
  const pts = decoded.map(f => {
    const raw = f.best_effort_timestamp ?? f.pts;
    if (raw != null && Number.isSafeInteger(Number(raw))) return Number(raw) * tick;
    const seconds = Number(f.best_effort_timestamp_time ?? f.pts_time);
    if (!Number.isFinite(seconds)) throw new Error('存在缺失或超出精度范围的视频帧时间戳，不能建立精确分镜。');
    return seconds;
  });
  if (!pts.length) throw new Error('源文件未解码出视频帧。');
  for (let i = 1; i < pts.length; i++) if (!(pts[i] > pts[i - 1])) throw new Error('存在重复或倒退的视频帧 PTS；此时间轴暂不支持。');
  const origin = pts[0], last = decoded.at(-1);
  if (audio.some(a => Number.isFinite(Number(a.start_time)) && Number(a.start_time) < origin - EPS)) {
    throw new Error('音频早于视频首帧开始；此素材需先保留片头声音并规范公共时间轴，不能直接把视频 PTS 归零而丢失前段音频。');
  }
  const durationTicks = Number(last.duration ?? last.pkt_duration);
  let lastDuration = durationTicks > 0 ? durationTicks * tick : Number(last.pkt_duration_time);
  if (!(lastDuration > 0)) {
    const streamEnd = Number(stream.start_time || 0) + Number(stream.duration);
    if (Number.isFinite(streamEnd) && streamEnd > pts.at(-1)) lastDuration = streamEnd - pts.at(-1);
  }
  if (!(lastDuration > 0)) throw new Error('无法确定末帧结束时间；不以猜测帧率补齐。');
  const times = pts.map(t => t - origin), videoDuration = times.at(-1) + lastDuration;
  let fps = ratio(stream.avg_frame_rate) || ratio(stream.r_frame_rate);
  let timing = 'vfr';
  if (pts.length > 1) {
    const step = (pts.at(-1) - origin) / (pts.length - 1);
    const tolerance = Math.max(tick * 1.05, 1e-9);
    const uniform = pts.every((p, i) => Math.abs(p - origin - i * step) <= tolerance) && Math.abs(lastDuration - step) <= tolerance;
    if (uniform) { timing = 'cfr'; fps = 1 / step; }
  } else if (fps > 0 && Math.abs(lastDuration - 1 / fps) <= Math.max(tick, 1e-9)) timing = 'cfr';
  let duration = videoDuration;
  for (const a of audio) {
    const end = Number(a.start_time || 0) + Number(a.duration) - origin;
    if (Number.isFinite(end)) duration = Math.max(duration, end);
  }
  return { file: basename(video), duration, videoDuration, width: Number(stream.width), height: Number(stream.height), fps,
    frameCount: pts.length, hasAudio: audio.length > 0, audioStreams: audio.length, timing, timeOrigin: origin,
    timeBase: stream.time_base, frameTimes: [...times, videoDuration], sha256: fileHash(video), sizeBytes: statSync(video).size,
    codec: stream.codec_name, format: data.format?.format_name };
}

export function overlappingDialogue(study, shot) {
  const isLast = study.shots?.at(-1)?.id === shot.id;
  const displayEnd = isLast ? Math.max(shot.end, study.source?.duration || shot.end) : shot.end;
  return (study.dialogue || []).filter(c => Math.min(c.end, displayEnd) - Math.max(c.start, shot.start) > EPS)
    .sort((a, b) => a.start - b.start || a.end - b.end || String(a.id).localeCompare(String(b.id)));
}

export function mappedStudy(study) {
  const copy = structuredClone(study);
  for (const shot of copy.shots || []) shot.dialogueIds = overlappingDialogue(copy, shot).map(c => c.id);
  return copy;
}

function emptyShot(id, start, end, startFrame, endFrame) {
  return { id, start, end, startFrame, endFrame, size: '', camera: '', transition: '待核', description: '', subjects: [],
    dialogueIds: [], sound: { status: 'pending', note: '尚未核对本镜声音及画面字幕。' },
    director: { intention: '', emotion: '', blocking: '', edit: '', reshoot: '' }, evidence: [], frames: {} };
}

function closestIndex(values, target) {
  let lo = 0, hi = values.length;
  while (lo < hi) { const mid = (lo + hi) >>> 1; if (values[mid] < target) lo = mid + 1; else hi = mid; }
  if (lo === 0) return 0;
  if (lo === values.length) return lo - 1;
  return Math.abs(values[lo] - target) < Math.abs(values[lo - 1] - target) ? lo : lo - 1;
}

export function detectStudy(video, { threshold = 0.25, title } = {}) {
  if (!finite(threshold) || threshold <= 0 || threshold >= 1) throw new Error('threshold 必须在 0 与 1 之间。');
  const source = probeMedia(video);
  // showinfo is emitted on stderr; collect it without creating an output video.
  const analysis = spawnCapture('ffmpeg', ['-hide_banner', '-loglevel', 'info', '-copyts', '-i', resolve(video), '-an',
    '-vf', `select=gt(scene\\,${threshold}),showinfo`, '-fps_mode', 'vfr', '-f', 'null', '-']);
  const filterTimeBase = /config in time_base:\s*(\d+\/\d+)/.exec(analysis.stderr)?.[1] || source.timeBase;
  const unit = ratio(filterTimeBase), boundaries = new Set([0, source.frameCount]);
  for (const line of analysis.stderr.split('\n')) {
    const match = /showinfo[^\n]*\bn:\s*\d+\s+pts:\s*(-?\d+)/.exec(line);
    if (!match) continue;
    const time = Number(match[1]) * unit - source.timeOrigin;
    const index = closestIndex(source.frameTimes, time);
    if (Math.abs(source.frameTimes[index] - time) > Math.max(unit, EPS)) throw new Error('检测切点无法对应源帧，停止生成近似时间表。');
    if (index > 0 && index < source.frameCount) boundaries.add(index);
  }
  const indexes = [...boundaries].sort((a, b) => a - b), digits = Math.max(2, String(indexes.length - 1).length);
  return { schema: SCHEMA, title: title || basename(video, extname(video)), source,
    shots: indexes.slice(0, -1).map((f, i) => emptyShot(`S${String(i + 1).padStart(digits, '0')}`, source.frameTimes[f], source.frameTimes[indexes[i + 1]], f, indexes[i + 1])),
    dialogue: [], review: { audio: { state: 'not-reviewed', coverage: [], openIssues: ['全片语言尚未转写与核对；无音轨也须检查可见字幕。'] },
      visual: { state: 'pending', notes: '场景变化检测候选；需逐镜看片确认漏切、渐变与误切。' } },
    detection: { threshold, method: 'FFmpeg scene score', reviewed: false } };
}

// Unlike shell execution, arguments never undergo shell interpolation.
function spawnCapture(binary, args) {
  const result = spawnSync(binary, args, { encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 });
  if (result.error || result.status !== 0) throw new Error(`${binary} failed: ${String(result.stderr || result.error?.message).slice(-6000)}`);
  return result;
}

function frameBinding(study) {
  return digest({ source: study.source.sha256, frames: study.shots.map(s => [s.id, s.start, s.end, s.startFrame, s.endFrame]) });
}

function intervalIssues(items, duration, label) {
  const errors = [];
  for (const [i, item] of items.entries()) if (!finite(item.start) || !finite(item.end) || item.start < -EPS || item.end > duration + EPS || item.end - item.start <= EPS) errors.push(`${label}[${i}] 时间无效。`);
  return errors;
}

/** Structural checks are deliberately separate from actual human/ASR evidence. */
export function validateStudy(study, { production = false, baseDir = process.cwd(), video, checkAssets = false } = {}) {
  const errors = [], warnings = [], source = study?.source || {}, shots = study?.shots, cues = study?.dialogue;
  const fail = message => errors.push(message);
  if (study?.schema !== SCHEMA) fail(`schema 必须为 ${SCHEMA}。`);
  if (!finite(source.duration) || source.duration <= 0) fail('缺少有效源片时长。');
  if (!Number.isInteger(source.width) || source.width <= 0 || !Number.isInteger(source.height) || source.height <= 0) fail('缺少有效源片尺寸。');
  if (typeof source.hasAudio !== 'boolean') fail('hasAudio 必须明确。');
  if (!Number.isInteger(source.frameCount) || source.frameCount <= 0) fail('缺少有效帧数。');
  if (!Array.isArray(shots) || !shots.length) fail('必须至少有一镜。');
  if (!Array.isArray(cues)) fail('dialogue 必须是逐句数组，未转写时留空并保持待核。');
  if (errors.length) return { ok: false, errors, warnings, stats: { shots: shots?.length || 0, dialogue: cues?.length || 0 } };
  const times = source.frameTimes;
  if (times != null && (!Array.isArray(times) || times.length !== source.frameCount + 1 || times.some((t, i) => !finite(t) || (i && t <= times[i - 1])) || Math.abs(times[0]) > EPS)) fail('frameTimes 必须从零递增并包含 N+1 个真实边界。');
  const timeline = Array.isArray(times) && times.length === source.frameCount + 1 ? times : null;
  const shotIds = new Set(), cueIds = new Set();
  errors.push(...intervalIssues(shots, source.duration, 'shots'), ...intervalIssues(cues, source.duration, 'dialogue'));
  for (const [i, s] of shots.entries()) {
    if (!safeId(s.id) || shotIds.has(s.id)) fail(`镜号无效或重复：${s.id}`); shotIds.add(s.id);
    if (!Number.isInteger(s.startFrame) || !Number.isInteger(s.endFrame) || s.startFrame < 0 || s.endFrame > source.frameCount || s.endFrame <= s.startFrame) fail(`${s.id} 帧区间无效。`);
    if (i === 0 && (Math.abs(s.start) > EPS || s.startFrame !== 0)) fail('镜头时间轴必须从源首帧开始。');
    if (i && (Math.abs(s.start - shots[i - 1].end) > EPS || s.startFrame !== shots[i - 1].endFrame)) fail(`${s.id} 与前镜有空档或重叠。`);
    if (timeline && (Math.abs(s.start - timeline[s.startFrame]) > EPS || Math.abs(s.end - timeline[s.endFrame]) > EPS)) fail(`${s.id} 时间与真实帧索引不符。`);
    if (!timeline && source.timing === 'cfr' && source.fps > 0 && (Math.abs(s.start - s.startFrame / source.fps) > EPS || Math.abs(s.end - s.endFrame / source.fps) > EPS)) fail(`${s.id} 时间与所声明的 CFR 帧索引不符。`);
    const expected = overlappingDialogue(study, s).map(c => c.id);
    if (JSON.stringify(s.dialogueIds) !== JSON.stringify(expected)) fail(`${s.id} 对白关联不完整或顺序错误；应为 ${expected.join(', ')}。`);
    if (!['pending', 'reviewed', 'non-speech', 'none'].includes(s.sound?.status)) fail(`${s.id} 缺少明确的声音审核状态。`);
    if (production) {
      if (s.sound?.status === 'pending') fail(`${s.id} 声音仍待核。`);
      if (['non-speech', 'none'].includes(s.sound?.status) && expected.length) fail(`${s.id} 含语言事件，不能标成无语言。`);
      if (source.hasAudio && !expected.length && s.sound?.status === 'reviewed') fail(`${s.id} 没有语言事件；确认无语言时须明确 non-speech，并提供对应审核区间。`);
      if (source.hasAudio && ['non-speech', 'none'].includes(s.sound?.status)) {
        let covered = s.start;
        const proof = (study.review?.audio?.coverage || []).filter(c => c.result === 'non-speech' && c.audioChecked === true).sort((a, b) => a.start - b.start);
        for (const c of proof) { if (c.start > covered + EPS) break; if (c.end > covered) covered = c.end; }
        if (covered < s.end - EPS || !filled(s.sound?.note)) fail(`${s.id} 无语言判断缺少覆盖整镜的 result:non-speech 听审记录或说明。`);
      }
      if (!filled(s.description) || !filled(s.size) || !filled(s.camera)) fail(`${s.id} 逐镜画面、景别或运镜尚未完成。`);
    }
  }
  const visualEnd = source.videoDuration ?? timeline?.at(-1) ?? source.duration;
  if (shots.at(-1).endFrame !== source.frameCount || Math.abs(shots.at(-1).end - visualEnd) > Math.max(EPS, timeline ? EPS : .000501)) fail('末镜未覆盖视频末帧或结束时间错误。');
  if (source.duration - visualEnd > EPS) warnings.push(`末帧后另有 ${(source.duration - visualEnd).toFixed(6)} 秒音轨尾部，播放端须继续保留声音。`);
  for (const c of cues) {
    if (!safeId(c.id) || cueIds.has(c.id)) fail(`对白 ID 无效或重复：${c.id}`); cueIds.add(c.id);
    if (!filled(c.text) || !filled(c.speaker)) fail(`${c.id} 缺少原文或说话人；未知人物请明确写待核。`);
    if (!['dialogue', 'voiceover', 'singing', 'subtitle-meaning'].includes(c.type)) fail(`${c.id} 语言类型无效。`);
    if (!['audio', 'subtitle', 'subtitle+audio'].includes(c.source)) fail(`${c.id} 证据来源无效。`);
    if (!['verified', 'uncertain'].includes(c.status)) fail(`${c.id} 确定性状态无效。`);
    if (!source.hasAudio && ['audio', 'subtitle+audio'].includes(c.source)) fail(`${c.id} 声称音频来源，但源片被标记为无音轨。`);
    if (c.type === 'subtitle-meaning' && c.source !== 'subtitle') fail(`${c.id} 唱词大意必须标明为字幕释义来源。`);
    if (c.status === 'uncertain') (production ? errors : warnings).push(`${c.id} 内容待核${filled(c.notes) ? `：${c.notes}` : '，须说明具体疑点。'}`);
    if (!shots.some(s => overlappingDialogue({ dialogue: [c] }, s).length) && c.start < visualEnd - EPS) fail(`${c.id} 未映射到任何镜头。`);
  }
  const languageReviewNeeded = source.hasAudio || cues.length > 0;
  const review = study.review?.audio || {};
  if (production && languageReviewNeeded) {
    if (review.state !== 'complete') fail('全片语言审核尚未完成。');
    if (!Array.isArray(review.openIssues) || review.openIssues.length) fail('声音审核仍有未解决项，或未明确登记为空。');
    const coverage = Array.isArray(review.coverage) ? review.coverage : [];
    if (!coverage.length) fail('缺少全片声音/字幕审核覆盖记录。');
    errors.push(...intervalIssues(coverage, source.duration, 'review.audio.coverage'));
    let covered = 0;
    for (const [i, c] of [...coverage].sort((a, b) => a.start - b.start).entries()) {
      if (c.start > covered + EPS) fail(`语言审核在 ${covered}–${c.start} 秒缺少覆盖。`);
      covered = Math.max(covered, c.end);
      if (!filled(c.method) || !filled(c.notes)) fail(`审核覆盖 ${i + 1} 缺少实际方法或证据说明。`);
      if (source.hasAudio && c.audioChecked !== true) fail(`审核覆盖 ${i + 1} 未明确记录 audioChecked:true；原字幕已核对不等于声音已听核。`);
      if (!source.hasAudio && cues.length && c.subtitlesChecked !== true) fail(`审核覆盖 ${i + 1} 未明确记录 subtitlesChecked:true。`);
    }
    if (covered < source.duration - EPS) fail(`语言审核未覆盖片尾 ${covered}–${source.duration} 秒。`);
  }
  if (production && study.review?.visual?.state !== 'reviewed') fail('全片切点及画面尚未完成看片复核。');
  let actualVideo = video ? resolve(video) : filled(source.file) ? absolute(baseDir, source.file) : null;
  if (actualVideo && existsSync(actualVideo)) {
    if (production || video) {
      try {
        const h = mediaHeader(actualVideo);
        if ((h.audio.length > 0) !== source.hasAudio) fail('源片真实音轨与 hasAudio 不符。');
        if (Number(h.stream.width) !== source.width || Number(h.stream.height) !== source.height) fail('源片真实尺寸与记录不符。');
        const origin = Number(h.stream.start_time || 0), tolerance = Math.max(2e-6, ratio(h.stream.time_base) * 1.05);
        if (source.timeOrigin != null && Math.abs(origin - source.timeOrigin) > tolerance) fail('源片真实时间起点与 timeOrigin 不符。');
        const ends = [h.stream, ...h.audio].map(s => Number(s.start_time || 0) + Number(s.duration) - origin);
        if (ends.every(Number.isFinite)) {
          const measuredDuration = Math.max(...ends);
          if (Math.abs(measuredDuration - source.duration) > tolerance) fail('源片真实音视频总时长与 source.duration 不符。');
          if (source.videoDuration != null && Math.abs(Number(h.stream.duration) - source.videoDuration) > tolerance) fail('源片真实视频时长与 videoDuration 不符。');
        } else if (production) fail('容器没有足够的流时长信息，暂不能确认完整声音时长；请先规范素材并重新测量。');
        if (Number.isInteger(Number(h.stream.nb_frames)) && Number(h.stream.nb_frames) > 0 && Number(h.stream.nb_frames) !== source.frameCount) fail('源片声明帧数与 source.frameCount 不符。');
        if (source.sha256 && fileHash(actualVideo) !== source.sha256) fail('源片 SHA-256 已改变，拒绝使用旧分析和帧图。');
        else if (!source.sha256 && production) fail('缺少源片 sha256，无法确认当前素材身份。');
      } catch (error) { fail(`源片核验失败：${error.message}`); }
    }
  } else if (production || video) fail('找不到可核验的源片；请保持 source.file 路径关系或传 --video。');
  if (checkAssets || production) {
    for (const s of shots) for (const role of ['in', 'out']) if (!filled(s.frames?.[role]) || !existsSync(absolute(baseDir, s.frames[role]))) fail(`${s.id} ${role} 帧图缺失。`);
    const manifestPath = study.assets?.framesManifest;
    if (!filled(manifestPath)) (production ? errors : warnings).push('缺少帧图清单，尚不能验证帧图身份。');
    else {
      try {
        const path = absolute(baseDir, manifestPath), m = json(path);
        if (m.schema !== 'aipi.frames/v1' || m.binding !== frameBinding(study) || m.sourceSha256 !== source.sha256) fail('帧图清单与当前素材或镜头边界不一致。');
        for (const s of shots) for (const role of ['in', 'out']) {
          const item = m.items?.find(e => e.shotId === s.id && e.role === role);
          const expectedPath = filled(s.frames?.[role]) ? absolute(baseDir, s.frames[role]) : null;
          if (!item || !expectedPath || resolve(dirname(path), item.file) !== resolve(expectedPath) || !existsSync(expectedPath) || fileHash(expectedPath) !== item.sha256) fail(`${s.id} ${role} 帧图内容或路径与清单不一致。`);
        }
      } catch (error) { fail(`帧图清单核验失败：${error.message}`); }
    }
  }
  return { ok: errors.length === 0, errors: [...new Set(errors)], warnings: [...new Set(warnings)], stats: { shots: shots.length, dialogue: cues.length,
    crossShotDialogue: cues.filter(c => shots.filter(s => overlappingDialogue({ dialogue: [c] }, s).length).length > 1).length,
    pendingShots: shots.filter(s => s.sound?.status === 'pending').length, production } };
}

function textForCue(c) {
  const labels = [c.status === 'uncertain' ? '待核' : '', c.type === 'subtitle-meaning' ? '原字幕大意' : c.source === 'subtitle' ? '原字幕' : ''].filter(Boolean);
  return `${c.speaker}：${labels.length ? `【${labels.join('·')}】` : ''}${c.text}`;
}

const srtStamp = seconds => {
  const ms = Math.max(0, Math.round(seconds * 1000));
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`;
};

export function srtText(study) {
  const seen = new Set();
  return [...(study.dialogue || [])].sort((a, b) => a.start - b.start || a.end - b.end).map((c, i) => {
    if (seen.has(c.id)) throw new Error(`重复对白 ID：${c.id}`); seen.add(c.id);
    if (!filled(c.text) || !finite(c.start) || !finite(c.end) || c.start < 0 || c.end <= c.start) throw new Error(`${c.id} 不可导出为字幕。`);
    const end = Math.max(Math.round(c.start * 1000) + 1, Math.round(c.end * 1000)) / 1000;
    return `${i + 1}\n${srtStamp(c.start)} --> ${srtStamp(end)}\n${textForCue(c)}\n`;
  }).join('\n');
}

export const CSV_HEADERS = ['镜号', '开始秒', '结束秒', '时长秒', '首帧序号', '结束帧序号（不含）', '景别', '运镜', '转场', '原片观察', '出场人物', '完整语言', '语言条目ID', '声音审核', '原声音说明', '导演意图', '情绪变化', '空间调度', '剪辑理由', '复拍建议', '原片证据', '入帧', '出帧'];
const csvCell = value => `"${String(value ?? '').replaceAll('"', '""')}"`;
export function csvText(study) {
  const rows = [CSV_HEADERS];
  for (const s of study.shots || []) {
    const cues = overlappingDialogue(study, s), d = s.director || {};
    rows.push([s.id, s.start, s.end, s.end - s.start, s.startFrame, s.endFrame, s.size, s.camera, s.transition, s.description,
      (s.subjects || []).join('、'), cues.map(c => `${c.start < s.start - EPS || c.end > s.end + EPS ? '↳（跨镜全文）' : ''}${textForCue(c)}`).join('\n'),
      cues.map(c => c.id).join('、'), s.sound?.status, s.sound?.note, d.intention, d.emotion, d.blocking, d.edit, d.reshoot,
      (s.evidence || []).join('\n'), s.frames?.in, s.frames?.out]);
  }
  return '\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}

export function extractFrames(study, video, outDir, { baseDir = process.cwd(), studyOut = join(dirname(resolve(outDir)), 'study.frames.json') } = {}) {
  const source = probeMedia(video), working = structuredClone(study);
  if (study.source.sha256 && study.source.sha256 !== source.sha256) throw new Error('源片 SHA-256 不同；拒绝为旧镜头表抽帧。');
  if (source.frameCount !== study.source.frameCount || source.hasAudio !== study.source.hasAudio || source.width !== study.source.width || source.height !== study.source.height) throw new Error('实际源片与镜头表元数据不符。');
  working.source = { ...source, file: unixPath(relative(dirname(resolve(studyOut)), resolve(video))) };
  const structural = validateStudy(working);
  if (!structural.ok) throw new Error(structural.errors.join('\n'));
  outDir = resolve(outDir); mkdirSync(outDir, { recursive: true });
  const items = [], studyBase = dirname(resolve(studyOut));
  for (const shot of working.shots) {
    shot.frames = {};
    for (const [role, proportion] of [['in', .15], ['out', .85]]) {
      const index = Math.min(shot.endFrame - 1, shot.startFrame + Math.floor((shot.endFrame - shot.startFrame) * proportion));
      const time = source.frameTimes[index], originalTime = source.timeOrigin + time;
      const file = `${shot.id}-${role}.jpg`, path = join(outDir, file), temp = join(outDir, `${shot.id}-${role}.writing-${process.pid}.jpg`);
      run('ffmpeg', ['-v', 'error', '-y', '-seek_timestamp', '1', '-ss', Math.max(source.timeOrigin, originalTime - .000001).toFixed(9), '-i', resolve(video),
        '-map', '0:v:0', '-frames:v', '1', '-vf', 'scale=640:-2', '-q:v', '2', temp]);
      if (!existsSync(temp) || statSync(temp).size === 0) throw new Error(`${shot.id} ${role} 未抽出实际帧。`);
      renameSync(temp, path);
      items.push({ shotId: shot.id, role, index, time, originalTime, file, sha256: fileHash(path) });
      shot.frames[role] = unixPath(relative(studyBase, path));
    }
  }
  const manifest = join(outDir, 'frame-manifest.json');
  saveJson(manifest, { schema: 'aipi.frames/v1', sourceSha256: source.sha256, binding: frameBinding(working), items });
  working.assets = { ...(working.assets || {}), framesManifest: unixPath(relative(studyBase, manifest)) };
  saveJson(studyOut, working);
  return { study: working, studyOut: resolve(studyOut), manifest, count: items.length };
}

export function recutStudy(study, { splits = [], merges = [] } = {}) {
  if (!splits.length && !merges.length) throw new Error('至少提供一个 --split 或 --merge。');
  const result = structuredClone(study), times = result.source.frameTimes;
  if (!Array.isArray(times) || times.length !== result.source.frameCount + 1 || times.some((t, i) => !finite(t) || (i && t <= times[i - 1]))) throw new Error('重新切镜需要真实 frameTimes；先对源片 probe 或 frames，不能按猜测帧率吸附。');
  const frameAt = t => {
    if (!finite(t)) throw new Error('切点必须是有限秒数。');
    const index = closestIndex(times, t);
    if (Math.abs(times[index] - t) > EPS) throw new Error(`${t} 秒不在真实帧边界；请选择实际 PTS。`);
    return index;
  };
  const boundaries = new Set([0, ...result.shots.map(s => s.endFrame)]);
  for (const t of merges) {
    const f = frameAt(t);
    if (f === 0 || f === result.source.frameCount || !boundaries.has(f)) throw new Error(`${t} 秒不是可合并的内部镜头边界。`);
    boundaries.delete(f);
  }
  for (const t of splits) {
    const f = frameAt(t);
    if (f === 0 || f === result.source.frameCount || boundaries.has(f)) throw new Error(`${t} 秒已经是边界，无法再次补切。`);
    boundaries.add(f);
  }
  const points = [...boundaries].sort((a, b) => a - b), digits = Math.max(2, String(points.length - 1).length);
  result.shots = points.slice(0, -1).map((a, i) => {
    const b = points[i + 1], previous = study.shots.filter(s => Math.min(s.endFrame, b) > Math.max(s.startFrame, a));
    const same = previous.length === 1 && previous[0].startFrame === a && previous[0].endFrame === b;
    const id = `S${String(i + 1).padStart(digits, '0')}`;
    if (same) return { ...previous[0], id, derivedFrom: [previous[0].id] };
    return { ...emptyShot(id, times[a], times[b], a, b), derivedFrom: previous.map(s => s.id), evidence: ['切点已改变；重新看片和听审后补充观察与导演分析。'] };
  });
  result.review = { ...(result.review || {}), visual: { state: 'pending', notes: '镜头边界已调整，需重新抽帧及逐镜复核。' } };
  const oldToNew = Object.fromEntries(study.shots.map(old => [old.id, result.shots.filter(s => s.derivedFrom.includes(old.id)).map(s => s.id)]));
  const rewriteReference = text => typeof text !== 'string' ? text : text.replace(/\b[A-Za-z][A-Za-z0-9_-]*\b/g, token => {
    const ids = oldToNew[token];
    if (!ids) return token;
    return ids.length === 1 ? ids[0] : `${token}（旧编号，现 ${ids.join('/')}；引用范围待复核）`;
  });
  for (const s of result.shots) for (const field of Object.keys(s.director || {})) s.director[field] = rewriteReference(s.director[field]);
  result.recut = { oldToNew, splits, merges, referenceReview: 'pending' };
  delete result.assets;
  return mappedStudy(result);
}

function options(args) {
  const out = { positional: [] };
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (!a.startsWith('--')) out.positional.push(a);
    else if (['--production', '--check-assets'].includes(a)) out[a.slice(2)] = true;
    else {
      const value = args[++i];
      if (value == null || value.startsWith('--')) throw new Error(`${a} 需要参数。`);
      const key = a.slice(2);
      if (['split', 'merge'].includes(key)) (out[key] ||= []).push(...value.split(',').map(Number)); else out[key] = value;
    }
  }
  return out;
}

const HELP = `AIπ｜AI圆周派 逐镜分析引擎\nprobe <video>\ndetect <video> --out study.json [--threshold 0.25]\nframes <study.json> --video <video> --out frames [--study-out study.frames.json]\nvalidate <study.json> [--production] [--video video] [--check-assets]\nsubtitles <study.json> --out dialogue.srt\ntable <study.json> --out table.csv\nrecut <study.json> --split <actual-frame-seconds> / --merge <boundary-seconds> --out new.json\n`;
export function main(argv = process.argv.slice(2)) {
  const [command, ...rest] = argv;
  if (!command || ['-h', '--help', 'help'].includes(command)) { process.stdout.write(HELP); return; }
  const o = options(rest), input = o.positional[0];
  if (!input) throw new Error('缺少输入文件。');
  if (command === 'probe') { process.stdout.write(JSON.stringify(probeMedia(input), null, 2) + '\n'); return; }
  if (command === 'detect') {
    if (!o.out) throw new Error('detect 需要 --out。');
    const doc = detectStudy(input, { threshold: o.threshold == null ? .25 : Number(o.threshold), title: o.title });
    doc.source.file = unixPath(relative(dirname(resolve(o.out)), resolve(input)));
    saveJson(o.out, doc); process.stdout.write(JSON.stringify({ out: resolve(o.out), shots: doc.shots.length, state: 'pending' }) + '\n'); return;
  }
  const doc = json(input), baseDir = dirname(resolve(input));
  if (command === 'validate') {
    const result = validateStudy(doc, { production: !!o.production, baseDir, video: o.video, checkAssets: !!o['check-assets'] });
    process.stdout.write(JSON.stringify(result, null, 2) + '\n'); if (!result.ok) process.exitCode = 1; return;
  }
  if (!o.out) throw new Error(`${command} 需要 --out。`);
  if (command === 'frames') {
    const result = extractFrames(doc, o.video || absolute(baseDir, doc.source.file), o.out, { baseDir, studyOut: o['study-out'] || join(dirname(resolve(o.out)), 'study.frames.json') });
    process.stdout.write(JSON.stringify({ studyOut: result.studyOut, manifest: result.manifest, frames: result.count }) + '\n'); return;
  }
  const check = validateStudy(doc);
  if (!check.ok) throw new Error(check.errors.join('\n'));
  if (command === 'recut') {
    const next = recutStudy(doc, { splits: o.split || [], merges: o.merge || [] }), outputBase = dirname(resolve(o.out));
    next.source.file = unixPath(relative(outputBase, absolute(baseDir, doc.source.file)));
    for (const s of next.shots) for (const role of ['in', 'out']) if (filled(s.frames?.[role])) s.frames[role] = unixPath(relative(outputBase, absolute(baseDir, s.frames[role])));
    saveJson(o.out, next);
  }
  else if (['subtitles', 'table'].includes(command)) { mkdirSync(dirname(resolve(o.out)), { recursive: true }); writeFileSync(o.out, command === 'table' ? csvText(doc) : srtText(doc)); }
  else throw new Error(`未知命令：${command}\n${HELP}`);
  process.stdout.write(JSON.stringify({ out: resolve(o.out) }) + '\n');
}

if (process.argv[1] && existsSync(process.argv[1]) && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { main(); } catch (error) { process.stderr.write(`${error.message}\n`); process.exitCode = 1; }
}
