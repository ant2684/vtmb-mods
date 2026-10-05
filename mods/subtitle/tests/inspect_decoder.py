import sys,json,struct
from pathlib import Path
from probe import Probe
import capstone
p=Probe(sys.argv[1]);row=p.snap();radio=next(c for c in row['channels'] if 'radio_loop_' in c['name']);mixer=radio['mixer'];decoder=p.p.u(mixer+0x2c);vt=p.p.u(decoder)
d=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);methods=struct.unpack('<10I',p.p.read(vt,40))
out={'modules':p.p.modules,'radio':radio,'decoder':decoder,'vtable':vt,'raw':p.p.read(decoder,512).hex(),'methods':[]}
for address in methods:
 try:
  owner=next((name,base) for name,base in sorted(p.p.modules.items(),key=lambda x:-x[1]) if base<=address)
  lines=[{'address':hex(i.address),'op':i.mnemonic+' '+i.op_str} for i in d.disasm(p.p.read(address,128),address)]
  out['methods'].append({'address':address,'owner':owner,'rva':hex(address-owner[1]),'instructions':lines})
 except OSError:pass
(p.session/'decoder-inspection.json').write_text(json.dumps(out,indent=2));print(json.dumps({'decoder':decoder,'methods':[{k:m[k] for k in ('owner','rva','instructions')} for m in out['methods'][:7]]},indent=2))
