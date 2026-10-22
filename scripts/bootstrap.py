"""Check, repair and smoke-test the Windows runtime. No repair without --repair."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
import uuid
import stat
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

def download(url, target, expected, mirrors=()):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and digest(target) == expected: return
    partial = target.with_name(target.name + '.partial')
    failures=[]
    for source in (url,*mirrors):
        for attempt in range(2):
            print(f'Download (attempt {attempt+1}): {source}', file=sys.stderr, flush=True)
            try:
                with urllib.request.urlopen(source, timeout=60) as response, partial.open('wb') as f:
                    shutil.copyfileobj(response, f, length=1024*1024)
            except (OSError, TimeoutError) as e:
                failures.append(str(e))
                if attempt==0:time.sleep(1)
                continue
            if digest(partial) != expected: raise RuntimeError('SHA256 mismatch: ' + target.name)
            partial.replace(target)
            return
    raise RuntimeError('Download failed: '+target.name+'; '+'; '.join(failures))

def probe_tool(name):
    try:
        path = tool(name)
        r = run([path, '--version' if name == 'node' else '-version'], capture_output=True)
        if name == 'node' and int(r.stdout.strip().lstrip('v').split('.')[0]) < 18:
            return {'ok': False, 'error': 'Node.js 18+ required'}
        return {'ok': True, 'path': path, 'version': r.stdout.splitlines()[0]}
    except (SystemExit, Exception) as e:
        return {'ok': False, 'error': str(e)}

def runtime_directory(prefix):
    # tempfile.mkdtemp uses a protected owner-only DACL on Windows Python 3.12.
    # These generated public tools/results must inherit the chosen runtime's ACL.
    path=RUNTIME/(prefix+uuid.uuid4().hex)
    path.mkdir()
    return path

def rename_directory(source,target):
    # Windows scanners/native-loader teardown can briefly retain a directory.
    # Do not force replacement or suppress persistent access failures.
    for attempt in range(8):
        try:
            source.rename(target)
            return
        except PermissionError as e:
            if sys.platform!='win32' or getattr(e,'winerror',None) not in (5,32) or attempt==7:raise
            time.sleep(0.5*(attempt+1))

def inherit_runtime_access(path):
    """Enable existing parent ACL inheritance only; never add principals/grants."""
    path=Path(path)
    if sys.platform!='win32':return
    if path.parent.resolve()!=RUNTIME.resolve() or not (path.name=='python-packages' or path.name.startswith('packages-stage-')):
        raise RuntimeError('Permission repair restricted to generated dependency directories')
    marker=path/'.film-runtime-access.json'
    policy={'schema':'parent-acl-inheritance/v1','runtime':str(RUNTIME.resolve())}
    # A validated stage carries its repair record through the atomic rename.
    # Later readers with Modify access need not request WRITE_DAC again.
    try:
        if json.loads(marker.read_text(encoding='utf-8'))==policy:return
    except (OSError,ValueError):pass
    # Do not traverse links into another location while changing inheritance.
    def walk_error(error):raise error
    for parent,dirs,files in os.walk(path,followlinks=False,onerror=walk_error):
        for item in [Path(parent),*(Path(parent)/n for n in dirs+files)]:
            if item.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise RuntimeError('Refusing permission repair through a reparse point')
    icacls=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/icacls.exe'
    absolute=str(path.resolve())
    native_path=('\\\\?\\UNC\\'+absolute[2:]) if absolute.startswith('\\\\') else ('\\\\?\\'+absolute)
    try:
        run([icacls,native_path,'/inheritancelevel:e','/T','/Q'],capture_output=True,timeout=120)
    except subprocess.CalledProcessError as e:
        raise RuntimeError('Cannot inherit runtime access; run setup as the installation owner. '+e.stdout[-1000:]+e.stderr[-1000:]) from e
    marker.write_text(json.dumps(policy),encoding='utf-8')

def check_packages(packages=None):
    packages = Path(packages) if packages else RUNTIME/'python-packages'
    if packages.exists():
        try:next(packages.iterdir(),None)
        except PermissionError:return {'ok':False,'error':'Dependency directory is not readable. Run setup as the installation owner to repair runtime ACL inheritance.'}
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
        download(spec['url'], archive, spec['sha256'],spec.get('mirrors',[]))
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
        stage=runtime_directory('packages-stage-')
        run([sys.executable,'-m','pip','install','--disable-pip-version-check','--only-binary=:all:',
             '--index-url','https://pypi.org/simple','--target',stage,'-r',ROOT/'requirements-win-py312.lock.txt'])
        inherit_runtime_access(stage)
        validated=check_packages(stage)
        if not validated['ok']:raise RuntimeError('Staged dependencies failed verification: '+validated['error'])
        old=RUNTIME/'python-packages'
        if old.exists(): rename_directory(old,RUNTIME/('packages-backup-'+str(time.time_ns())))
        rename_directory(stage,old)
    for name, sha in lock['model']['files'].items():
        download(f"https://huggingface.co/{lock['model']['repository']}/resolve/{lock['model']['revision']}/{name}",RUNTIME/'model-small'/name,sha)

def self_test():
    out=runtime_directory('self-test-')
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
    result={'ok':False,'version':'0.3.3'}
    try:
        if a.repair and (RUNTIME/'python-packages').is_dir():
            inherit_runtime_access(RUNTIME/'python-packages')
            result['permissionRepair']='Enabled parent ACL inheritance on generated dependencies; no principals added'
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
