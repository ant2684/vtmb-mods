"""Distinct final-byte console workflows. Record first result and stop on failure."""
from driver import *
import traceback
session=Path(sys.argv[1]);d=None;completed=[]
def audio(d):
 p=d.p;e=p.modules['engine.dll'];r=d.snap();r['audio']=[]
 for i in range(min(p.u(e+0x13107d4),128)):
  a=e+0x1310b08+i*0xa0;sfx=p.u(a)
  if not sfx:continue
  name=p.read(sfx+4,256).split(b'\0',1)[0].decode('cp1252','replace');mixer=p.u(a+4)
  if 'radio_loop_' in name and mixer:r['audio'].append({'name':name,'mixer':mixer,'position':p.d(mixer+8),'caption':p.u(a+0x94)})
 return r
def sample(label,seconds=1):
 rows=[];end=time.monotonic()+seconds
 while time.monotonic()<end:rows.append(audio(d));d.delay(.1)
 with (session/'controls.jsonl').open('a') as f:
  for r in rows:f.write(json.dumps(dict(label=label,**r))+'\n')
 return rows
def frozen(label):
 rows=sample(label);assert all(r['paused']==r['server_paused']==1 for r in rows)
 assert len({r['client_time'] for r in rows})==1
 assert all(r['audio'] for r in rows),'Radio channel not ready'
 assert len({tuple((x['mixer'],x['position'],x['caption']) for x in r['audio']) for r in rows})==1
def running(label):
 rows=sample(label);assert rows[-1]['client_time']-rows[0]['client_time']>.2
 assert all(r['paused']==r['server_paused']==0 and r['audio'] for r in rows)
 assert rows[-1]['audio'][0]['position']>rows[0]['audio'][0]['position'],'Native audio mixer did not resume'
def probe(label):
 before=d.snap();d.delay(5);d.log('input_ready_wait',before,d.snap(),probe=label,delay_seconds=5)
 result=d.probe(label)
 with (session/'probes.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
 assert result['passed'],result
def stage(label):completed.append(label);print('PASS',label,flush=True)
try:
 time.sleep(25);d=Driver(session)
 # Startup console changes visibility asynchronously while the load finishes.
 # Wait for a stable live player/world before any command or test input.
 before=d.snap();d.delay(2);after=d.snap()
 assert after['player_handle']==before['player_handle'] and after['client_time']>before['client_time'] and not after['console']['visible'],'Scene not stable'
 d.text_command('ent_fire Radio2 Activate',1)
 if d.snap()['console']['visible']:d.click_x()
 d.delay(.5);running('audio_ready')
 for closing in ('x','tilde'):
  d.phase=closing;d.toggle(True);frozen(closing+'_open')
  if closing=='x':d.click_x()
  else:d.toggle(False)
  probe('after_'+closing);running(closing+'_resumed');stage(closing)
 cfg=(Path(json.loads((session/'launch.json').read_text(encoding='utf-8-sig'))['GameRoot'])/'Unofficial_Patch/cfg/config.cfg').read_text(encoding='cp1252')
 assert not re.search(r'bind "F11"',cfg,re.I),'Existing personal F11 binding'
 d.phase='ordinary';d.text_command('bind F11 pause',.25);d.click_x();d.key(0x7a);d.delay(.4);frozen('ordinary_before');d.toggle(True);d.click_x();frozen('ordinary_after');d.key(0x7a);d.delay(.4);running('ordinary_resumed');stage('ordinary')
 d.phase='menu';d.key(0x1b);d.delay(.3);assert d.snap()['menu']['visible'];d.toggle(True);d.click_x();frozen('menu_restored');assert d.snap()['menu']['visible'] and d.snap()['menu_pause_depth']==1;d.key(0x1b);d.delay(.3);running('menu_resumed');stage('menu')
 d.phase='script';d.text_command('exec console_task_overlap.cfg',.25);frozen('script_preserved');assert d.snap()['pause_depth']==1 and d.snap()['menu_pause_depth']==0 and not d.snap()['console']['visible']
 deadline=time.monotonic()+60
 while d.snap()['pause_depth']:assert time.monotonic()<deadline,'Native v_unpause timeout';d.delay(.2)
 probe('script_resumed');running('script_audio_resumed');stage('script')
 d.phase='reload';d.text_command('load rc_console',4);d.text_command('ent_fire Radio2 Activate',.3);d.click_x();probe('after_reload');running('reload_audio');stage('reload')
 (session/'runner-result.json').write_text(json.dumps({'passed':True,'completed':completed}));print('PASS all distinct console workflows',flush=True)
except BaseException as error:
 result={'passed':False,'completed':completed,'error':repr(error),'traceback':traceback.format_exc()}
 if d:
  try:result['snapshot']=d.snap()
  except BaseException:pass
 (session/'runner-result.json').write_text(json.dumps(result,indent=2));print('FAIL',repr(error),flush=True);raise
