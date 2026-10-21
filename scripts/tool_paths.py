"""Resolve only this skill's local runtime or explicit/system tools."""
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def tool(name,override=None):
    if override:
        found=shutil.which(override)
    else:
        local=ROOT/'runtime'/'tools'/(name+'.exe')
        found=str(local) if local.is_file() else shutil.which(name)
    if not found:raise SystemExit('Missing tool: '+name)
    return found
