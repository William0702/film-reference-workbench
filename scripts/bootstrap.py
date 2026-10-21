"""Check, repair and smoke-test the Windows runtime. No repair without --repair."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from tool_paths import ROOT, RUNTIME, tool

LOCK = ROOT / 'references/runtime-lock.json'

def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, encoding='utf-8', errors='replace', **kwargs)

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def download(url, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and digest(target) == expected: return
    partial = target.with_name(target.name + '.partial')
    print('Download: ' + url, file=sys.stderr, flush=True)
    with urllib.request.urlopen(url, timeout=60) as response, partial.open('wb') as f:
        shutil.copyfileobj(response, f, length=1024*1024)
    if digest(partial) != expected: raise RuntimeError('SHA256 mismatch: ' + target.name)
    partial.replace(target)

def probe_tool(name):
    try:
        path = tool(name)
        r = run([path, '--version' if name == 'node' else '-version'], capture_output=True)
        if name == 'node' and int(r.stdout.strip().lstrip('v').split('.')[0]) < 18:
            return {'ok': False, 'error': 'Node.js 18+ required'}
        return {'ok': True, 'path': path, 'version': r.stdout.splitlines()[0]}
    except (SystemExit, Exception) as e:
        return {'ok': False, 'error': str(e)}

def check_packages():
    packages = RUNTIME/'python-packages'
    code = '''import sys,json,importlib.metadata as m
sys.path.insert(0,sys.argv[1])
from pathlib import Path
bad=[]
for line in Path(sys.argv[2]).read_text().splitlines():
 if not line.strip() or line.startswith('#'):continue
 name,want=line.split('==')
 try:
  distribution=m.distribution(name)
  got=distribution.version
  if got!=want or not Path(distribution.locate_file('')).resolve().is_relative_to(Path(sys.argv[1]).resolve()):bad.append(name)
 except m.PackageNotFoundError:bad.append(name)
if bad:raise SystemExit('Missing/mismatched local dependencies: '+', '.join(bad))
import numpy,av,ctranslate2,onnxruntime,faster_whisper,tokenizers
print(json.dumps({'ok':True}))
'''
    try:
        run([sys.executable, '-X', 'utf8', '-c', code, packages, ROOT/'requirements-win-py312.lock.txt'], capture_output=True)
        return {'ok':True}
    except subprocess.CalledProcessError as e:
        return {'ok':False, 'error':e.stderr[-3000:]}

def model_status(lock):
    result={}
    for name, sha in lock['model']['files'].items():
        path=RUNTIME/'model-small'/name
        result[name]=path.is_file() and digest(path)==sha
    return {'ok':all(result.values()), 'files':result}

def check(lock):
    return {'platform':sys.platform, 'python':platform.python_version(),
            'supported':sys.platform=='win32' and sys.version_info[:2]==(3,12) and platform.machine().lower() in ('amd64','x86_64'),
            'tools':{n:probe_tool(n) for n in ('node','ffmpeg','ffprobe')},
            'packages':check_packages(), 'model':model_status(lock), 'externalSkillsRequired':[]}

def ready(report):
    return report['supported'] and all(x['ok'] for x in report['tools'].values()) and report['packages']['ok'] and report['model']['ok']

def repair(report, lock):
    if not report['supported']: raise RuntimeError('Use Windows x64 Python 3.12; run scripts/setup.ps1')
    if not report['tools']['node']['ok']:
        spec=lock['node']
        with urllib.request.urlopen(spec['checksumsUrl'],timeout=60) as response:
            sums=response.read().decode('utf-8').splitlines()
        matches=[s.split()[0] for s in sums if len(s.split())==2 and s.split()[1]==spec['filename']]
        if len(matches)!=1 or len(matches[0])!=64:raise RuntimeError('Node checksum not found')
        archive=RUNTIME/'downloads'/spec['filename'];download(spec['url'],archive,matches[0])
        target=RUNTIME/'node-distribution'/spec['version'];target.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                if not (target/entry.filename).resolve().is_relative_to(target.resolve()):raise RuntimeError('Unsafe archive path')
            z.extractall(target)
        executables=list(target.rglob('node.exe'))
        if len(executables)!=1:raise RuntimeError('Unexpected Node archive structure')
        (RUNTIME/'tools').mkdir(exist_ok=True);shutil.copy2(executables[0],RUNTIME/'tools/node.exe')
    if not all(report['tools'][n]['ok'] for n in ('ffmpeg','ffprobe')):
        spec=lock['ffmpeg']; archive=RUNTIME/'downloads'/spec['filename']
        download(spec['url'], archive, spec['sha256'])
        target=RUNTIME/'ffmpeg-distribution'/spec['version']
        target.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                resolved=(target/entry.filename).resolve()
                if not resolved.is_relative_to(target.resolve()): raise RuntimeError('Unsafe archive path')
            z.extractall(target)
        (RUNTIME/'tools').mkdir(exist_ok=True)
        for n in ('ffmpeg','ffprobe'):
            matches=list(target.rglob(n+'.exe'))
            if len(matches)!=1: raise RuntimeError('Unexpected FFmpeg archive structure')
            shutil.copy2(matches[0],RUNTIME/'tools'/(n+'.exe'))
    if not report['packages']['ok']:
        pip=subprocess.run([sys.executable,'-m','pip','--version'],capture_output=True)
        if pip.returncode:run([sys.executable,'-m','ensurepip'])
        stage=Path(tempfile.mkdtemp(prefix='packages-stage-',dir=RUNTIME))
        run([sys.executable,'-m','pip','install','--disable-pip-version-check','--only-binary=:all:',
             '--index-url','https://pypi.org/simple','--target',stage,'-r',ROOT/'requirements-win-py312.lock.txt'])
        old=RUNTIME/'python-packages'
        if old.exists(): old.rename(RUNTIME/('packages-backup-'+str(time.time_ns())))
        stage.rename(old)
    for name, sha in lock['model']['files'].items():
        download(f"https://huggingface.co/{lock['model']['repository']}/resolve/{lock['model']['revision']}/{name}",RUNTIME/'model-small'/name,sha)

def self_test():
    out=Path(tempfile.mkdtemp(prefix='self-test-',dir=RUNTIME))
    video=out/'synthetic.mp4'
    run([tool('ffmpeg'),'-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=10:duration=1',
         '-f','lavfi','-i','anullsrc=r=16000:cl=mono','-t','1','-c:v','mpeg4','-c:a','aac',video],capture_output=True)
    run([sys.executable,'-X','utf8',ROOT/'scripts/prepare_case.py','--video',video,'--out',out/'case'],capture_output=True)
    run([sys.executable,'-X','utf8',ROOT/'scripts/export_pool.py','--study',out/'case/study.frames.json','--out',out/'case'],capture_output=True)
    required=['preparation.json','report.html','asset-pool.json','asset-pool.csv']
    if not all((out/'case'/n).is_file() for n in required):raise RuntimeError('Incomplete self-test output')
    return {'ok':True,'directory':str(out),'coverage':'synthetic video -> probe/cuts/frames/ASR -> HTML/pool; not director analysis or browser UI validation'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--repair',action='store_true');p.add_argument('--self-test',action='store_true');a=p.parse_args()
    lock=json.loads(LOCK.read_text(encoding='utf-8'))
    RUNTIME.mkdir(parents=True,exist_ok=True)
    flag=RUNTIME/'.bootstrap.lock'
    try: fd=os.open(flag,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError: raise SystemExit('Another setup is running, or previous setup was interrupted. Inspect runtime/.bootstrap.lock before retrying.')
    os.close(fd)
    result={'ok':False,'version':'0.3.0'}
    try:
        result['before']=check(lock)
        if a.repair and not ready(result['before']):repair(result['before'],lock)
        result['after']=check(lock)
        result['ok']=ready(result['after'])
        if a.self_test and result['ok']: result['selfTest']=self_test()
    except Exception as e:
        result['ok']=False;result['error']=str(e)
    finally:
        flag.unlink(missing_ok=True)
        (RUNTIME/'setup-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 1

if __name__=='__main__':sys.exit(main())
