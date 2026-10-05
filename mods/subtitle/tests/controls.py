import os
"""Exact-candidate radio/pause/load/map scenarios with owned process audio."""
import sys,time,json,subprocess,msvcrt,re
from pathlib import Path
from probe import Probe
p=Probe(sys.argv[1]);root=p.session;lock=(root/'baseline.lock').open('a+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
p.session=root/'runs'/sys.argv[2];p.session.mkdir(parents=True,exist_ok=False);(p.session/'process.json').write_text(json.dumps(p.owned))
def radio(row=None):
 row=row or p.snap();r=[c for c in row['channels'] if 'radio_loop_' in c['name']];assert len(r)==1;return r[0]
def ready(previous=None):
 start=time.perf_counter()
 while time.perf_counter()-start<25:
  try:
   row=p.snap();player=next(x for x in row['entities'] if x['class']=='player');identity=(player['entity'],player['serial'])
   if (previous is None or identity!=previous) and not row['server_paused'] and not p.console():return row
  except (OSError,StopIteration):pass
  time.sleep(.1)
 raise RuntimeError('Fresh load/map not ready')
def load(cmd='load autosave'):
 player=next(x for x in p.entities() if x['class']=='player');p.command(cmd);return ready((player['entity'],player['serial']))
def tv(on):
 p.command('ent_fire newscaster SetFakeSilence '+('0' if on else '1'));p.command('ent_fire tv_screen '+('ScriptUnhide' if on else 'ScriptHide'))
 assert next(x for x in p.entities() if x['class']=='npc_VNewscaster')['fake_silence']==int(not on)
def r(on):
 p.command('ent_fire Radio2 '+('Activate' if on else 'Deactivate'))
 assert next(x for x in p.entities() if x['class']=='prop_radio')['fake_silence']==int(not on)
def record(label,seconds):p.record(label,seconds)
def capture(label,duration):
 child=subprocess.Popen([os.environ.get('VTMB_AUDIO_HELPER', os.environ.get('VTMB_AUDIO_HELPER', str(Path(__file__).with_name('capture_audio.exe')))),str(p.owned['Id']),str(p.owned['Ticks']),str(p.session/(label+'.wav')),str(duration)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
 line=child.stdout.readline();assert line.startswith('READY'),line;(p.session/(label+'.audio.json')).write_text(json.dumps({'ready':line}));return child
load();audio=capture('controls',165)
r(True);record('first_on',6)
r(False);record('off_20',20);r(True);record('repeat_on',6)
cfg=Path(r'LOCAL_GAME_ROOT_REQUIRED/Unofficial_Patch/cfg/config.cfg').read_text(encoding='cp1252')
assert not re.search(r'bind "F11"',cfg,re.I),'Personal F11 binding exists'
p.command('bind F11 pause');p.key(0x57);time.sleep(.5);before=p.snap();assert before['server_paused']==before['paused']==1
record('ordinary_pause',5);after=p.snap();assert abs(after['server_time']-before['server_time'])<.02
assert abs(radio(after)['sample_position']-radio(before)['sample_position'])<2048
assert radio(after)['caption_index']==radio(before)['caption_index']
p.key(0x57);time.sleep(.5);assert p.snap()['server_paused']==0;p.command('unbind F11');record('pause_resumed',6)
r(False);tv(True);record('radio_to_tv',8);tv(False);r(True);record('tv_back_to_radio',8)
save=Path(r'LOCAL_GAME_ROOT_REQUIRED/Unofficial_Patch/save/broadcast_sync_diag.sav');assert not save.exists()
p.command('save broadcast_sync_diag');assert save.exists();record('radio_saved',2)
load('load broadcast_sync_diag');record('radio_reloaded_on',10)
r(False);record('radio_reloaded_off',5);r(True);record('radio_reloaded_repeat',6)
load('map sm_apartment_1');record('changed_map',4)
load();r(True);record('returned_autosave',6)
audio.wait();assert audio.returncode==0
(p.session/'runner-result.json').write_text(json.dumps({'result':'PASS','pid':p.owned['Id'],'scope':'first/repeat/off20/ordinary pause/both TV transitions/on-save reload/off after reload/map return'}));lock.close();print('PASS control phases',flush=True)
