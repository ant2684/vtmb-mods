"""Execute pinned native packet/queue code using the operand applied by the VTM.
No live process or game DLL load. External world effects are supplied by mocks.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESI, UC_X86_REG_EBP, UC_X86_REG_EIP, UC_X86_REG_ESP
EXPECTED='c546f4de2003624d72f54d03805e0dbe1d8157231adcc62368ff53fe6e48a76f'
BASE=0x10000000
MEM=0x12000000
STACK=0x13000000
STOP=MEM+0xff00
SITE=0x3e3674
class Machine:
    def __init__(self, image, operand):
        self.u=Uc(UC_ARCH_X86, UC_MODE_32)
        self.u.mem_map(BASE, (len(image)+4095)&~4095)
        self.u.mem_write(BASE,image)
        self.u.mem_write(BASE+SITE,bytes([operand]))
        self.u.mem_map(MEM,0x20000)
        self.u.mem_map(STACK,0x10000)
        self.hooks={}
        self.calls=[]
        self.u.hook_add(UC_HOOK_CODE,self.hook)
    def w(self,a,v): self.u.mem_write(a,struct.pack('<I',v&0xffffffff))
    def f(self,a,v): self.u.mem_write(a,struct.pack('<f',v))
    def r(self,a): return struct.unpack('<I',self.u.mem_read(a,4))[0]
    def reg(self,r,v=None):
        if v is None: return self.u.reg_read(r)
        self.u.reg_write(r,v)
    def ret(self,result=0,pop=0):
        sp=self.reg(UC_X86_REG_ESP)
        dst=self.r(sp)
        self.reg(UC_X86_REG_EAX,result)
        self.reg(UC_X86_REG_ESP,sp+4+pop)
        self.reg(UC_X86_REG_EIP,dst)
    def hook(self,u,a,size,data):
        if a==STOP: u.emu_stop(); return
        if a in self.hooks: self.hooks[a](self)
    def run(self,start,args=(),end=STOP):
        sp=STACK+0xff00
        self.w(sp,STOP)
        for i,v in enumerate(args): self.w(sp+4+i*4,v)
        self.reg(UC_X86_REG_ESP,sp)
        self.u.emu_start(BASE+start,end,count=50000)
def build_and_queue(image,operand,coefficient,npc=True,invulnerable=False):
    m=Machine(image,operand)
    weapon=MEM+0x1000; info=MEM+0x7000; owner=MEM+0x8000; target=MEM+0x9000; template=MEM+0xa000
    m.w(BASE+0x9f3680,MEM+0xb000)
    m.w(BASE+0x9f3620,MEM+0xc000)
    m.w(info,0); m.w(info+0x3f8,110)
    m.w(target+0x9c,target); m.w(target+0x98,target if npc else 0)
    m.u.mem_write(target+0x63d8,bytes([invulnerable]))
    m.f(template+0xc8,coefficient)
    d=weapon+0x77c
    for off,val in ((0,2),(4,1),(8,0),(0xc,2),(0x10,8)): m.w(d+off,val)
    m.f(d+0x3c,1.0)
    m.hooks[BASE+0x2517e0]=lambda x:x.ret(info)
    m.hooks[BASE+0x1faa70]=lambda x:x.ret(1)
    m.hooks[BASE+0x2521f0]=lambda x:x.ret(owner)
    m.hooks[BASE+0x337860]=lambda x:x.ret(0)
    m.hooks[BASE+0x1d5e80]=lambda x:x.ret(template,4)
    m.reg(UC_X86_REG_ECX,weapon)
    m.run(0x3e3570,(target,0,0,0),end=BASE+0x3e36c3)
    packet=m.r(m.reg(UC_X86_REG_ESP)); descriptor=m.r(packet)
    packet_bytes=bytes(m.u.mem_read(packet,0x4c))
    descriptor_bytes=bytes(m.u.mem_read(descriptor,0x44))
    # Remove the pre-builder mock; the queue gate now executes actual GetDmg.
    del m.hooks[BASE+0x1faa70]
    def queue(x):
        sp=x.reg(UC_X86_REG_ESP)
        x.calls.append({'target':x.r(sp+4),'amount':x.r(sp+8)})
        x.ret()
    m.hooks[BASE+0x23e4b0]=queue
    m.reg(UC_X86_REG_EBP,packet); m.reg(UC_X86_REG_ESI,target)
    m.run(0x33054c,end=BASE+0x330593)
    expected_count=1 if operand==0 and npc and not invulnerable else 0
    assert len(m.calls)==expected_count
    if expected_count: assert m.calls==[{'target':target,'amount':int(110*coefficient)}]
    assert packet_bytes[0x4a]==operand
    assert m.r(descriptor+0x40)&8
    return packet_bytes,descriptor_bytes,m.calls
def cvar_gate(image,enabled):
    m=Machine(image,0)
    convar=MEM+0x1000; vtable=MEM+0x2000
    m.w(BASE+0x752ddc,convar);m.w(convar,vtable)
    m.w(vtable+4,MEM+0xf000);m.w(convar+0x2c,enabled)
    m.hooks[MEM+0xf000]=lambda x:x.ret(0)
    m.run(0x23e720,(MEM+0x3000,55),end=BASE+0x23e799)
    continues=m.reg(UC_X86_REG_EIP)==BASE+0x23e799
    assert continues==bool(enabled)
    return {'enabled':enabled,'native_emit_path_continues':continues}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--server',required=True);ap.add_argument('--identity-only',action='store_true')
    ap.add_argument('--certificate');ap.add_argument('--plugin')
    a=ap.parse_args()
    raw=Path(a.server).read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED,'unsupported server identity'
    image=pefile.PE(data=raw).get_memory_mapped_image()
    assert image[SITE-1:SITE+10]==bytes.fromhex('6a018d4c2420e817d5c2ff')
    if a.identity_only: print('PASS supported native server SHA-256');return
    assert a.certificate and a.plugin
    certificate=json.loads(Path(a.certificate).read_text())
    assert certificate['rva']==SITE and certificate['operand']==0 and certificate['changed_bytes']==1
    cases=[]
    # Actual boss filter declarations and neutral control exercise amount handling.
    for c in (1.0,0.5,0.3,0.1):
        old,old_d,old_q=build_and_queue(image,1,c)
        new,new_d,new_q=build_and_queue(image,certificate['operand'],c)
        assert [i for i,(x,y) in enumerate(zip(old,new)) if x!=y]==[0x4a]
        assert old_d==new_d and not old_q and len(new_q)==1
        cases.append({'filter':c,'stock_hit_number':new_q[0]['amount'],'packet_differences':[0x4a],'damage_descriptor_identical':True})
    for npc,invulnerable in ((False,False),(True,True)):
        _,_,queue=build_and_queue(image,0,0.5,npc,invulnerable)
        assert not queue
        cases.append({'npc':npc,'invulnerable':invulnerable,'queue_count':0})
    result={'result':'PASS','cases':len(cases)+2,'server_sha256':EXPECTED,
            'plugin_sha256':hashlib.sha256(Path(a.plugin).read_bytes()).hexdigest(),
            'source_of_operand':'actual finalized VTM Windows fixture certificate',
            'amount_policy':'existing native hit-number semantics, not a new net-HP-loss policy',
            'packet_and_queue':cases,'damage_floaters_cvar':[cvar_gate(image,0),cvar_gate(image,1)]}
    Path(a.certificate).with_name('flow-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result))
if __name__=='__main__':main()
