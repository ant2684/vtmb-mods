"""Execute original full caption dispatcher + native phrase/sentence search.
Only its external clock/source metadata/UI endpoints are synthetic; dispatcher,
rewind, gap, cursor, and suppressed-display behavior run from recorded engine.
"""
import sys,struct,json,hashlib,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import native_clock as native
import pefile,capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
GAME=Path(os.environ.get('VTMB_VERIFY_GAME',r'LOCAL_GAME_ROOT_REQUIRED'))
pe=pefile.PE(str(GAME/'Bin/engine.dll'));base=0x20000000
assert hashlib.sha256((GAME/'Bin/engine.dll').read_bytes()).hexdigest().upper()=='9D00B2C1E5EDBAD052FB0B514634BA54574666E12D1B408C46CE141D51ED2313'
u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(base,0x1400000);u.mem_write(base,pe.get_memory_mapped_image());u.mem_map(0x30000000,0x20000);u.mem_map(0x60000000,0x2000)
DATA=0x30000000;CH=DATA+0x1000;SFX=DATA+0x2000;SRC=DATA+0x3000;MIX=DATA+0x4000;CAP=DATA+0x5000;STACK=DATA+0x1f000;CODE=0x60000000;STATE=CODE+0x1000;END=DATA+0x100
def u32(a,x):u.mem_write(a,struct.pack('<I',x&0xffffffff))
def f32(a,x):u.mem_write(a,struct.pack('<f',x))
def r32(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def text(a):return bytes(u.mem_read(a,256)).split(b'\0',1)[0].decode('ascii')
def ret(pop=0,eax=None):
 sp=u.reg_read(UC_X86_REG_ESP)
 if eax is not None:u.reg_write(UC_X86_REG_EAX,eax)
 u.reg_write(UC_X86_REG_EIP,r32(sp));u.reg_write(UC_X86_REG_ESP,sp+4+pop)
u.mem_write(CODE,native.sync(CODE,STATE));u.mem_write(CODE+0x200,native.clock(CODE+0x200,STATE,CODE))
site=base+0x1188b0;u.mem_write(site,b'\xe8'+struct.pack('<i',CODE+0x200-site-5))
NOW=DATA+0x8000;NOW_STUB=DATA+0x8010;RATE_STUB=DATA+0x8020;POS_STUB=DATA+0x8030;SENTENCE_STUB=DATA+0x8040;FALSE_STUB=DATA+0x8050;SHOW=DATA+0x8060
u.mem_write(NOW_STUB,b'\xdd\x05'+struct.pack('<I',NOW)+b'\xc3');u32(native.PLAT_IAT,NOW_STUB)
u.mem_write(RATE_STUB,bytes.fromhex('8b4104c3'));u.mem_write(POS_STUB,bytes.fromhex('8b8180000000c3'))
u.mem_write(native.GET_SAMPLE_POSITION,b'\xe9'+struct.pack('<i',POS_STUB-native.GET_SAMPLE_POSITION-5));u.mem_write(SENTENCE_STUB,b'\xb8'+struct.pack('<I',CAP)+b'\xc3');u.mem_write(FALSE_STUB,bytes.fromhex('31c0c3'));u.mem_write(SHOW,bytes.fromhex('c20400'))
u32(CH,SFX);u32(CH+4,MIX);u32(SFX+0x104,SRC);u32(SRC,DATA+0x8100);u32(SRC+4,44100);u32(DATA+0x810c,RATE_STUB);u32(DATA+0x813c,SENTENCE_STUB)
u32(base+0x3460c4,DATA+0x8200);u32(DATA+0x8200,DATA+0x8300);u32(DATA+0x8200+0x2c,1);u32(DATA+0x8304,FALSE_STUB)
u32(base+0x1cc820,DATA+0x8400);u32(DATA+0x8400,DATA+0x8500);u32(DATA+0x8500+0xa8,SHOW);u32(base+0x173328,DATA+0x8600);u32(base+0x17332c,DATA+0x8700);u32(base+0x1970d0,DATA+0x8400)
f32(base+0x1734e8,0);f32(CH+0x98,100);u32(CH+0xc,100);u32(CH+0x94,0xfffffffe)
u32(CAP+0x820,3);u32(CAP+0x814,DATA+0x9000)
phrases=[(0,10,[(0,4,'Early A'),(4,10,'Early B')]),(20,40,[(20,30,'Late A'),(30,40,'Late B')]),(45,50,[(45,50,'')])]
for i,(start,end,sentences) in enumerate(phrases):
 p=DATA+0xa000+i*0x100;arr=DATA+0xb000+i*0x100;u32(DATA+0x9000+i*4,p);f32(p,start);f32(p+4,end);u32(p+0x10,arr);u32(p+0x1c,len(sentences))
 for j,(s,e,t) in enumerate(sentences):
  ptr=DATA+0xc000+i*0x400+j*0x100;f32(arr+j*12,s);f32(arr+j*12+4,e);u32(arr+j*12+8,ptr);u.mem_write(ptr,t.encode()+b'\0')
visible='';pending='';emitted=[]
def endpoint(uc,a,size,_):
 global visible,pending
 sp=u.reg_read(UC_X86_REG_ESP)
 if a==base+0xde630:
  f32(r32(sp+4),0);f32(r32(sp+8),50);ret(8)
 elif a==base+0xdb790:ret() # sentences already constructed, no allocation/parser
 elif a==base+0xdf380:pending=text(r32(sp+4));ret(0,1)
 elif a==base+0x118710:ret(0,42) # caller removes its two arguments
 elif a==SHOW:visible=pending;emitted.append(visible);ret(4)
u.hook_add(UC_HOOK_CODE,endpoint)
results=[]
def run(label,audio,fallback,expected_cursor,expected_visible,emit,mixer=True,volume=100):
 global emitted
 emitted=[];u32(CH+4,MIX if mixer else 0);u32(CH+0x80,int(audio*44100));u.mem_write(NOW,struct.pack('<d',fallback));u32(CH+0xc,volume)
 for reg,value in ((UC_X86_REG_EBX,0x11223344),(UC_X86_REG_ESI,0x55667788),(UC_X86_REG_EDI,0x99aabbcc),(UC_X86_REG_EBP,0xabcdef00)) :u.reg_write(reg,value)
 u.reg_write(UC_X86_REG_ESP,STACK);u32(STACK,END);u32(STACK+4,0);u32(STACK+8,CH)
 u.emu_start(base+0x118880,END,count=20000)
 cursor=r32(CH+0x94);assert cursor==expected_cursor,(label,cursor,expected_cursor);assert visible==expected_visible,(label,visible);assert bool(emitted)==emit,(label,emitted)
 assert u.reg_read(UC_X86_REG_ESP)==STACK+4
 for reg,value in ((UC_X86_REG_EBX,0x11223344),(UC_X86_REG_ESI,0x55667788),(UC_X86_REG_EDI,0x99aabbcc),(UC_X86_REG_EBP,0xabcdef00)):assert u.reg_read(reg)==value
 results.append({'case':label,'cursor':cursor,'visible':visible,'emitted':emitted})
run('primary late',24,124,0x10000,'Late A',True)
run('fallback later',0,134,0x10001,'Late B',True,mixer=False)
run('primary rewind',2,135,0,'Early A',True)
run('fallback gap',0,116,0,'Early A',False,mixer=False)
run('primary valid after gap',22,136,0x10000,'Late A',True)
run('empty text',46,137,0x10000,'Late A',False)
run('volume suppressed',34,138,0x10000,'Late A',False,volume=0)
run('same cursor retained after suppression',34,139,0x10001,'Late B',True)
run('fallback rewind',0,122,0x10000,'Late A',True,mixer=False)
run('primary stable',22,140,0x10000,'Late A',False)
PHASE=DATA+0x8080
# A 50-second synthetic loop tests the complete dispatcher through the actual
# generated callback call. The real MP3 period is separately measured in-game.
u.mem_write(PHASE,bytes.fromhex('8b44240831d2b9')+struct.pack('<I',50*44100)+bytes.fromhex('f7f18bc2c3'))
u32(STATE+40,PHASE)
run('loop late phrase',34,141,0x10001,'Late B',True)
run('loop wrap to early',52,142,0,'Early A',True)
run('loop no-text gap',66,143,0,'Early A',False)
run('loop following phrase',74,144,0x10000,'Late A',True)
print(json.dumps({'result':'PASS','cases':results,'scope':'original full dispatcher/native lookup with synthetic metadata/UI endpoints; gap retains stock visible text'},indent=2))
