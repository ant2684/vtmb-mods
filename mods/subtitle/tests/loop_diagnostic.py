"""Observe a real uninterrupted radio loop; no synthetic time or audio seeking."""
import sys,time,json,subprocess,msvcrt
from pathlib import Path
from probe import Probe
p=Probe(sys.argv[1]);lock=(p.session/'baseline.lock').open('a+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
dest=p.session/'loop_diagnostic';dest.mkdir(exist_ok=False);audio=None;first=None;end=None
with (dest/'trace.jsonl').open('w') as f:
 while True:
  row=p.snap();radios=[c for c in row['channels'] if 'radio_loop_' in c['name']]
  assert len(radios)==1 and radios[0]['sample_rate']==44100
  radio=radios[0];position=radio['sample_position']/44100
  if first is None:first=position;print('Start radio position',first,flush=True)
  row['elapsed']=time.perf_counter();f.write(json.dumps(row)+'\n');f.flush()
  if position>=412 and audio is None:
   wav=dest/'boundary.wav';audio=subprocess.Popen([str(Path(__file__).with_name('capture_audio.exe')),str(p.owned['Id']),str(p.owned['Ticks']),str(wav),'38'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
   ready=audio.stdout.readline();assert ready.startswith('READY'),ready;(dest/'audio.json').write_text(json.dumps({'ready':ready}));print('Recording natural loop boundary at',position,flush=True)
  if position>=430:
   print('Observed radio position',position,'caption',radio['caption_index'],row['last_caption'],flush=True)
   if audio:audio.wait();assert audio.returncode==0
   p.record('loop_boundary_after',0);break
  if position<first-5:print('Native mixer position reset at',position,flush=True);end=end or time.perf_counter()+8
  if end and time.perf_counter()>=end:
   if audio:audio.wait();assert audio.returncode==0
   break
  if time.perf_counter()-row['qpc']>2:raise RuntimeError('Trace lag')
  time.sleep(.4)
lock.close()
