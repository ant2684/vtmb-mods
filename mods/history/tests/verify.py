"""Exact clean-PE regression harness. Unicorn executes the delivered x86 bytes.

Only native game calls and six Windows APIs are modeled. The game image is
read, never modified. Sparse executable sections keep signature fault tests
fast; the same signature patterns are also checked against the real DLL.
"""
import argparse, hashlib, json, re, struct, subprocess
from pathlib import Path
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *

ROOT = Path(__file__).resolve().parents[1]
SERVER_HASH = 'C546F4DE2003624D72F54D03805E0DBE1D8157231ADCC62368FF53FE6E48A76F'
EXPECTED_IMPORTS = {'FlushInstructionCache','GetCurrentProcess','GetModuleHandleA','VirtualAlloc','VirtualFree','VirtualProtect'}
S = (ROOT/'plugin/history_stat_reset_fix.c').read_text()
RV = {k:int(v,16) for k,v in re.findall(r'(\w+_RVA)\s*=\s*(0x[0-9a-f]+)',S)}
PATTERNS = [(RV[k+'_SIGNATURE_RVA'],bytes(int(x,16) for x in re.findall(r'0x([0-9a-f]{2})', re.search(r'k'+name+r'Signature\[\] = \{(.*?)\};',S,re.S).group(1)))) for k,name in [('HISTORY','History'),('NONE','None'),('CLAN_GUARD','ClanGuard')]]
PATTERNS += [(RV['GET_RAW_RVA'],bytes.fromhex('e9b6c31f00')),(RV['SET_RAW_RVA'],bytes.fromhex('e995ea1e00'))]
PBASE, VBASE, HEAP, STACK, STOP, API = 0x10000000,0x20000000,0x30000000,0x40000000,0x50000000,0x60000000
REGS = [UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX,UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EDI]

class Harness:
 def __init__(self,pe,variant='',fault=None):
  self.u=Uc(UC_ARCH_X86,UC_MODE_32); self.pe=pe;self.variant=variant;self.fault=fault or {};self.calls=[];self.api_count={};self.allocs=[];self.freed=[];self.protection={};self.native=[]
  for a,n in [(PBASE,0x10000),(VBASE,0xa00000),(HEAP,0x10000),(STACK,0x10000),(STOP,0x1000),(API,0x1000)]:self.u.mem_map(a,n)
  self.u.mem_write(PBASE,pe.get_memory_mapped_image())
  self.u.mem_write(STOP,b'\xc3');self.api={}
  for index,entry in enumerate(i for dll in pe.DIRECTORY_ENTRY_IMPORT for i in dll.imports):
   addr=API+index*16;self.api[addr]=entry.name.decode();self.w(entry.address,addr);self.u.mem_write(addr,b'\xc3')
  # Nonoverlapping executable sections, including the adjacent History/None.
  sections=sorted({r&~0xff for r,pat in PATTERNS})
  self.u.mem_write(VBASE,b'MZ');self.w(VBASE+0x3c,0x100);self.u.mem_write(VBASE+0x100,b'PE\0\0');self.u.mem_write(VBASE+0x104,struct.pack('<HH',0x14c,len(sections)));self.u.mem_write(VBASE+0x114,struct.pack('<H',224));self.u.mem_write(VBASE+0x118,struct.pack('<H',0x10b));self.w(VBASE+0x150,0xa00000)
  for i,r in enumerate(sections):
   h=VBASE+0x1f8+i*40;self.w(h+8,0x100);self.w(h+12,r);self.w(h+36,0x60000020)
  for r,pat in PATTERNS:self.u.mem_write(VBASE+r,pat)
  if variant.startswith('mismatch'):
   index=int(variant.split(':')[1]);self.u.mem_write(VBASE+PATTERNS[index][0],b'\x90')
  if variant.startswith('duplicate'):
   index=int(variant.split(':')[1]);r,pat=PATTERNS[index]
   dest=(r&~0xff)+0x10
   if dest<=r<dest+len(pat):dest=(r&~0xff)+0x80
   self.u.mem_write(VBASE+dest,pat)
  if variant=='bad_pe':self.u.mem_write(VBASE,b'XX')
  self.u.mem_write(VBASE+RV['HISTORY_RETURN_RVA'],b'\xc3');self.u.mem_write(VBASE+RV['NONE_RETURN_RVA'],b'\xc3')
  self.initial={key:bytes(self.u.mem_read(VBASE+RV[key+'_HOOK_RVA'],size)) for key,size in [('HISTORY',9),('NONE',9),('CLAN_GUARD',8)]}
  self.player=HEAP+0x8000;self.group=HEAP+0xa000;self.w(self.player+0x13bc,1);self.w(self.player+0x13c0,HEAP+0xb000);self.w(HEAP+0xb000,self.group);self.w(self.group+4,35);self.w(self.group+0x10,0)
  self.xp=8996;self.clan=2;self.history=4;self.stat=3
  self.u.hook_add(UC_HOOK_CODE,self.step)
 def r(self,a):return struct.unpack('<I',self.u.mem_read(a,4))[0]
 def w(self,a,v):self.u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def reg(self,r):return self.u.reg_read(r)
 def ret(self,n=0,value=1,clobber=False):
  sp=self.reg(UC_X86_REG_ESP);target=self.r(sp);self.u.reg_write(UC_X86_REG_ESP,sp+4+n);self.u.reg_write(UC_X86_REG_EAX,value&0xffffffff)
  if clobber:self.u.reg_write(UC_X86_REG_ECX,0xbad00001);self.u.reg_write(UC_X86_REG_EDX,0xbad00002)
  self.u.reg_write(UC_X86_REG_EIP,target)
 def step(self,u,addr,size,unused):
  if addr==STOP:u.emu_stop();return
  if addr in self.api:
   name=self.api[addr];sp=self.reg(UC_X86_REG_ESP);arg=lambda i:self.r(sp+4+i*4);self.api_count[name]=self.api_count.get(name,0)+1;count=self.api_count[name];self.calls.append((name,count));fail=count in self.fault.get(name,[])
   if name=='GetModuleHandleA':self.ret(4,VBASE);return
   if name=='GetCurrentProcess':self.ret(0,0xffffffff);return
   if name=='VirtualAlloc':
    if fail:self.ret(16,0);return
    a=HEAP;self.allocs.append(a);self.ret(16,a);return
   if name=='VirtualFree':
    self.freed.append(arg(0));self.ret(12);return
   if name=='FlushInstructionCache':self.ret(12,not fail);return
   if name=='VirtualProtect':
    a,n,prot,old=[arg(i) for i in range(4)]
    if fail:self.ret(16,0);return
    prior=self.protection.get(a,4 if a==HEAP else 0x20);self.w(old,prior);self.protection[a]=prot
    if self.variant=='race' and count==3:self.u.mem_write(a,b'\xcc')
    self.ret(16);return
   raise AssertionError(name)
  native={VBASE+RV[k]:k for k in ['GET_CLAN_RVA','SET_CLAN_RVA','GET_RAW_RVA','SET_RAW_RVA','SET_HISTORY_RVA']}
  if addr in native:
   name=native[addr];sp=self.reg(UC_X86_REG_ESP);args=[self.r(sp+4+i*4) for i in range(2)];ecx=self.reg(UC_X86_REG_ECX);self.native.append((name,ecx,args))
   if name=='GET_CLAN_RVA':assert ecx==self.player;self.ret(0,self.clan,True)
   elif name=='GET_RAW_RVA':assert ecx==self.group and args[0]==34;self.ret(4,self.xp,True)
   elif name=='SET_RAW_RVA':assert ecx==self.group and args[0]==34;self.xp=args[1];self.ret(8,0,True)
   elif name=='SET_CLAN_RVA':
    assert ecx==VBASE+RV['CLAN_MANAGER_RVA'] and args==[self.clan,self.player]
    owner=self.owner_address();assert self.r(owner)==self.player;self.w(owner,0)
    self.xp=0;self.stat=1;self.history=0xffffffff;self.ret(8,0,True)
   else:
    assert ecx==self.player;selected=args[0];self.stat-= int(self.history!=0xffffffff);self.history=selected;self.stat+=int(selected!=0xffffffff);self.ret(4,0,True)
 def run(self,addr,sp=None):
  sp=sp or STACK+0x8000;self.w(sp,STOP);self.u.reg_write(UC_X86_REG_ESP,sp);self.u.emu_start(addr,STOP,count=2000000);assert self.reg(UC_X86_REG_EIP)==STOP,'did not terminate';return self.reg(UC_X86_REG_ESP)
 def install(self):self.run(PBASE+next(e.address for e in self.pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name==b'loaded_vampire'))
 def helper(self,key):
  a=VBASE+RV[key+'_HOOK_RVA'];assert self.u.mem_read(a,1)==b'\xe9';return (a+5+self.r(a+1))&0xffffffff
 def owner_address(self):return self.r(self.helper('CLAN_GUARD')+6)
 def exercise(self,key,edi,xp):
  self.xp=xp;self.stat=3;self.history=4;self.native=[];sp=STACK+0x7000
  saved=[0xabc003,0xabc002,0xabc001]
  for i,val in enumerate(saved):self.w(sp+i*4,val)
  self.w(sp+12+0xa0,STOP);self.u.reg_write(UC_X86_REG_ESP,sp);self.u.reg_write(UC_X86_REG_ESI,self.player);self.u.reg_write(UC_X86_REG_EDI,edi&0xffffffff);self.u.reg_write(UC_X86_REG_EBP,0xabc004)
  self.u.emu_start(self.helper(key),STOP,count=100000)
  assert self.reg(UC_X86_REG_EIP)==STOP and self.reg(UC_X86_REG_ESP)==sp+12+0xa0+4
  assert [self.reg(r) for r in [UC_X86_REG_EDI,UC_X86_REG_ESI,UC_X86_REG_EBX]]==saved and self.reg(UC_X86_REG_EBP)==0xabc004
  assert self.xp==xp and self.history==(0xffffffff if key=='NONE' else edi) and self.stat==(1 if key=='NONE' else 2)
  assert self.r(self.owner_address())==0
  assert [n[0] for n in self.native]==['GET_RAW_RVA','GET_CLAN_RVA','SET_CLAN_RVA','SET_RAW_RVA','SET_HISTORY_RVA']
 def guard(self,same,owner):
  self.w(self.owner_address(),owner);self.u.reg_write(UC_X86_REG_EBX,2);self.u.reg_write(UC_X86_REG_EBP,2 if same else 3);self.u.reg_write(UC_X86_REG_ESI,self.player)
  for k in ['CLAN_RESET_BODY_RVA','CLAN_RESET_SKIP_RVA']:self.u.mem_write(VBASE+RV[k],b'\xc3')
  path=[]
  hh=self.u.hook_add(UC_HOOK_CODE,lambda u,a,n,d:path.append(a) if a in [VBASE+RV['CLAN_RESET_BODY_RVA'],VBASE+RV['CLAN_RESET_SKIP_RVA']] else None)
  self.run(self.helper('CLAN_GUARD'));self.u.hook_del(hh)
  assert path==[VBASE+RV['CLAN_RESET_BODY_RVA' if not same or owner==self.player else 'CLAN_RESET_SKIP_RVA']]
  assert self.r(self.owner_address())==(0 if same and owner==self.player else owner)

def clean(binary):
 raw=binary.read_bytes();p=pefile.PE(data=raw)
 assert p.FILE_HEADER.Machine==0x14c and p.OPTIONAL_HEADER.Magic==0x10b
 assert not p.FILE_HEADER.NumberOfSymbols and not p.FILE_HEADER.PointerToSymbolTable
 assert not p.OPTIONAL_HEADER.DATA_DIRECTORY[6].Size and not p.OPTIONAL_HEADER.DATA_DIRECTORY[9].Size
 assert {s.Name.rstrip(b'\0') for s in p.sections}=={b'.text',b'.rdata',b'.data',b'.reloc'}
 assert {e.name for e in p.DIRECTORY_ENTRY_EXPORT.symbols}=={b'loaded_vampire',b'loaded_client'}
 assert all(d.dll.upper()==b'KERNEL32.DLL' for d in p.DIRECTORY_ENTRY_IMPORT)
 assert {i.name.decode() for d in p.DIRECTORY_ENTRY_IMPORT for i in d.imports}==EXPECTED_IMPORTS
 assert p.get_overlay_data_start_offset() is None
 for debris in [b'.pdb',b'RSDS',b'.log',b'debug',b'logging',b'test_hook',b'OutputDebugString',b'CreateFile',b'WriteFile',b'.buildid',b'.debug']:
  assert debris.lower() not in raw.lower(),debris
 return p,hashlib.sha256(raw).hexdigest().upper()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('plugin');ap.add_argument('server');a=ap.parse_args();binary=Path(a.plugin).resolve();p,sha=clean(binary)
 server=Path(a.server).read_bytes();assert hashlib.sha256(server).hexdigest().upper()==SERVER_HASH
 game=pefile.PE(data=server);mapped=game.get_memory_mapped_image()
 for r,pat in PATTERNS:
  assert mapped[r:r+len(pat)]==pat
  matches=[]
  for section in game.sections:
   if section.Characteristics&0x20000000:
    data=mapped[section.VirtualAddress:section.VirtualAddress+section.Misc_VirtualSize];pos=data.find(pat)
    while pos>=0:matches.append(section.VirtualAddress+pos);pos=data.find(pat,pos+1)
  assert matches==[r],(hex(r),matches)
 cases=0
 for variant in ['bad_pe']+[f'{kind}:{index}' for kind in ['mismatch','duplicate'] for index in range(5)]:
  h=Harness(p,variant);h.install();assert not h.allocs
  for k,b in h.initial.items():assert bytes(h.u.mem_read(VBASE+RV[k+'_HOOK_RVA'],len(b)))==b
  cases+=1
 h=Harness(p);h.install();assert len(h.allocs)==1 and not h.freed
 h.install();assert len(h.allocs)==1
 before_calls=h.calls[:]
 h.run(PBASE+next(e.address for e in p.DIRECTORY_ENTRY_EXPORT.symbols if e.name==b'loaded_client'))
 # Old releases have an empty client callback; candidates may validate stock
 # client entry points. This server-only fixture must not install more hooks.
 assert h.allocs==[HEAP] and h.native==[]
 assert all(name=='GetModuleHandleA' for name,count in h.calls[len(before_calls):]);cases+=1
 # Distinct arguments cover empty History, a selected History, and automatic
 # automatic None with an unrelated EDI. No Cartesian repetition is needed.
 for key,selected,xp in [('HISTORY',0,9000),('HISTORY',4,8996),('HISTORY',1,0),('NONE',999,8996),('NONE',-2,0)]:
  h.exercise(key,selected,xp);cases+=1
 for same,owner in [(True,0),(True,h.player),(True,h.player+4),(False,0),(False,h.player)]:h.guard(same,owner);cases+=1
 # Permission consumed once; a second same-clan call must skip.
 h.guard(True,h.player);h.guard(True,0);cases+=1
 faults=[{'VirtualAlloc':[1]},{'VirtualProtect':[1]}]
 faults += [{'VirtualProtect':[i]} for i in range(2,8)]
 faults += [{'FlushInstructionCache':[i]} for i in range(1,5)]
 for fault in faults:
  h=Harness(p,fault=fault);h.install()
  for k,b in h.initial.items():assert bytes(h.u.mem_read(VBASE+RV[k+'_HOOK_RVA'],len(b)))==b,(fault,k)
  assert not h.allocs or h.freed==h.allocs
  assert all(v==0x20 for k,v in h.protection.items() if k!=HEAP),(fault,h.protection)
  cases+=1
 h=Harness(p,fault={'FlushInstructionCache':[3],'VirtualProtect':list(range(5,30))});h.install();assert h.allocs and not h.freed;assert any(h.u.mem_read(VBASE+RV[k+'_HOOK_RVA'],1)==b'\xe9' for k in h.initial);cases+=1
 h=Harness(p,'race');h.install();assert h.u.mem_read(VBASE+RV['CLAN_GUARD_HOOK_RVA'],1)==b'\xcc' and not h.freed;cases+=1
 subprocess.run([str(ROOT/'build/load_clean.exe'),str(binary),'loaded_vampire'],check=True)
 report={'result':'PASS','hash':sha,'cases':cases,'server_hash':SERVER_HASH,'clean_pe':True,'abi':'x86 thiscall/cdecl stack and nonvolatile registers','rollback':'fault injection; surviving helpers retained'}
 (ROOT/'build/technical-verification.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report))
if __name__=='__main__':main()
