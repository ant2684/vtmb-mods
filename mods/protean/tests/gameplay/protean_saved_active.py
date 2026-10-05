"""Final-byte Protean lifecycle and filter workflows on an archived save."""
from driver import *
from actors import snapshot
from warehouse_gate import check as warehouse_ready
import ast,traceback
session=Path(sys.argv[1]);d=None;completed=[]
def native(label):
 r=snapshot(d,label)
 with (session/'actors.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
 return r
def player(row):return next(a for a in row['actors'] if a['class']=='player')
def shadows(row):return [a for a in row['actors'] if a['class']=='npc_VFrenzyShadow']
def action(name,wait=.5):
 d.text_command("__import__('cleanup_probe').action('"+name+"')",.25)
 if d.snap()['console']['visible']:d.click_x()
 d.delay(wait);r=native(name)
 if (session/'probe.txt').exists():
  errors=[ast.literal_eval(x) for x in (session/'probe.txt').read_text().splitlines() if "'ERROR'" in x]
  assert not errors,errors
 return r
def require_beast(r):
 p=player(r);s=shadows(r);assert p['wolf']==1 and p['frenzy']>0 and len(s)==1 and s[0]['handle']==p['controller'],r
 assert p['model'] and p['model']!=player(base)['model'] and p['model']==s[0]['model'],r
def wait_end(label,limit=65):
 end=time.monotonic()+limit;rows=[]
 while time.monotonic()<end:
  r=native(label);rows.append(r)
  if not player(r)['frenzy'] and not shadows(r):return r,rows
  d.delay(.2)
 raise AssertionError('Native Frenzy did not end')
def stage(name):completed.append(name);print('PASS',name,flush=True)
def ready_frenzy():
 end=time.monotonic()+15;last=None
 while time.monotonic()<end:
  r=native('before_frenzy_readiness');reason=warehouse_ready(r)
  if reason!=last:print('Recovered readiness gate:',reason,flush=True);last=reason
  if reason is None:
   targets=[a for a in r['actors'] if a['name'] in ('fk_target_0','fk_target_1')];p=player(r)
   assert all(sum((a['origin'][i]-p['origin'][i])**2 for i in range(3))<600**2 for a in targets),'Enemies outside checked nearby range'
   return action('frenzy',1)
  d.delay(.2)
 raise AssertionError('Scene not ready; frenzyplayer NOT invoked: '+str(last))
try:
 time.sleep(25);d=Driver(session);b=d.snap();d.delay(2);assert d.snap()['client_time']>b['client_time'] and not d.snap()['console']['visible']
 d.text_command('exec cleanup_aliases.cfg',.25)
 if d.snap()['console']['visible']:d.click_x()
 action('prepare');action('warehouse_targets');base=action('record');action('cast',5);both=ready_frenzy();require_beast(both)
 d.text_command('save rc_both',.3)
 if d.snap()['console']['visible']:d.click_x()
 saved=native('saved_both');require_beast(saved)
 d.text_command('load rc_both',8);loaded=native('loaded_both');require_beast(loaded);stage('saved_both_active_load')
 action('record');(session/'runner-result.json').write_text(json.dumps({'passed':True,'completed':completed}));print('PASS saved both active load',flush=True)
except BaseException as error:
 (session/'runner-result.json').write_text(json.dumps({'passed':False,'completed':completed,'error':repr(error),'traceback':traceback.format_exc()},indent=2));print('FAIL first saved-active result preserved',flush=True);raise
