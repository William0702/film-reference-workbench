"""Export an evidence-preserving pool and self-contained local review page."""
import argparse,csv,hashlib,html,json,os
from pathlib import Path
from urllib.parse import quote

def export(study_file,out,sequences=None):
    study_file=Path(study_file).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    d=json.loads(study_file.read_text(encoding='utf-8'));shots=d['shots'];ids=[s['id'] for s in shots]
    if not shots or len(ids)!=len(set(ids)):raise ValueError('Empty or duplicate shot IDs')
    for i,s in enumerate(shots):
        if not 0<=s['start']<s['end']:raise ValueError('Invalid interval')
        if i and abs(shots[i-1]['end']-s['start'])>1e-6:raise ValueError('Timeline gap or overlap')
    groups=json.loads(Path(sequences).read_text(encoding='utf-8')) if sequences else []
    if any(sid not in ids for group in groups for sid in group['shotIds']):raise ValueError('Unknown sequence shot ID')
    def path(value):return os.path.relpath(study_file.parent/value,out).replace('\\','/')
    source=d['source'].copy();source['file']=path(source['file'])
    video=(out/source['file']).resolve()
    if not video.is_file():raise ValueError('Missing original video')
    digest=hashlib.sha256()
    with video.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    if source.get('sha256') and digest.hexdigest()!=source['sha256']:raise ValueError('Source identity changed')
    source['sha256']=digest.hexdigest()
    for s in shots:
        s['frames']={k:path(v) for k,v in s.get('frames',{}).items()}
        for frame in s['frames'].values():
            if not (out/frame).is_file():raise ValueError('Missing reference frame')
    audio=d.get('machineAudioEvidence',{}).copy()
    raw=[]
    if audio.get('file'):
        audio_file=(study_file.parent/audio['file']).resolve()
        raw=json.loads(audio_file.read_text(encoding='utf-8'))['segments']
        audio['file']=os.path.relpath(audio_file,out).replace('\\','/')
    pool={'schema':'film-reference-pool/v1','caseId':source['sha256'][:16],'title':d.get('title','拉片素材'),
          'usageState':'inspiration','review':d.get('review',{}),'acceptance':d.get('acceptance',[]),
          'source':source,'shots':shots,'dialogue':d.get('dialogue',[]),'machineAudioEvidence':audio,'machineTranscript':raw,'sequences':groups,
          'contributors':{'aipi-film-study':'时间轴与媒体证据','storyboard-shot-breakdown':'Agent五维分析','video-shot-analysis-feishu':'本地素材库字段与复刻提示词'}}
    (out/'asset-pool.json').write_text(json.dumps(pool,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'asset-pool.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.writer(stream);writer.writerow(['镜号','记录类型','开始','结束','画面事实','人物','字幕','ASR','五维分析','复拍建议','分镜图提示词','视频提示词','审核状态'])
        for s in shots:
            cues=[c for c in pool['dialogue'] if min(c['end'],s['end'])>max(c['start'],s['start'])]
            speech=[r for r in raw if min(r['end'],s['end'])>max(r['start'],s['start'])]
            writer.writerow([s['id'],s.get('recordType','shot'),s['start'],s['end'],s.get('description',''),' / '.join(s.get('subjects',[])),' / '.join(c['speaker']+'：'+c['text'] for c in cues),' / '.join(r['text'] for r in speech),json.dumps(s.get('fiveDimensions',{}),ensure_ascii=False),s.get('director',{}).get('reshoot',''),s.get('generationPrompts',{}).get('storyboard',''),s.get('generationPrompts',{}).get('video',''),'inspiration / 声音及动态复核状态见数据'])
    e=html.escape
    def para(label,text):return f'<h4>{e(label)}</h4><p>{e(str(text or "待补"))}</p>'
    cards=[]
    for s in shots:
        cues=[c for c in pool['dialogue'] if min(c['end'],s['end'])>max(c['start'],s['start'])]
        speech=[r for r in raw if min(r['end'],s['end'])>max(r['start'],s['start'])]
        pics=''.join(f'<a href="{quote(v,safe="/:")}" target="_blank"><img src="{quote(v,safe="/:")}" alt="{e(s["id"]+" "+k)}"><small>{e(k)}</small></a>' for k,v in s.get('frames',{}).items())
        dims=s.get('fiveDimensions',{});prompts=s.get('generationPrompts',{})
        cards.append(f'''<article class="shot" id="shot-{e(s['id'])}" data-start="{s['start']}" data-end="{s['end']}"><header><button class="jump" data-time="{s['start']}">{e(s['id'])} · {s['start']:.3f}–{s['end']:.3f}s</button><span>{e(s.get('recordType','shot'))} · {e(s.get('size',''))}</span></header><div class="columns"><section><h3>aipi · 画面与声音证据</h3><div class="frames">{pics}</div>{para('出镜人物',' / '.join(s.get('subjects',[])) or '无人物')}{para('画面事实',s.get('description'))}{para('对白／字幕来源','\n'.join(c['speaker']+'：'+c['text'] for c in cues) or '未见字幕，不等于无对白')}{para('本地ASR · 机器原文待听审','\n'.join(f"{r['start']:.2f}–{r['end']:.2f}s：{r['text']}" for r in speech) or '无重叠识别结果，不等于无声音')}<small>字幕与ASR分别保存；说话人、发声边界及音效以审核记录为准。</small></section><section><h3>OpenChatCut · 五维导演分析</h3>{''.join(para(k,dims.get(k)) for k in ['构图','焦距感／心理距离','运镜动机','剪辑理由','叙事功能'])}{para('复拍建议',s.get('director',{}).get('reshoot'))}<small>导演意图为分析推断；真实焦距没有证据时不填。</small></section><section><h3>飞书拉片 · 本地素材库输出</h3>{para('分镜图提示词',prompts.get('storyboard'))}{para('视频提示词',prompts.get('video'))}{para('提示词来源与状态',prompts.get('source','当前Agent复刻草稿；未生成测试；未写入飞书'))}{para('证据与疑点','\n'.join(s.get('evidence',[])))}</section></div></article>''')
    group_html=''.join(f'<section class="group"><h3>{e(g["id"])} · {e(g.get("mechanism",""))}</h3>{para("关联镜头"," / ".join(g["shotIds"]))}{para("成立条件",g.get("conditions"))}{para("迁移限制",g.get("limits"))}</section>' for g in groups)
    data=json.dumps(pool,ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>复合逐镜头工作台</title><style>
    *{box-sizing:border-box}body{margin:0;background:#101319;color:#e8edf5;font:14px/1.65 system-ui,'Microsoft YaHei',sans-serif}main{max-width:1800px;margin:auto;padding:18px}h1{font-size:22px;margin:0}h3{font-size:15px;color:#edbe7c}h4{font-size:13px;margin:14px 0 3px;color:#b8c7dc}p{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}small{color:#a9b5c7}a{color:#a6cff5}button,input{font:inherit;background:#243249;color:#edf2fa;border:1px solid #486080;border-radius:6px;padding:8px;cursor:pointer}button:focus-visible,input:focus-visible{outline:2px solid #edbe7c}.monitor{position:sticky;top:0;z-index:2;background:#101319f5;border-bottom:1px solid #344052;padding:10px 0;display:grid;grid-template-columns:minmax(300px,560px) 1fr;gap:16px}video{width:100%;max-height:31vh;background:#000}.tools{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.tools input{min-width:210px;flex:1}article,.group{border:1px solid #344052;border-radius:8px;padding:16px;margin:18px 0;background:#181e28}.shot.active{border-color:#edbe7c}.shot header{display:flex;justify-content:space-between;gap:10px;align-items:center}.columns{display:grid;grid-template-columns:1fr 1fr 1fr;gap:24px}.columns section{min-width:0}.frames{display:flex;gap:8px}.frames a{display:block;width:50%}.frames img{display:block;width:100%}.badge{color:#edbe7c}.warning{color:#d6b78c}#count{margin:10px 0}.group{background:#192323}@media(max-width:900px){.columns{grid-template-columns:1fr}.monitor{position:static;grid-template-columns:1fr}video{max-height:42vh}.shot header{align-items:flex-start;flex-direction:column}}
    </style><main><h1>复合逐镜头工作台</h1><p class="badge">aipi 取证 · OpenChatCut 五维分析 · 飞书拉片字段与复刻提示词</p><div class="monitor"><video id="video" controls preload="metadata" src="VIDEO"></video><div><h3>TITLE</h3><p>COUNT · 本地参考素材池</p><p class="warning">使用等级：灵感参考。机器转写已取得；听审、说话人、动态复核及音效状态以审核记录为准。</p><p id="now">当前片段：—</p><div class="tools"><button id="previous">上一段</button><button id="next">下一段</button><label><input id="follow" type="checkbox"> 跟随播放滚动</label></div><div class="tools"><input id="search" aria-label="搜索全部拉片内容" placeholder="搜索人物、对白、技法、提示词"><a href="asset-pool.json" download>素材池JSON</a><a href="asset-pool.csv" download>逐镜CSV</a></div><small>下方每段直接展示三部分。点击镜号定位原片；ASR时间是机器估计。</small></div></div><p id="count"></p><h2>镜头组与脚本优化交接</h2>GROUPS<h2>逐段记录</h2>CARDS<script id="pool-data" type="application/json">DATA</script><script>
    const pool=JSON.parse(document.getElementById('pool-data').textContent),v=document.getElementById('video'),rows=[...document.querySelectorAll('.shot')];let active=-1;const seek=t=>{v.currentTime=t;};document.querySelectorAll('.jump').forEach(b=>b.addEventListener('click',()=>seek(Number(b.dataset.time))));document.getElementById('previous').onclick=()=>seek(pool.shots[Math.max(0,active-1)].start);document.getElementById('next').onclick=()=>seek(pool.shots[Math.min(pool.shots.length-1,active+1)].start);v.addEventListener('timeupdate',()=>{let i=pool.shots.findIndex(s=>v.currentTime>=s.start&&v.currentTime<s.end);if(i<0&&v.currentTime>=pool.shots.at(-1).end)i=pool.shots.length-1;if(i!==active&&i>=0){rows.forEach((r,j)=>r.classList.toggle('active',i===j));active=i;document.getElementById('now').textContent='当前片段：'+pool.shots[i].id;if(document.getElementById('follow').checked&&!rows[i].hidden)rows[i].scrollIntoView({block:'center'});}});const search=document.getElementById('search');function filter(){const q=search.value.trim().toLowerCase();rows.forEach((r,i)=>r.hidden=!(r.textContent+' '+JSON.stringify(pool.shots[i])).toLowerCase().includes(q));document.getElementById('count').textContent='显示 '+rows.filter(r=>!r.hidden).length+' / '+rows.length+' 段';}search.addEventListener('input',filter);filter();v.addEventListener('error',()=>document.getElementById('now').textContent='原片无法加载，请检查原片路径；数据与图片仍可阅读。');
    </script></main></html>'''
    for key,value in [('VIDEO',quote(source['file'],safe='/:' )),('TITLE',e(pool['title'])),('COUNT',f"{len(shots)}段（{sum(s.get('recordType','shot')=='shot' for s in shots)}个内容镜头）"),('GROUPS',group_html),('CARDS',''.join(cards)),('DATA',data)]:page=page.replace(key,value)
    (out/'report.html').write_text(page,encoding='utf-8')
    return {'shots':len(shots),'sequences':len(groups),'out':str(out),'usageState':pool['usageState']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',required=True);p.add_argument('--out',required=True);p.add_argument('--sequences');a=p.parse_args()
    print(json.dumps(export(a.study,a.out,a.sequences)))
