"""Local ASR: run with an already installed faster-whisper environment."""
import argparse,json,subprocess,wave
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    for name in ('video','model','ffmpeg','out'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    video=Path(args.video).resolve();model=Path(args.model).resolve();out=Path(args.out).resolve()
    if not video.is_file() or not (model/'model.bin').is_file():raise SystemExit('Video or local model missing')
    out.mkdir(parents=True,exist_ok=True)
    import numpy as np
    from faster_whisper import WhisperModel
    wav=out/'source-16k-mono.wav'
    subprocess.run([args.ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(video),'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(wav)],check=True)
    with wave.open(str(wav),'rb') as stream:
        assert (stream.getnchannels(),stream.getsampwidth(),stream.getframerate())==(1,2,16000)
        audio=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float32)/32768.0
    engine=WhisperModel(str(model),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
    segments,info=engine.transcribe(audio,language='zh',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
    rows=[{'id':s.id,'start':s.start,'end':s.end,'text':s.text,'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in (s.words or [])]} for s in segments]
    data={'source':str(video),'modelPath':str(model),'language':info.language,'duration':info.duration,'review_state':'machine_transcript_unreviewed','segments':rows}
    (out/'transcript.raw.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'segments':len(rows),'out':str(out)},ensure_ascii=True))
if __name__=='__main__':main()
