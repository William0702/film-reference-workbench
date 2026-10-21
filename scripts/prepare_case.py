"""Unified evidence preparation; director analysis remains an Agent task."""
import argparse,json,subprocess,sys
from pathlib import Path
from tool_paths import ROOT
def main():
    p=argparse.ArgumentParser();p.add_argument('--video',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    video=Path(a.video).resolve();out=Path(a.out).resolve()
    if not video.is_file():raise SystemExit('Video not found')
    if out.exists() and any(out.iterdir()):raise SystemExit('Output is not empty; resume existing evidence instead of overwriting')
    out.mkdir(parents=True,exist_ok=True)
    def run(script,args):
        result=subprocess.run([sys.executable,str(ROOT/'scripts'/script),*map(str,args)],capture_output=True,text=True,encoding='utf-8',errors='replace')
        if result.returncode:raise RuntimeError(result.stdout+'\n'+result.stderr)
        return json.loads(result.stdout)
    probe=run('media.py',['probe',video]);(out/'probe.json').write_text(json.dumps(probe,ensure_ascii=False,indent=2),encoding='utf-8')
    detected=run('media.py',['detect',video,'--out',out/'study.json'])
    frames=run('media.py',['frames',out/'study.json','--video',video,'--out',out/'frames'])
    asr=run('run_asr.py',['--video',video,'--out',out/'asr'])
    data=json.loads((out/'study.frames.json').read_text(encoding='utf-8'))
    data['machineAudioEvidence']={'file':'asr/transcript.raw.json','state':'machine_transcript_unreviewed'}
    data['review']['audio']['openIssues']=['已取得本地机器转写，逐句听审、说话人及音效待核；画面字幕另行提取。']
    (out/'study.frames.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'shots':detected['shots'],'referenceFrames':frames['frames'],'machineDialogueSegments':asr['segments'],'externalSkillCalls':[],'stage':'evidence-prepared / analysis-required','next':'Review actual frames and audio, fill facts, fiveDimensions, generationPrompts, sequences; then export_pool.py'}
    (out/'preparation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()
