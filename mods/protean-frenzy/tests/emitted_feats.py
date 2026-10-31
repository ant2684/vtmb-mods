"""Execute the emitted feat proxy at both DLL bases and across guard failures."""
import sys,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'tools'))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import *
import json
META=json.loads((Path(sys.argv[1])/'emitted.json').read_text())
DELTA=META['server']-0x10000000
CODE=META['server_code']
BLOB=(Path(sys.argv[1])/'server-code.bin').read_bytes()


for delta in (DELTA,):
 for extra in (False,True):
  for case in ('active','null_arg','null_player','null_pc','inactive','human','missing','stale','empty','wrong_class','unrelated'):
   u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(CODE,0x1000)
   u.mem_map(0x10000000+delta,0xb00000)
   u.mem_map(0x20000000,0x40000)
   pc,combat,shadow,npc,table=0x20000000,0x20004000,0x20008000,0x20010000,0x20018000
   stack=0x20030000
   def w(a,v):u.mem_write(a,struct.pack('<I',v))
   def r(a):return struct.unpack('<I',u.mem_read(a,4))[0]
   w(combat+0xa8,0 if case=='null_pc' else pc)
   w(pc+0x146c,0 if case=='inactive' else 10)
   w(pc+0x1edc,0 if case=='human' else 1)
   w(pc+0x1db0,0xffffffff if case=='missing' else (7<<13)|1)
   w(0x10566458+delta,table);w(table+16,0 if case=='empty' else shadow)
   w(table+20,8 if case=='stale' else 7)
   w(shadow,0 if case=='wrong_class' else 0x104b2184+delta)
   w(shadow+0x9c,npc)
   arg=0 if case=='null_arg' else (combat if case=='unrelated' else npc)
   w(stack+4,arg)
   getter=0 if case=='null_player' else combat
   # Stub intentionally clobbers volatile registers, as the real call may.
   u.mem_write(0x101193b0+delta,b'\xb8'+struct.pack('<I',getter)+bytes.fromhex('b978563412ba21436587c3'))
   start=(CODE-DELTA+1536) if extra else (CODE-DELTA+1280)
   end=0x101e5b37 if extra else 0x101e56e5
   u.mem_write(start+delta,BLOB[0x600:0x800] if extra else BLOB[0x500:0x600])
   regs=(UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP)
   initial={reg:0xabc000+i for i,reg in enumerate(regs)}
   for reg,value in initial.items():u.reg_write(reg,value)
   u.reg_write(UC_X86_REG_ESP,stack)
   u.emu_start(start+delta,end+delta,count=150)
   expected=combat if case=='active' else arg
   assert r(stack+4)==expected,(delta,extra,case)
   assert u.reg_read(UC_X86_REG_ESP)==stack-(12 if extra else 24)
   for reg,value in initial.items():
    assert u.reg_read(reg)==(expected if extra and reg==UC_X86_REG_EDX else value),(case,reg)
   print('PASS feat',hex(delta),extra,case)
