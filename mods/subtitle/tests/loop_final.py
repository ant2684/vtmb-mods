import os
"""Record a real radio wrap and verify native caption interval selection."""
import sys,time,json,subprocess,msvcrt
from pathlib import Path
from probe import Probe
p=Probe(sys.argv[1]);root=p.session
lock=(root/'baseline.lock').open('a+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
dest=root/'loop_final';dest.mkdir(exist_ok=False);p.session=dest
(dest/'process.json').write_text(json.dumps(p.owned));audio=None;first=None;last_picture=-1;wrapped=[]
period=18801792;rate=44100
with (dest/'trace.jsonl').open('w') as f:
 while True:
  row=p.snap();radio=next(c for c in row['channels'] if 'radio_loop_1.mp3' in c['name']);position=radio['sample_position']/rate
  assert radio['sample_rate']==rate and next(x for x in row['entities'] if x['class']=='prop_radio')['fake_silence']==0
  if first is None:
   first=position;assert first<412,'A fresh first boundary is required';print('Waiting for real loop; initial position',first,flush=True)
  phase=(int(radio['sample_position'])%period)/rate;row['radio_phase']=phase
  f.write(json.dumps(row)+'\n');f.flush()
  if position>=412 and audio is None:
   audio=subprocess.Popen([os.environ.get('VTMB_AUDIO_HELPER', os.environ.get('VTMB_AUDIO_HELPER', str(Path(__file__).with_name('capture_audio.exe')))),str(p.owned['Id']),str(p.owned['Ticks']),str(dest/'boundary.wav'),'42'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
   ready=audio.stdout.readline();assert ready.startswith('READY'),ready;(dest/'audio.json').write_text(json.dumps({'ready':ready}));print('Recording actual loop boundary at',position,flush=True)
  if 425<=position<=436 and int(position)!=last_picture:
   last_picture=int(position);p.focus()
   from PIL import ImageGrab
   ImageGrab.grab().save(dest/(str(last_picture)+'.png'))
  if position>period/rate+.5:
   interval=radio.get('caption_interval');assert interval,('Native caption interval unavailable',radio['caption_index'])
   assert interval['start']-.1<=phase<=interval['end']+.1,(phase,interval)
   assert row['last_caption'].endswith(interval['text']),row['last_caption']
   wrapped.append({'position':position,'phase':phase,'index':radio['caption_index'],'text':row['last_caption']})
  if position>=450:
   audio.wait();assert audio.returncode==0
   assert len(wrapped)>20
   (dest/'runner-result.json').write_text(json.dumps({'result':'PASS','period_samples':period,'rate':rate,'initial_position':first,'wrapped':wrapped},indent=2))
   print('PASS real loop',wrapped[0],wrapped[-1],flush=True);break
  time.sleep(.2)
lock.close()
