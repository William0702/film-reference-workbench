"""Resolve only this skill's local runtime or explicit/system tools."""
import shutil,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=Path(os.environ.get('FILM_REFERENCE_RUNTIME',str(ROOT/'runtime'))).resolve()
def tool(name,override=None):
    if override:
        found=shutil.which(override)
    else:
        local=RUNTIME/'tools'/(name+'.exe')
        found=str(local) if local.is_file() else shutil.which(name)
    if not found:raise SystemExit('Missing tool: '+name)
    return found
