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
from PIL import ImageGrab,ImageStat
def capture(label):
 action('record');r=native(label)
 api=[ast.literal_eval(line) for line in (session/'probe.txt').read_text().splitlines()]
 recorded=[row for row in api if row[1]=='record'];assert recorded
 r['native_cvars']={k:recorded[-1][2][k] for k in ('mat_fullbright','feedvision')}
 d.focus();im=ImageGrab.grab();im.save(session/(label+'.png'));w,h=im.size
 crop=im.crop((w//3,h//3,2*w//3,2*h//3));r['brightness']=sum(ImageStat.Stat(crop).mean[:3])/3
 with (session/'filter.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
 print(label,'filter',r.get('filter'),'brightness',r['brightness'],flush=True)
 return r
try:
 time.sleep(25);d=Driver(session);b=d.snap();d.delay(2);assert d.snap()['client_time']>b['client_time'] and not d.snap()['console']['visible']
 d.text_command('exec cleanup_aliases.cfg',.25)
 if d.snap()['console']['visible']:d.click_x()
 action('prepare');action('rank4');action('cast',2)
 d.text_command('save rc_filter',.3)
 if d.snap()['console']['visible']:d.click_x()
 d.delay(1);first=capture('protean_filter_initial');assert player(first)['protean']==4 and first['filter']['kind']==1 and first['native_cvars']['mat_fullbright']==1
 for i in range(2):
  d.text_command('load rc_filter',8);r=capture('protean_filter_reload_'+str(i));assert player(r)['protean']==4 and r['native_cvars']['mat_fullbright']==1 and r['filter']['kind']==1 and abs(r['brightness']-first['brightness'])<5
 action('end',1);off=capture('protean_filter_off');assert not player(off)['protean'] and off['native_cvars']['mat_fullbright']==0;stage('protean_filter_reload_and_off')
 action('redvision',1);red=capture('redvision_initial');assert red['filter']['kind']!=1 and red['native_cvars']['feedvision']==10
 d.text_command('save rc_redvision',.3)
 if d.snap()['console']['visible']:d.click_x()
 d.text_command('load rc_redvision',8);r=capture('redvision_reload');assert r['filter']['kind']==red['filter']['kind'] and r['native_cvars']['feedvision']==10 and abs(r['brightness']-red['brightness'])<5
 action('redvision_off');stage('redvision_separate_branch')
 (session/'runner-result.json').write_text(json.dumps({'passed':True,'completed':completed}));print('PASS filters',flush=True)
except BaseException as error:
 (session/'runner-result.json').write_text(json.dumps({'passed':False,'completed':completed,'error':repr(error),'traceback':traceback.format_exc()},indent=2));print('FAIL first result preserved',flush=True);raise
