"""Execute code captured from the final Windows-loaded DLL, not a recipe."""
import json,struct,sys
from pathlib import Path
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
root=Path(sys.argv[1]);m=json.loads((root/'emitted.json').read_text())
def machine(which):
 u=Uc(UC_ARCH_X86,UC_MODE_32);base=m[which];code=m[which+'_code']
 u.mem_map(base,0xb00000);u.mem_map(code,0x1000);u.mem_map(0x60000000,0x20000)
 u.mem_write(code,(root/(which+'-code.bin')).read_bytes());u.reg_write(UC_X86_REG_ESP,0x60018000)
 return u,base,code
for frenzy,wolf in [(0,0),(0,1),(1,0),(1,1)]:
 u,b,c=machine('server');p=0x60000000;u.mem_write(p+0x146c,struct.pack('<I',frenzy));u.mem_write(p+0x1edc,bytes([wolf]));u.reg_write(UC_X86_REG_EBP,p)
 u.emu_start(c,b+0x16c55e,count=20)
 assert u.reg_read(UC_X86_REG_EAX)&255==(0 if frenzy else wolf)
 assert u.reg_read(UC_X86_REG_ESP)==0x60018000
 print('PASS actual sync',frenzy,wolf)
for requested,stored,enabled,kind,expect in [(0,1,0,1,0x19dab7),(2,1,0,1,0x19da81),(1,1,1,1,0x19da81),(1,1,0,1,0x19dacd),(1,1,0,2,0x19da81)]:
 u,b,c=machine('client');obj,filter,vt=0x60000000,0x60001000,0x60002000;stub=0x60003000
 def w(a,v):u.mem_write(a,struct.pack('<I',v))
 w(b+0x61992c,stored);w(b+0x619928,obj);w(obj+4,filter);w(filter,vt);w(filter+0x2c,kind);w(vt+4,stub)
 u.mem_write(stub,b'\xb8'+struct.pack('<I',enabled)+b'\xc3');u.reg_write(UC_X86_REG_EDI,requested)
 exits=[]
 def stop(uc,at,size,data):
  if at in [b+x for x in (0x19dab7,0x19da81,0x19dacd)]:exits.append(at);uc.emu_stop()
 u.hook_add(UC_HOOK_CODE,stop);u.emu_start(c,0,count=40)
 assert exits==[b+expect] and u.reg_read(UC_X86_REG_ESP)==0x60018000
 print('PASS actual filter branch',requested,stored,enabled,kind)
