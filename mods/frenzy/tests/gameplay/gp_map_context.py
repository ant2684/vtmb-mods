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
 d.text_command("__import__('cleanup_probe').action('"+name+"')",8 if name=='gp_map' else .25)
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
import math
mode=sys.argv[2]
def wolf(row):return next(a for a in row['actors'] if a['name']=='werewolf')
def gap(a,b):
 return [max(0,a['origin'][i]+a['mins'][i]-(b['origin'][i]+b['maxs'][i]),b['origin'][i]+b['mins'][i]-(a['origin'][i]+a['maxs'][i])) for i in range(3)]
def gate():
 end=time.monotonic()+15;reason='unknown'
 while time.monotonic()<end:
  r=native('gp_before_frenzy');w=wolf(r);p=player(r)
  reason=None
  if w['vtable']!=0x4cf4d4 or w['life'] or not w['alive'] or not w['targetable'] or w['health']<=0:reason='native live Werewolf identity/readiness'
  elif not 1<=w['solid']<=6 or w['effects']&0x20 or w['spawn_flags']&0x8000 or w['think_disabled']:reason='Werewolf collision/AI eligibility'
  # Werewolf uses its boss movement path; generic NPC enemy_handle is not
  # acquisition evidence. Require actual native approach below instead.
  elif r['paused'] or r['engine_paused'] or r['ai_global_flags']:reason='paused/disabled AI'
  elif shadows(r) or p['frenzy'] or p['life']:reason='player not ready'
  elif math.dist(w['origin'],p['origin'])>600:reason='Werewolf too far'
  if reason is None:return r
  d.delay(.2)
 raise AssertionError('GP unready; no frenzyplayer: '+str(reason))
def activate(warform=False):
 action('prepare');initial=native('context_prepare')
 if wolf(initial)['effects']&0x20:action('gp_start_encounter',.5)
 if warform:action('cast',5)
 action('gp_approach',.2);gate();r=action('frenzy',.2);assert player(r)['frenzy'] and len(shadows(r))==1;return r
try:
 time.sleep(25);d=Driver(session);b=d.snap();d.delay(2);assert d.snap()['client_time']>b['client_time'] and not d.snap()['console']['visible']
 d.text_command('exec cleanup_aliases.cfg',.25)
 if d.snap()['console']['visible']:d.click_x()
 base=native('gp_loaded');active=activate(False);native('before_active_map');r=action('gp_map',8);assert not any(a['name']=='werewolf' for a in r['actors']) and not shadows(r) and not player(r)['frenzy'];stage('gp_active_map_clear')
 (session/'runner-result.json').write_text(json.dumps({'passed':True,'completed':completed}));print('PASS GP active map context',flush=True)
except BaseException as error:
 (session/'runner-result.json').write_text(json.dumps({'passed':False,'completed':completed,'error':repr(error),'traceback':traceback.format_exc()},indent=2));print('FAIL first map result preserved',flush=True);raise
