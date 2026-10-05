"""Only previously unexecuted script/reload cases; keep first run unchanged."""
from driver import *
import traceback
session=Path(sys.argv[1]);d=Driver(session);completed=[]
def sample(label):
 rows=[]
 for i in range(10):rows.append(d.snap());d.delay(.1)
 with (session/'remaining-controls.jsonl').open('a') as f:
  for r in rows:f.write(json.dumps(dict(label=label,**r))+'\n')
 return rows
def probe(label):
 b=d.snap();d.delay(5);d.log('input_ready_wait',b,d.snap(),probe=label,delay_seconds=5);r=d.probe(label)
 with (session/'probes.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
 assert r['passed'],r
try:
 d.phase='script';b=d.snap();d.delay(5);d.log('command_ready_wait',b,d.snap(),delay_seconds=5)
 d.text_command('exec console_task_overlap.cfg',.25);rows=sample('script_preserved')
 assert all(r['paused']==r['server_paused']==r['pause_depth']==1 and r['menu_pause_depth']==0 and not r['console']['visible'] for r in rows)
 assert len({r['client_time'] for r in rows})==1
 deadline=time.monotonic()+60
 while d.snap()['pause_depth']:assert time.monotonic()<deadline;d.delay(.2)
 probe('script_resumed');completed.append('script');print('PASS script pause and delayed first input',flush=True)
 d.phase='reload';d.delay(5);d.text_command('load rc_console',8);probe('after_reload');completed.append('reload');print('PASS reload and delayed first input',flush=True)
 (session/'remaining-result.json').write_text(json.dumps({'passed':True,'completed':completed}))
except BaseException as error:
 (session/'remaining-result.json').write_text(json.dumps({'passed':False,'completed':completed,'error':repr(error),'traceback':traceback.format_exc()}));raise
