from pathlib import Path
import json,struct,sys
session=Path(sys.argv[1])
for file in sorted(session.glob('*/trace.jsonl')):
 rows=[json.loads(s) for s in file.read_text().splitlines()];print(file.parent.name,len(rows))
 last=None
 for r in rows:
  channels=[x for x in r['channels'] if 'newscaster' in x['name']]
  news=[x for x in r['entities'] if 'newscaster' in x['class'].lower()]
  scenes=[{k:s[k] for k in ('entity','scene_file') if k in s} for s in r['entities'] if s['class']=='scripted_scene']
  state=(tuple((x['name'],x['mixer'],x['caption_index']) for x in channels),tuple(n['fake_silence'] for n in news))
  if last!=state or r is rows[-1]:
   print(round(r['elapsed'],3),'server',round(r.get('server_time',-1),3),'logical',round(r.get('clock',{}).get('logicalNow',-1),3),[(c['name'],round(c.get('sample_position',0)/c.get('sample_rate',44100),3),round(c['caption_start'],3),c['caption_index']) for c in r['channels']],scenes,r['last_caption'])
   last=state
