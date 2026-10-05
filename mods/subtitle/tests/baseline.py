import os
"""TV/radio baseline on the nominated autosave, accepted plug-in unchanged."""
from pathlib import Path
import json,sys,time,subprocess,msvcrt,atexit
from probe import Probe
base=Path(sys.argv[1]);lock=(base/'baseline.lock').open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
atexit.register(lock.close)
p=Probe(base);mode=sys.argv[2]
if len(sys.argv)>3:
 run=sys.argv[3];assert run.replace('_','').isalnum();p.session=base/'runs'/run;p.session.mkdir(parents=True,exist_ok=False)
 (p.session/'process.json').write_text(json.dumps(p.owned))
def command(s):p.command(s)
def ready():
 start=time.perf_counter()
 while time.perf_counter()-start<25:
  try:
   row=p.snap();players=[x for x in row['entities'] if x['class']=='player']
   if players and row['server_paused']==0 and not p.console():return row
  except OSError:pass
  time.sleep(.1)
 raise RuntimeError('Save did not become ready')
def capture(label,duration):
 dest=p.session/(label+'.wav')
 child=subprocess.Popen([os.environ.get('VTMB_AUDIO_HELPER', os.environ.get('VTMB_AUDIO_HELPER', str(Path(__file__).with_name('capture_audio.exe')))),str(p.owned['Id']),str(p.owned['Ticks']),str(dest),str(duration)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
 line=child.stdout.readline();assert line.startswith('READY'),line
 (p.session/(label+'.audio.json')).write_text(json.dumps({'start':line,'pid':p.owned['Id'],'capture_pid':child.pid}))
 return child
def tv(on):
 command('ent_fire newscaster SetFakeSilence '+('0' if on else '1'))
 command('ent_fire tv_screen '+('ScriptUnhide' if on else 'ScriptHide'))
 row=p.snap();news=[x for x in row['entities'] if x['class']=='npc_VNewscaster'];assert len(news)==1 and news[0]['fake_silence']==int(not on)
 if on:assert any('newscaster' in c['name'] for c in row['channels']),'No native TV audio channel; invalidate this run'

def radio_on():
 command('ent_fire Radio2 Activate')
 row=p.snap()
 assert next(x for x in row['entities'] if x['class']=='prop_radio')['fake_silence']==0,'Radio did not unmute; invalidate this run'
 assert any('radio_loop_' in c['name'] for c in row['channels']),'No native radio audio channel; invalidate this run'
def reload():
 ready()
 before=[x for x in p.entities() if x['class']=='player'][0]
 command('load autosave');row=ready();after=[x for x in row['entities'] if x['class']=='player'][0]
 assert (before['entity'],before['serial'])!=(after['entity'],after['serial']),'Fresh load not confirmed'
 return row
if mode=='immediate':
 reload();audio=capture('tv_immediate',75);p.record('tv_immediate_before');tv(True);p.record('tv_immediate_on',20);tv(False);p.record('tv_immediate_off',20);tv(True);p.record('tv_immediate_again',20);audio.wait();assert audio.returncode==0
elif mode=='wait':
 reload();audio=capture('tv_wait',55);p.record('tv_wait_off',20);tv(True);p.record('tv_wait_on',22);audio.wait();assert audio.returncode==0
elif mode=='radio_tv':
 reload();audio=capture('radio_tv',60);tv(True);p.record('radio_tv_view',20);tv(False);p.record('radio_tv_before');radio_on();p.record('radio_tv_on',22);audio.wait();assert audio.returncode==0
elif mode=='radio_wait':
 reload();audio=capture('radio_wait',55);p.record('radio_wait_off',20);radio_on();p.record('radio_wait_on',22);audio.wait();assert audio.returncode==0
elif mode=='diag':
 save=Path(r'LOCAL_GAME_ROOT_REQUIRED/Unofficial_Patch/save/broadcast_sync_diag.sav');assert not save.exists(),'Diagnostic name already exists'
 reload();audio=capture('tv_diag',65);tv(True);p.record('tv_diag_before_save',6);command('save broadcast_sync_diag');assert save.exists();p.record('tv_diag_saved',2)
 tv(False);p.record('tv_diag_off_short',8);tv(True);p.record('tv_diag_on_short',5)
 command('load broadcast_sync_diag');ready();p.record('tv_diag_reloaded',12);audio.wait();assert audio.returncode==0
elif mode=='map':
 audio=capture('tv_freshmap',32);command('map sm_apartment_1');ready();p.record('tv_freshmap_off',6);tv(True);p.record('tv_freshmap_on',15);audio.wait();assert audio.returncode==0
else:raise ValueError(mode)
