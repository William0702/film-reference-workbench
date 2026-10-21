import argparse,os,subprocess
from pathlib import Path
from tool_paths import ROOT,tool
def main():
    p=argparse.ArgumentParser();p.add_argument('--node');p.add_argument('--ffmpeg');p.add_argument('--ffprobe');p.add_argument('engine_args',nargs=argparse.REMAINDER);a=p.parse_args()
    if not a.engine_args:p.error('Pass probe/detect/frames/validate or another engine command')
    node=tool('node',a.node);ffmpeg=tool('ffmpeg',a.ffmpeg);ffprobe=tool('ffprobe',a.ffprobe)
    env=os.environ.copy();env['PATH']=os.pathsep.join([str(Path(ffmpeg).parent),str(Path(ffprobe).parent)])+os.pathsep+env.get('PATH','')
    return subprocess.call([node,str(ROOT/'vendor/aipi-film-study/scripts/engine.mjs'),*a.engine_args],env=env)
if __name__=='__main__':raise SystemExit(main())
