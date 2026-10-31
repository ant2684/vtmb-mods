"""Execute the clean bridge and original paired-scene argument construction."""
import json,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
CONFIG=json.loads(Path(os.environ['PFI_CONFIG']).read_text())
def path(key):return Path(CONFIG[key])
sys.path[:0]=[CONFIG['native_dependencies'],str(HERE.parent/'_support')]
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
import sys
import pefile
raw=(path('game')/'Vampire/dlls/vampire.dll').read_bytes()
assert __import__('hashlib').sha256(raw).hexdigest()=='c546f4de2003624d72f54d03805e0dbe1d8157231adcc62368ff53fe6e48a76f'
pe=pefile.PE(data=raw);mem=pe.get_memory_mapped_image();base=pe.OPTIONAL_HEADER.ImageBase
def machine():
 u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(base,0xb00000);u.mem_write(base,mem)
 u.mem_map(0x20000000,0x100000);u.mem_map(0x70000000,0x20000);u.mem_map(0x7f000000,0x4000)
 return u
def put(u,a,v):u.mem_write(a,struct.pack('<I',v&0xffffffff))
def word(u,a):return struct.unpack('<I',u.mem_read(a,4))[0]
def ret(u,value,cleanup=0):
 sp=u.reg_read(UC_X86_REG_ESP);pc=word(u,sp)
 u.reg_write(UC_X86_REG_EAX,value&0xffffffff);u.reg_write(UC_X86_REG_ESP,sp+4+cleanup);u.reg_write(UC_X86_REG_EIP,pc)
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
import pefile,struct,json,hashlib,math
from pathlib import Path
MOD,PLAYER,OWNER,PARTNER,SOURCE,MOVE,DESC=0x30000000,0x20000000,0x20010000,0x20020000,0x20030000,0x20040000,0x20050000
TABLE,WEAPON,CLASS,WCLASS=0x20070000,0x20080000,0x20090000,0x20091000
SP,STOP=0x70018000,0x7f001000
HERE=Path(__file__).resolve().parent
PLUGIN=path('output')/'Payload/Bin/loader/protean-frenzy-improved.vtm'
class Harness:
    def __init__(self,bad=False):
        self.u=u=machine();self.desc=DESC;self.bone=0;self.root=(45,60,34)
        pe=pefile.PE(data=PLUGIN.read_bytes());pe.relocate_image(MOD)
        u.mem_map(MOD,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(MOD,pe.get_memory_mapped_image())
        imports={}
        for lib in pe.DIRECTORY_ENTRY_IMPORT:
            for e in lib.imports:
                pc=0x7f003000+16*len(imports);imports[pc]=e.name.decode();put(u,e.address,pc)
        def text(p):return bytes(u.mem_read(p,256)).split(b'\0')[0]
        def hook(u,pc,size,unused):
            esp=u.reg_read(UC_X86_REG_ESP)
            if pc==base+0x8d990:ret(u,self.desc,4)
            elif pc==base+0x92550:ret(u,self.bone,4)
            elif pc==base+0x926e0:
                u.mem_write(word(u,esp+8),struct.pack('<3f',*self.root));u.mem_write(word(u,esp+12),b'\0'*12);ret(u,0,12)
            elif pc in imports:
                name=imports[pc]
                if name=='GetModuleFileNameA':
                    data=b'C:\\Fixture\\Vampire.exe\0';u.mem_write(word(u,esp+8),data);ret(u,len(data)-1,12)
                elif name=='GetPrivateProfileStringA':
                    key=text(word(u,esp+8));value=b'1\0' if key==b'ClawsStealthPosition' else b'0\0'
                    u.mem_write(word(u,esp+16),value);ret(u,1,24)
                elif name=='GetSystemInfo':put(u,word(u,esp+4)+4,4096);ret(u,0,4)
                elif name=='VirtualQuery':
                    p=word(u,esp+8);put(u,p+16,0x1000);put(u,p+20,0x20);ret(u,28,12)
                elif name=='GetModuleHandleA':ret(u,base,4)
                elif name=='VirtualProtect':put(u,word(u,esp+16),0x20);ret(u,1,16)
                elif name=='GetCurrentProcess':ret(u,0xffffffff)
                elif name=='FlushInstructionCache':ret(u,1,12)
                elif name=='strrchr':
                    a=word(u,esp+4);index=text(a).rfind(bytes([word(u,esp+8)&255]));ret(u,a+index if index>=0 else 0)
                elif name in ('memcpy','memset','strcpy'):
                    target,value=word(u,esp+4),word(u,esp+8)
                    if name=='strcpy':data=text(value)+b'\0'
                    else:
                        length=word(u,esp+12);data=bytes([value&255])*length if name=='memset' else bytes(u.mem_read(value,length))
                    u.mem_write(target,data);ret(u,target)
                elif name in ('strlen','strcmp','strncmp','memcmp'):
                    a=word(u,esp+4)
                    if name=='strlen':ret(u,len(text(a)));return
                    b=word(u,esp+8)
                    if name in ('strncmp','memcmp'):
                        n=word(u,esp+12);x=bytes(u.mem_read(a,n));y=bytes(u.mem_read(b,n))
                        if name=='strncmp':x=x.split(b'\0')[0];y=y.split(b'\0')[0]
                    else:x,y=text(a),text(b)
                    ret(u,(x>y)-(x<y))
                else:raise AssertionError(name)
        u.hook_add(UC_HOOK_CODE,hook)
        if bad is True:u.mem_write(base+0x329298,b'\x90')
        elif isinstance(bad,int) and not isinstance(bad,bool):u.mem_write(base+bad,b'\x90')
        elif bad=='exit':u.mem_write(base+0x329c24,b'\x90')
        export=next(e for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name==b'loaded_vampire')
        put(u,SP,STOP);u.reg_write(UC_X86_REG_ESP,SP);u.emu_start(MOD+export.address,STOP,count=100000)
        assert u.reg_read(UC_X86_REG_EIP)==STOP and u.reg_read(UC_X86_REG_ESP)==SP+4
        self.installed=bytes(u.mem_read(base+0x329298,1))==b'\xe9'
        assert (bytes(u.mem_read(base+0x329c24,1))==b'\xe9')==self.installed
        put(u,PLAYER+0xa8,OWNER);put(u,OWNER+0x1da4,17);put(u,PLAYER+0x1538,100)
        self.setup()
    def setup(self,weapon='item_w_claws',role=0,kind=3,sequence=810,cycle=.1,actor_class='player',activity='ACT_SNEAKATTACK_SUCCESS_ATTACKER_TALLVICTIM_CLAWS'):
        u=self.u;put(u,PLAYER+0x153c,role);put(u,PLAYER+0x1540,kind);put(u,PLAYER+0x6f0,sequence)
        u.mem_write(PLAYER+0x6f8,struct.pack('<f',cycle))
        put(u,PLAYER+0x11c,CLASS);u.mem_write(CLASS,actor_class.encode()+b'\0')
        put(u,PLAYER+0x19a4,100|(3<<13));put(u,base+0x566458,TABLE)
        put(u,TABLE+100*12+4,WEAPON);put(u,TABLE+100*12+8,3)
        put(u,WEAPON+0x11c,WCLASS);u.mem_write(WCLASS,weapon.encode()+b'\0')
        put(u,DESC+4,800);u.mem_write(DESC+800,activity.encode()+b'\0')
    def frame(self,anchor,partner,cycle=.1):
        u=self.u;u.mem_write(SP,b'\0'*256)
        put(u,SP+0x1c,1);u.mem_write(SP+0x28,struct.pack('<f',.8501992));put(u,PARTNER,0x20060000)
        u.mem_write(SP+0x2c,struct.pack('<f',partner[2]));u.mem_write(SP+0x3c,struct.pack('<3f',*partner))
        u.mem_write(SP+0x5c,struct.pack('<3f',*anchor));u.mem_write(PLAYER+0x6f8,struct.pack('<f',cycle))
        # Absolute origin may be dirty after native placement. The bridge must
        # use the calculated anchor, not read stale entity coordinate caches.
        u.mem_write(PLAYER+0x404,struct.pack('<3f',1234,5678,9))
        player_before=bytes(u.mem_read(PLAYER,0x2100));victim_before=bytes(u.mem_read(PARTNER,0x2100))
        movement_before=bytes(u.mem_read(base+0x186589,0x1d))
        regs={UC_X86_REG_EDI:PLAYER,UC_X86_REG_ESI:PARTNER,UC_X86_REG_EAX:SOURCE,UC_X86_REG_EBP:3,
              UC_X86_REG_EBX:0x12345678,UC_X86_REG_EDX:0x12345678,UC_X86_REG_ESP:SP,UC_X86_REG_EFLAGS:0x246}
        for r,v in regs.items():u.reg_write(r,v)
        u.emu_start(base+0x329298,base+0x3292d8,count=100000)
        assert u.reg_read(UC_X86_REG_EIP)==base+0x3292d8
        for r in (UC_X86_REG_EDI,UC_X86_REG_ESI,UC_X86_REG_EBP,UC_X86_REG_EBX):assert u.reg_read(r)==regs[r]
        assert u.reg_read(UC_X86_REG_ESP)==SP-28
        assert [word(u,SP-28+j*4) for j in range(5)]==[PLAYER,1,3,1,SP+0x5c]
        assert u.reg_read(UC_X86_REG_ECX)==PARTNER and u.reg_read(UC_X86_REG_EDX)==0x20060000
        assert u.reg_read(UC_X86_REG_EFLAGS)&0x8d5==regs[UC_X86_REG_EFLAGS]&0x8d5
        assert player_before==bytes(u.mem_read(PLAYER,0x2100)) and victim_before==bytes(u.mem_read(PARTNER,0x2100))
        assert movement_before==bytes(u.mem_read(base+0x186589,0x1d))
        return struct.unpack('<3f',u.mem_read(SP+0x5c,12))
    def exit_frame(self,native=(-20,-50,5)):
        u=self.u;u.mem_write(SP,b'\0'*256);u.mem_write(SOURCE,struct.pack('<3f',*native))
        start=(-40,-80,5);u.mem_write(SP+0x10,struct.pack('<3f',*start))
        u.mem_write(MOVE,struct.pack('<6f',-16,-16,0,16,16,72))
        regs={UC_X86_REG_ESI:PLAYER,UC_X86_REG_EAX:SOURCE,UC_X86_REG_EBX:MOVE,UC_X86_REG_EDI:MOVE+12,
              UC_X86_REG_EBP:PARTNER,UC_X86_REG_ECX:0x12345678,UC_X86_REG_EDX:0x87654321,UC_X86_REG_ESP:SP,UC_X86_REG_EFLAGS:0x246}
        for r,v in regs.items():u.reg_write(r,v)
        player_before=bytes(u.mem_read(PLAYER,0x2100))
        u.emu_start(base+0x329c24,base+0x329c2b,count=100000)
        assert u.reg_read(UC_X86_REG_ESP)==SP-20
        for r in (UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBX,UC_X86_REG_EBP,UC_X86_REG_ECX,UC_X86_REG_EDX):assert u.reg_read(r)==regs[r]
        assert u.reg_read(UC_X86_REG_EFLAGS)&0x8d5==regs[UC_X86_REG_EFLAGS]&0x8d5
        pointer=word(u,SP-20);result=struct.unpack('<3f',u.mem_read(pointer,12))
        assert [word(u,SP-20+j*4) for j in range(1,5)]==[MOVE,MOVE+12,1,0]
        u.emu_start(base+0x329c2b,base+0x329c3c,count=100000)
        assert u.reg_read(UC_X86_REG_ESP)==SP
        delta=struct.unpack('<3f',u.mem_read(SP+0x98+0xc,12))
        assert max(abs(a-(b-c)) for a,b,c in zip(delta,result,start))<.0002
        assert player_before==bytes(u.mem_read(PLAYER,0x2100))
        return result
def main():
    global PLUGIN
    cases=[]
    def expect(label,got,wanted):
        assert max(abs(a-b) for a,b in zip(got,wanted))<.0002,(label,got,wanted)
        cases.append(label)
    candidate=PLUGIN
    old_path=CONFIG.get('historical_stealth_plugin')
    if old_path:
        PLUGIN=Path(old_path)
        assert hashlib.sha256(PLUGIN.read_bytes()).hexdigest()=='1db0fdb71f9c63c007a6fb891ab692d3a1480577d5c4752a6c540a07c228f6b1'
        old=Harness();old.setup(weapon='item_w_chang_claw')
        expect('OLD Tiger common anchor defect reproduced',old.frame((-20,-50,3),(100,200,5)),(100,200,5))
        expect('OLD Tiger exit defect reproduced',old.exit_frame(),(-20,-50,5))
    PLUGIN=candidate
    assert not Harness(True).installed
    for rva in [0x329c24,0x8d990,0x92550,0x926e0]:assert not Harness(rva).installed
    for weapon in ['item_w_claws','item_w_chang_claw']:
        h=Harness();assert h.installed
        setup=h.setup
        def configure(**kw):setup(**dict(dict(weapon=weapon),**kw))
        configure()
        expect(weapon+' common anchor',h.frame((-20,-50,3),(100,200,5)),(-20,-50,5))
        expect(weapon+' repeated scene fresh anchor',h.frame((80,150,3),(100,200,5),.2),(80,150,5))
        expect(weapon+' native height',h.frame((-20,-50,3),(100,200,7),.3),(-20,-50,7))
        for yaw in [0,90,180,-90]:
            angle=math.radians(yaw);x,y=59.7084465,.8501992
            rotated=(x*math.cos(angle)-y*math.sin(angle),x*math.sin(angle)+y*math.cos(angle))
            victim=(100,200,5);anchor=(100-rotated[0],200-rotated[1],5)
            placed=h.frame(anchor,victim)
            expect(weapon+' victim world XY yaw '+str(yaw),(placed[0]+rotated[0],placed[1]+rotated[1],placed[2]),victim)
        for label,kw in [('victim role',dict(role=1)),('feeding',dict(kind=0)),('failure',dict(kind=4)),('ordinary',dict(kind=-1)),('NPC',dict(actor_class='npc_VHumanCombatant'))]:
            configure(**kw);expect(weapon+' '+label+' unchanged',h.frame((-20,-50,3),(100,200,5)),(100,200,5))
        configure(sequence=809);expect(weapon+' short victim',h.frame((-5,-10,3),(100,200,5)),(-5,-10,5))
        put(h.u,TABLE+100*12+8,4);expect(weapon+' stale serial unchanged',h.frame((-20,-50,3),(100,200,5)),(100,200,5))
        configure();put(h.u,PLAYER+0x19a4,0xffffffff);expect(weapon+' absent weapon',h.frame((-20,-50,3),(100,200,5)),(100,200,5))
        configure();put(h.u,base+0x566458,0);expect(weapon+' absent table',h.frame((-20,-50,3),(100,200,5)),(100,200,5))
        configure(role=-1,kind=-1);expect(weapon+' native exit actual root',h.exit_frame(),(45,60,5))
        h.root=(10,-15,80);expect(weapon+' exit keeps floor height',h.exit_frame(),(10,-15,5))
        for label,kw in [('failure',dict(activity='ACT_SNEAKATTACK_FAILURE_ATTACKER_CLAWS')),('ordinary',dict(activity='ACT_MELEE_ATTACK_CLAWS')),('NPC',dict(actor_class='npc_VHumanCombatant'))]:
            configure(**kw);expect(weapon+' '+label+' exit unchanged',h.exit_frame(),(-20,-50,5))
        configure();put(h.u,TABLE+100*12+8,4);expect(weapon+' stale exit unchanged',h.exit_frame(),(-20,-50,5))
        configure();h.bone=-1;expect(weapon+' missing root',h.exit_frame(),(-20,-50,5))
        h.bone=0;h.root=(float('nan'),2,3);expect(weapon+' invalid root',h.exit_frame(),(-20,-50,5))
    for weapon in ['item_w_unarmed','item_w_fists','item_w_knife','item_w_katana']:
        h=Harness();h.setup(weapon=weapon)
        expect(weapon+' entry unchanged',h.frame((-20,-50,3),(100,200,5)),(100,200,5))
        expect(weapon+' exit unchanged',h.exit_frame(),(-20,-50,5))
    out=path('output');out.mkdir(parents=True,exist_ok=True)
    (out/'stealth-native.json').write_text(json.dumps(dict(passed=True,plugin_sha256=hashlib.sha256(PLUGIN.read_bytes()).hexdigest(),cases=cases,signature_refusals=5,scope='Exact finalized module, native scene argument and swept-hull Ray instructions in Unicorn; synthetic entity state/root query. Stack/register/flags preserved; no live claim.'),indent=2),encoding='utf8')
    print('PASS',len(cases),'native cases, 5 signature refusals, ABI; optional historical control:',bool(old_path))
if __name__=='__main__':main()
