"""Explicit opt-in download of a fixed upstream model revision."""
import argparse,hashlib,json,urllib.request
from pathlib import Path
repo='Systran/faster-whisper-small';revision='536b0662742c02347bc0e980a01041f333bce120'
p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
files={}
for name in ['config.json','model.bin','tokenizer.json','vocabulary.txt']:
    target=out/name
    if target.exists():raise SystemExit('Refusing to overwrite existing model file: '+name)
    url=f'https://huggingface.co/{repo}/resolve/{revision}/{name}'
    digest=hashlib.sha256()
    with urllib.request.urlopen(url,timeout=60) as response,target.with_suffix(target.suffix+'.partial').open('wb') as stream:
        size=0;expected=int(response.headers.get('Content-Length',0))
        while True:
            chunk=response.read(1024*1024)
            if not chunk:break
            stream.write(chunk);digest.update(chunk);size+=len(chunk)
    if expected and size!=expected:raise RuntimeError('Incomplete model file')
    target.with_suffix(target.suffix+'.partial').replace(target)
    files[name]={'bytes':size,'sha256':digest.hexdigest()}
(out/'model-manifest.json').write_text(json.dumps({'repository':repo,'revision':revision,'files':files},indent=2),encoding='utf-8')
print('Local model download complete.')
