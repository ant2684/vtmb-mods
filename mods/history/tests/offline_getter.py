"""Execute native read accessors on an isolated copy of process pages.

All writes stay inside Unicorn. The real process handle has read permissions
only. This includes history modifiers and native min/max clamps without adding
any hooks, threads or commands to the game or the delivered plug-in.
"""
import struct
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_MEM_UNMAPPED
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX,UC_X86_REG_EAX,UC_X86_REG_EIP
class Getter:
 def __init__(self,process):
  self.p=process;self.u=Uc(UC_ARCH_X86,UC_MODE_32);self.u.mem_map(0x7e000000,0x20000);self.u.mem_write(0x7e010000,b'\xc3');self.pages={0x7e000000+i*4096 for i in range(32)};self.u.hook_add(UC_HOOK_MEM_UNMAPPED,self.page)
 def page(self,u,access,address,size,value,data):
  start=address&~4095
  for page in range(start,(address+size+4095)&~4095,4096):
   if page not in self.pages:
    raw=self.p.read(page,4096);u.mem_map(page,4096);u.mem_write(page,raw);self.pages.add(page)
  return True
 def call(self,rva,this,*args):
  sp=0x7e008000;self.u.mem_write(sp,struct.pack('<'+'I'*(len(args)+1),0x7e010000,*args));self.u.reg_write(UC_X86_REG_ESP,sp);self.u.reg_write(UC_X86_REG_ECX,this)
  self.u.emu_start(self.p.modules['vampire.dll']+rva,0x7e010000,count=100000)
  assert self.u.reg_read(UC_X86_REG_EIP)==0x7e010000,'Offline accessor did not return'
  assert self.u.reg_read(UC_X86_REG_ESP)==sp+4+len(args)*4,'Native thiscall stack mismatch'
  return struct.unpack('<i',struct.pack('<I',self.u.reg_read(UC_X86_REG_EAX)))[0]
 def effective(self,group,index):return self.call(0x010609,group,index)
 def cost(self,group,kind,index,raw):
  traits=self.p.u(self.p.u(group)+0x20)
  info=self.call(0x1f9e80,traits,kind,index)
  # Native CVStatCost_t stores New and Raise as separate subcosts. Its bool
  # selects New for a zero base rating; History can change the two differently.
  return self.call(0x1fc350,info,raw,int(raw==0))
