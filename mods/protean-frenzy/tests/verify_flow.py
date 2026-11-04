"""Run the exact unified buffer bridge and original native continuation code."""
import os,json,sys,struct,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
CONFIG=json.loads(Path(os.environ['PFI_CONFIG']).read_text())
sys.path[:0]=[CONFIG['native_dependencies'],str(HERE.parent/'_support')]
from mdl import seqs,f
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
OUT=Path(CONFIG['output']);GAME=Path(CONFIG['game'])
PLUGIN=OUT/'Payload/Bin/loader/protean-frenzy-improved.vtm'
native=GAME/'Vampire/dlls/vampire.dll'
assert hashlib.sha256(native.read_bytes()).hexdigest()=='c546f4de2003624d72f54d03805e0dbe1d8157231adcc62368ff53fe6e48a76f'
mem=pefile.PE(str(native)).get_memory_mapped_image()
MOD,IMAGE,NAMES,TRAMP=0x30000000,0x21000000,0x22000000,0x32000000
WEAPON,PLAYER,COMP,PVT,WVT=0x20000000,0x20010000,0x20020000,0x20030000,0x20040000
SP,STOP,dllbase=0x70018000,0x7f001000,0x10000000
def writeword(u,a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
def word(u,a):return struct.unpack('<I',u.mem_read(a,4))[0]
def ret(u,value,cleanup=0):
    sp=u.reg_read(UC_X86_REG_ESP);pc=word(u,sp)
    u.reg_write(UC_X86_REG_EAX,value&0xffffffff);u.reg_write(UC_X86_REG_ESP,sp+4+cleanup);u.reg_write(UC_X86_REG_EIP,pc)
def machine():
    u=Uc(UC_ARCH_X86,UC_MODE_32)
    for start,size in [(dllbase,0xb00000),(0x20000000,0x100000),(0x70000000,0x20000),(0x7f000000,0x4000)]:u.mem_map(start,size)
    u.mem_write(dllbase,mem);return u
class Harness:
    def __init__(self,bad_signature=False):
        self.u=u=machine();self.assigned=[];self.lookups=[];self.reset_calls=0;self.allocations=0
        # Model-pool ownership is qualified by exact NPC/configuration fixtures.
        u.mem_write(dllbase+0x8dac0,b'\xcc')
        self.pe=pefile.PE(data=PLUGIN.read_bytes());self.pe.relocate_image(MOD)
        u.mem_map(MOD,(self.pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(MOD,self.pe.get_memory_mapped_image())
        u.mem_map(IMAGE,(len(MODEL)+4095)&~4095);u.mem_write(IMAGE,MODEL)
        u.mem_map(NAMES,0x10000);u.mem_map(TRAMP,0x1000)
        self.names=list(seqs(MODEL))+['fists_attack_med','fists_idle','howl']
        self.indices={n.lower():100+j for j,n in enumerate(self.names)};self.ptrs={}
        p=NAMES
        for n in self.names:
            self.ptrs[self.indices[n.lower()]]=p;u.mem_write(p,n.encode()+b'\0');p+=len(n)+1
        writeword(u,WEAPON,WVT);writeword(u,PLAYER,PVT);writeword(u,COMP+0xa8,PLAYER)
        writeword(u,dllbase+0x9f3680,0x20050000);writeword(u,0x20050000,1)
        writeword(u,PLAYER+0x1c5c,-1);writeword(u,PLAYER+0x2088,1)
        for vt,slot,target in ((PVT,0x668,0x7f002000),(PVT,0x5e0,0x7f002010),(PVT,0x4dc,0x7f002020),(WVT,0x5a4,0x7f002010)):
            writeword(u,vt+slot,target)
        self.imports={}
        for d in self.pe.DIRECTORY_ENTRY_IMPORT:
            for entry in d.imports:
                name=entry.name.decode();pc=0x7f003000+16*len(self.imports);self.imports[pc]=name
                writeword(u,entry.address,pc)
        if bad_signature:u.mem_write(dllbase+0x254250,b'\x90')
        u.hook_add(UC_HOOK_CODE,self.hook)
        export=next(s for s in self.pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name==b'loaded_vampire')
        self.call(MOD+export.address)
        self.installed=bytes(u.mem_read(dllbase+0x254250,1))==b'\xe9'

    def text(self,p):
        data=bytearray()
        for _ in range(512):
            b=bytes(self.u.mem_read(p,1));p+=1
            if b==b'\0':return data.decode('ascii')
            data.extend(b)
        raise AssertionError('Unterminated native text')
    def call(self,pc):
        u=self.u;writeword(u,SP,STOP);u.reg_write(UC_X86_REG_ESP,SP)
        u.emu_start(pc,STOP,count=300000)
        assert u.reg_read(UC_X86_REG_EIP)==STOP
        assert u.reg_read(UC_X86_REG_ESP)==SP+4

    def hook(self,u,pc,size,context):
        esp=u.reg_read(UC_X86_REG_ESP)
        if pc in self.imports:
            name=self.imports[pc]
            if name=='GetModuleFileNameA':
                data=b'C:\\Fixture\\Vampire.exe\0';u.mem_write(word(u,esp+8),data);ret(u,len(data)-1,12)
            elif name=='GetPrivateProfileStringA':
                key=self.text(word(u,esp+8));value=b'1\0' if key=='ClawsComboBuffer' else b'0\0'
                u.mem_write(word(u,esp+16),value);ret(u,1,24)
            elif name=='GetSystemInfo':writeword(u,word(u,esp+4)+4,4096);ret(u,0,4)
            elif name=='VirtualQuery':
                p=word(u,esp+8);writeword(u,p+16,0x1000);writeword(u,p+20,0x20);ret(u,28,12)
            elif name=='strrchr':
                p=word(u,esp+4);j=self.text(p).rfind(chr(word(u,esp+8)&255));ret(u,p+j if j>=0 else 0)
            elif name in ('memcpy','memset','strcpy'):
                target,value=word(u,esp+4),word(u,esp+8)
                if name=='strcpy':data=self.text(value).encode()+b'\0'
                else:
                    n=word(u,esp+12);data=bytes([value&255])*n if name=='memset' else bytes(u.mem_read(value,n))
                u.mem_write(target,data);ret(u,target)
            elif name in ('strcmp','memcmp'):
                a,b=word(u,esp+4),word(u,esp+8)
                if name=='strcmp':x,y=self.text(a),self.text(b)
                else:n=word(u,esp+12);x,y=bytes(u.mem_read(a,n)),bytes(u.mem_read(b,n))
                ret(u,(x>y)-(x<y))
            elif name=='GetModuleHandleA':assert self.text(word(u,esp+4))=='vampire.dll';ret(u,dllbase,4)
            elif name=='VirtualAlloc':self.allocations+=1;ret(u,TRAMP,16)
            elif name=='VirtualProtect':writeword(u,word(u,esp+16),0x20);ret(u,1,16)
            elif name=='VirtualFree':ret(u,1,12)
            elif name=='GetCurrentProcess':ret(u,0xffffffff)
            elif name=='FlushInstructionCache':ret(u,1,12)
            elif name=='strlen':ret(u,len(self.text(word(u,esp+4))))
            elif name=='strncmp':
                a,b,n=(word(u,esp+k) for k in (4,8,12));x,y=bytes(u.mem_read(a,n)),bytes(u.mem_read(b,n));ret(u,(x>y)-(x<y))
            else:raise AssertionError(('unexpected import',name))
        elif pc==dllbase+0x14fab:ret(u,COMP)
        elif pc in (dllbase+0xb4f6,dllbase+0x8d990):
            idx=word(u,esp+4);n=self.names[idx-100];ret(u,IMAGE+seqs(MODEL)[n],4)
        elif pc==dllbase+0x8fe80:ret(u,self.ptrs[word(u,esp+4)],4)
        elif pc==dllbase+0xe057:
            n=self.text(word(u,esp+4));self.lookups.append(n);ret(u,self.indices[n.lower()],4)
        elif pc==0x7f002000:ret(u,0)
        elif pc==0x7f002010:ret(u,word(u,esp+4),4)
        elif pc==0x7f002020:
            row=[word(u,esp+k) for k in (4,8,12)];self.assigned.append(row)
            writeword(u,PLAYER+0x6f0,row[2]);ret(u,0,12)
        elif pc==dllbase+0x5bdc:ret(u,0)
        elif pc==dllbase+0x117b1:self.reset_calls+=1;ret(u,0)

    def stage(self,name):writeword(self.u,PLAYER+0x6f0,self.indices[name.lower()])
    def tick(self,phase,pressed=0,name=None):
        u=self.u
        if name:self.stage(name)
        u.mem_write(PLAYER+0x6f8,struct.pack('<f',phase));writeword(u,PLAYER+0x208c,pressed)
        u.reg_write(UC_X86_REG_ECX,WEAPON);before=len(self.assigned);self.call(dllbase+0x254250)
        assert word(u,PLAYER+0x208c)==pressed,'Injected bit must not survive the function'
        return len(self.assigned)>before

    def command(self,current,target):
        u=self.u;self.stage(current);before=self.indices[current.lower()];targetid=self.indices[target.lower()]
        resets=self.reset_calls;writeword(u,0x20050000,1)
        u.mem_write(PLAYER+0x6f8,struct.pack('<f',.42))
        # Execute the patched original command's successful lookup branch,
        # including its original cycle reset and epilogue. The caller owns
        # saved EDI/ESI and a four-byte local, as in CC_Player_Sequence.
        u.mem_write(SP,struct.pack('<4I',0x12345678,0x23456789,0x3456789a,STOP))
        u.reg_write(UC_X86_REG_ESP,SP);u.reg_write(UC_X86_REG_ESI,PLAYER)
        u.reg_write(UC_X86_REG_EAX,targetid);u.reg_write(UC_X86_REG_ECX,PLAYER)
        u.emu_start(dllbase+0x3485fd,STOP,count=100000)
        assert u.reg_read(UC_X86_REG_EIP)==STOP and u.reg_read(UC_X86_REG_ESP)==SP+16
        accepted=self.reset_calls==resets+1
        if accepted:assert word(u,PLAYER+0x6f0)==targetid
        if not accepted:
            assert word(u,PLAYER+0x6f0)==before
            assert abs(struct.unpack('<f',u.mem_read(PLAYER+0x6f8,4))[0]-.42)<1e-6
        return accepted

cases=commands=0
for sex in ['male','female']:
    MODEL=(OUT/'Components/ClawsModels/Unofficial_Patch/models/character/shared'/sex/'claws.mdl').read_bytes()
    h=Harness();assert h.installed and h.allocations==1
    assert bytes(h.u.mem_read(dllbase+0x3485fd,6))==mem[0x3485fd:0x348603]
    for current in ['claws_chain_still_pi4_1_med_right','claws_guard_block_natural','Claws_air']:
        for target in ['Claws_alert_front_into','Claws_alert_front_outof','howl']:
            assert h.command(current,target);commands+=1
    bad=Harness(True);assert not bad.installed and bad.allocations==0
    stages=[]
    for line in (HERE.parent/'native/combo_windows.inc').read_text().splitlines():
        name=line.split('"')[1];duration=float(line.split(',')[1].strip('f},'));stages.append((name,duration))
    assert len(stages)==14
    for name,duration in stages:
        q=seqs(MODEL)[name];start,end=f(MODEL,q+752),f(MODEL,q+756)
        for rate in [1.,2.]:
            def fresh():
                hh=Harness();hh.u.mem_write(PLAYER+0x6f4,struct.pack('<f',rate));hh.tick(.01,0,name);return hh
            lead=.15*rate/duration
            hh=fresh();assert not hh.tick(start-.149*rate/duration,1);assert hh.tick(start+.001)
            hh=fresh();assert not hh.tick(start-.151*rate/duration,1);assert not hh.tick(start+.001)
            hh=fresh();assert hh.tick(start+.001,1)
            hh=fresh();hh.tick(.02,1);assert not hh.tick(start+.001)
            hh=fresh();hh.tick(start-lead*.9,1);hh.tick(.2,0,'claws_idle');assert not hh.tick(start+.001,0,name)
            hh=fresh();hh.tick(start-lead*.9,1);assert not hh.tick(end+.01);assert not hh.tick(start+.001)
            cases+=6
print('PASS',cases,'exact buffer cases;',commands,'native idle-command controls; both model resources')
(OUT/'flow-native.json').write_text(json.dumps(dict(passed=True,buffer_cases=cases,native_idle_controls=commands,plugin_sha256=hashlib.sha256(PLUGIN.read_bytes()).hexdigest()),indent=2)+'\n')
