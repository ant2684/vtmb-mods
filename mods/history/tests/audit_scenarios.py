"""Gate installation on unique workflows and exact clean bytes."""
import json,hashlib,sys
from pathlib import Path
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
work,binary,output=map(Path,sys.argv[1:])
h=hashlib.sha256(binary.read_bytes()).hexdigest().upper()
t=read(work/'source/build/technical-verification.json');assert t['result']=='PASS' and t['hash']==h
scenarios=[]
for name in ['clean_transition','clean_history']:
 p=work/'sessions'/name;s=read(p/'scenario-verification.json');launch=read(p/'launch.json')
 assert s['result']=='PASS' and s['hash']==launch['PluginHash']==h
 assert '-condebug' not in launch['Arguments']
 assert not any(a in launch['Arguments'] for a in ['-window','-windowed','-w','-h','-fullscreen','-width','-height'])
 scenarios.append({'session':name,**s})
report={'result':'PASS','hash':h,'technical_cases':t['cases'],'scenarios':scenarios,'coverage_reason':'Actual non-None purchase to gender transition and full refreshed pool; separate None/reverse-gender/explicit History reset path. No Cartesian repetition.','observer':'read-only process, native getters and costs run on isolated offline pages'}
output.write_text(json.dumps(report,indent=2));print(json.dumps(report))
