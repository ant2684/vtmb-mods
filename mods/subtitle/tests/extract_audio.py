from inspect_assets import entries,content,GAME
from pathlib import Path
import hashlib,json
dest=Path(__file__).resolve().parents[2]/'assets';dest.mkdir(exist_ok=True)
found={}
def wanted(n):
 return (('newscaster/' in n.lower() or 'radio_loop_' in n.lower()) and n.lower().endswith(('.mp3','.lip','.vcd'))) or n.lower().endswith(('newscaster_main.txt','newscaster_side.txt'))
for pack in sorted((GAME/'Vampire').glob('pack*.vpk')):
 for n,start,size in entries(pack):
  if wanted(n):found[n.lower()]=(content(pack,start,size),str(pack),n)
for folder in ('Vampire','Unofficial_Patch'):
 for file in (GAME/folder/'sound').rglob('*'):
  if file.is_file():
   n=file.relative_to(GAME/folder).as_posix()
   if wanted(n):found[n.lower()]=(file.read_bytes(),str(file),n)
rows=[]
for n,(b,origin,originalName) in found.items():
 p=dest/n;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists() and p.read_bytes()!=b:raise RuntimeError('Refuse overwrite')
 p.write_bytes(b);rows.append({'path':n,'origin':origin,'hash':hashlib.sha256(b).hexdigest(),'size':len(b)})
(dest/'origins.json').write_text(json.dumps(rows,indent=2));print('Retained',len(rows),'source assets',sum(r['size'] for r in rows),'bytes')
