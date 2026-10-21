import json,platform,sys
from tool_paths import ROOT,tool
result={'version':'0.2.1','python':platform.python_version(),'platform':sys.platform,'tools':{},'externalSkillsRequired':[],'localModel':(ROOT/'runtime/model-small/model.bin').is_file(),'localASR':(ROOT/'runtime/python-packages/faster_whisper').is_dir()}
for name in ['node','ffmpeg','ffprobe']:
    try:result['tools'][name]=tool(name)
    except SystemExit:result['tools'][name]=None
print(json.dumps(result,indent=2))
