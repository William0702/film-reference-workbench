import argparse,os,runpy,sys
from pathlib import Path
from tool_paths import ROOT,tool
def main():
    p=argparse.ArgumentParser();p.add_argument('--video',required=True);p.add_argument('--out',required=True);p.add_argument('--model',default=str(ROOT/'runtime/model-small'));p.add_argument('--ffmpeg');a=p.parse_args()
    if sys.platform!='win32' or sys.version_info[:2]!=(3,12):raise SystemExit('Local runtime requires Windows x64 CPython3.12')
    packages=ROOT/'runtime/python-packages'
    if not packages.is_dir():raise SystemExit('Packaged Python dependencies are missing')
    sys.path.insert(0,str(packages))
    if not (Path(a.model)/'model.bin').is_file():raise SystemExit('Local model is missing')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
    sys.argv=[str(ROOT/'scripts/transcribe.py'),'--video',a.video,'--out',a.out,'--model',a.model,'--ffmpeg',tool('ffmpeg',a.ffmpeg)]
    runpy.run_path(sys.argv[0],run_name='__main__')
if __name__=='__main__':main()
