"""Read Troika pack directories and the actual BSP entity lump, no game edits."""
import struct,sys,re
from pathlib import Path
GAME=Path(r'LOCAL_GAME_ROOT_REQUIRED')
def entries(pack):
 with pack.open('rb') as f:
  f.seek(-9,2);count,offset,flag=struct.unpack('<IIB',f.read(9));f.seek(offset)
  for _ in range(count):
   n=struct.unpack('<I',f.read(4))[0];name=f.read(n).decode('latin1').rstrip('\0');start,size=struct.unpack('<II',f.read(8));yield name,start,size
def content(pack,start,size):
 with pack.open('rb') as f:f.seek(start);return f.read(size)
if __name__=='__main__':
 for path in (GAME/'Unofficial_Patch/maps').glob('sm_apartment*.bsp'):
  b=path.read_bytes();off,n=struct.unpack_from('<II',b,8);entities=b[off:off+n].decode('latin1');print(path.name)
  for block in re.findall(r'\{[^}]*\}',entities):
   if any(s in block.lower() for s in ('newscaster','radio','tv_','television')):print(block)
 for pack in sorted(GAME.rglob('pack*.vpk')):
  for name,start,size in entries(pack):
   if name.lower().endswith('.bsp') and any(x in name.lower() for x in ('haven','apartment')):
    b=content(pack,start,size);off,n=struct.unpack_from('<II',b,8);entities=b[off:off+n].decode('latin1')
    print(pack.name,name)
    for block in re.findall(r'\{[^}]*\}',entities):
     if any(s in block.lower() for s in ('newscaster','radio','tv_','television')):print(block)
 for pack in sorted(GAME.rglob('pack*.vpk')):
  names=[n for n,_,_ in entries(pack) if n.lower().endswith('.bsp') and '/sm_' in n.lower()]
  if names:print(pack.name,names)
