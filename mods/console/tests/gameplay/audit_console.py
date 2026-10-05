"""Independent audit: native engine/input/audio only; no plug-in logs or private layouts."""
import json,math,sys,hashlib
from pathlib import Path
s=Path(sys.argv[1]);plugin=Path(sys.argv[2]);launch=json.loads((s/'launch.json').read_text(encoding='utf-8-sig'))
digest=hashlib.sha256(plugin.read_bytes()).hexdigest().upper()
assert any(x['Path'].endswith('console-pause-fix.vtm') and x['Hash']==digest for x in launch['Candidates'])
assert launch['SaveHash']=='C60EFE346A669FDD9668C0191521219E112049510DC6648907B1FD0FF2B5856A'
first=json.loads((s/'runner-result.json').read_text());last=json.loads((s/'remaining-result.json').read_text())
assert first['completed']==['x','tilde','ordinary','menu'] and not first['passed']
assert last['passed'] and last['completed']==['script','reload']
records=[json.loads(x) for x in (s/'input.jsonl').read_text().splitlines()]
probes=[json.loads(x) for x in (s/'probes.jsonl').read_text().splitlines()]
assert [x['label'] for x in probes]==['after_x','after_tilde','script_resumed','after_reload']
timings=[]
for result in probes:
 label=result['label'];assert result['passed']
 group=lambda suffix:[x for x in records if x['label']==label+suffix]
 quiet,=group('_quiet');mouse=group('_mouse');moves=group('_move')
 assert len(mouse)==len(moves)==2 and [x['command'] for x in moves]==['+back','+forward']
 assert quiet['after']['client_time']-quiet['before']['client_time']>.1
 assert math.dist(quiet['before']['origin'][:2],quiet['after']['origin'][:2])<1
 yaw=[(x['after']['angles'][1]-x['before']['angles'][1]+180)%360-180 for x in mouse];assert yaw[0]*yaw[1]<0 and min(map(abs,yaw))>.5
 for x in moves:
  angle=math.radians(x['before']['angles'][1]);delta=[x['after']['origin'][i]-x['before']['origin'][i] for i in (0,1)]
  dot=delta[0]*math.cos(angle)+delta[1]*math.sin(angle);assert (-dot if x['command']=='+back' else dot)>2
  name=x['command'][1:];assert x['held']['keys'][name][2]&1 and not x['after']['keys'][name][2]&1
  assert x['held']['os_keys'][x['binding'].upper()] and not any(x['held']['os_keys'][k] for k in ('Ctrl','Alt','Shift'))
 for x in [quiet,*mouse,*moves]:
  for r in (x['before'],x['after']):assert r['foreground'] and r['mouse_active']==1 and r['server_paused']==r['paused']==r['menu_pause_depth']==0 and 'clock' not in r
 wait,=[x for x in records if x['label']=='input_ready_wait' and x['probe']==label];elapsed=wait['after']['wall']-wait['before']['wall'];assert wait['delay_seconds']==5 and elapsed>=4.9
 timings.append({'probe':label,'external_wait_actual_seconds':elapsed,'first_mouse_after_ready_wait_start':mouse[0]['before']['wall']-wait['before']['wall'],'first_back_after_ready_wait_start':moves[0]['before']['wall']-wait['before']['wall']})
controls=[json.loads(x) for x in (s/'controls.jsonl').read_text().splitlines()]
for label in ['x_open','tilde_open','ordinary_before','ordinary_after','menu_restored']:
 rows=[x for x in controls if x['label']==label];assert len(rows)>=8 and all(r['paused']==r['server_paused']==1 and r['audio'] for r in rows)
 assert len({r['client_time'] for r in rows})==len({tuple((x['mixer'],x['position'],x['caption']) for x in r['audio']) for r in rows})==1
 if label=='menu_restored':assert all(r['menu']['visible'] and r['menu_pause_depth']==1 for r in rows)
for label in ['audio_ready','x_resumed','tilde_resumed','ordinary_resumed','menu_resumed']:
 rows=[x for x in controls if x['label']==label];assert rows[-1]['client_time']>rows[0]['client_time']+.2 and rows[-1]['audio'][0]['position']>rows[0]['audio'][0]['position']
script=[json.loads(x) for x in (s/'remaining-controls.jsonl').read_text().splitlines()];assert len(script)==10 and all(r['pause_depth']==r['server_paused']==r['paused']==1 and r['menu_pause_depth']==0 and not r['console']['visible'] for r in script) and len({r['client_time'] for r in script})==1
report={'result':'PASS','hash':digest,'scope':'Distinct X/tilde/ordinary/menu/script/reload workflows with measured five-second external readiness wait; immediate input NOT certified','first_result_preserved':True,'earlier_limit':'One console-opening key shortly after menu exit did not open console; original failed record retained, no movement retry replaced a failure','timings':timings,'native_audio_freeze_resume':True,'private_plugin_state_or_log_reads':False}
(s/'gameplay-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
