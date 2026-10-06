"""Execute exact candidate bytes against native client signatures and ABI guards.

Client fixture models only the stock initializer's contract. Real gameplay
and the separate read-only UI observer prove that actual budgets are returned.
"""
import argparse,json,struct
from pathlib import Path
import pefile
from verify import Harness,clean,PBASE,VBASE,HEAP,STACK,STOP,UC_X86_REG_ECX
from unicorn.x86_const import UC_X86_REG_ESI,UC_X86_REG_EIP,UC_X86_REG_ESP

CBASE=0x70000000
CLIENT_HASH='E88BEAE0DD03AF06493C71C5E8D87A6993B54E590CB6AD37CD3513C588582870'

def patterns(base):
    guard=bytearray.fromhex('a14cb15f1085c0740c8b887402000085c90f95c0c332c0c3')
    init=bytearray.fromhex('51558b2d500d4a10568bf185ed0f845102000053578b7c2418')
    struct.pack_into('<I',guard,1,base+0x5fb14c)
    struct.pack_into('<I',init,4,base+0x4a0d50)
    return [(0x1713e0,bytes(guard)),(0x17d930,bytes(init))]

class PoolHarness(Harness):
    def __init__(self,pe,client_variant=''):
        self.client_variant=client_variant;self.pool_calls=[]
        super().__init__(pe)
        self.u.mem_map(CBASE,0x600000)
        self.u.mem_write(CBASE,b'MZ');self.w(CBASE+0x3c,0x100)
        self.u.mem_write(CBASE+0x100,b'PE\0\0')
        self.u.mem_write(CBASE+0x104,struct.pack('<HH',0x14c,2))
        self.u.mem_write(CBASE+0x114,struct.pack('<H',224))
        self.u.mem_write(CBASE+0x118,struct.pack('<H',0x10b));self.w(CBASE+0x150,0x600000)
        for i,(r,pat) in enumerate(patterns(CBASE)):
            h=CBASE+0x1f8+i*40;self.w(h+8,0x100);self.w(h+12,r&~0xff);self.w(h+36,0x60000020)
            self.u.mem_write(CBASE+r,pat)
            if client_variant=='mismatch:'+str(i):self.u.mem_write(CBASE+r,b'\x90')
            if client_variant=='duplicate:'+str(i):self.u.mem_write(CBASE+(r&~0xff)+0x80,pat)
        self.character=HEAP+0xc000;self.sheet=HEAP+0xf000
        self.w(CBASE+0x5fb14c,self.character);self.w(self.character+0x274,1)
        self.w(self.character+0xedc,self.sheet)
        self.remaining=[0]*7;self.spent=10
    def step(self,u,addr,size,unused):
        if getattr(self,'purchase_guard',False):
            if addr in [CBASE+0x180bf3,CBASE+0x180b00]:
                self.purchase_rejected=addr==CBASE+0x180bf3;u.emu_stop();return
            if addr==CBASE+0x17c720:self.ret(0,0,True);return
        if addr in self.api and self.api[addr]=='GetModuleHandleA':
            sp=self.reg(UC_X86_REG_ESP);arg=self.r(sp+4)
            name=bytes(self.u.mem_read(arg,12)).split(b'\0')[0]
            self.ret(4,CBASE if name==b'client.dll' and self.client_variant!='missing' else 0 if name==b'client.dll' else VBASE)
            return
        if addr==CBASE+0x17d930:
            sp=self.reg(UC_X86_REG_ESP)
            assert self.reg(UC_X86_REG_ECX)==self.sheet and self.r(sp+4)==self.clan
            self.pool_calls.append((self.sheet,self.clan));self.remaining=[2,0,1,3,2,1,1];self.spent=0
            self.ret(4,0,True);return
        super().step(u,addr,size,unused)
    def client(self):
        self.run(PBASE+next(e.address for e in self.pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name==b'loaded_client'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('plugin');ap.add_argument('client');args=ap.parse_args()
    p,sha=clean(Path(args.plugin));raw=Path(args.client).read_bytes()
    import hashlib
    assert hashlib.sha256(raw).hexdigest().upper()==CLIENT_HASH
    native=pefile.PE(data=raw);image=native.get_memory_mapped_image()
    for r,pat in patterns(native.OPTIONAL_HEADER.ImageBase):
        assert image[r:r+len(pat)]==pat
        hits=[]
        for section in native.sections:
            if section.Characteristics&0x20000000:
                data=section.get_data();pos=data.find(pat)
                while pos>=0:hits.append(section.VirtualAddress+pos);pos=data.find(pat,pos+1)
        assert hits==[r],hits
    cases=[]
    for variant in ['missing','mismatch:0','mismatch:1','duplicate:0','duplicate:1']:
        h=PoolHarness(p,variant);h.install();h.client();h.exercise('NONE',999,8965)
        assert h.pool_calls==[] and h.remaining==[0]*7;cases.append(variant)
    for mode in ['no_character','outside_creation','no_sheet','auto_none','manual_history','repeat']:
        h=PoolHarness(p);h.install();h.client();h.client()
        if mode=='no_character':h.w(CBASE+0x5fb14c,0)
        if mode=='outside_creation':h.w(h.character+0x274,0)
        if mode=='no_sheet':h.w(h.character+0xedc,0)
        h.exercise('HISTORY' if mode=='manual_history' else 'NONE',4,8965)
        if mode in ['no_character','outside_creation','no_sheet']:
            assert not h.pool_calls and h.spent==10
        else:
            assert len(h.pool_calls)==1 and h.remaining==[2,0,1,3,2,1,1] and h.spent==0
            if mode=='repeat':
                h.exercise('NONE',-2,8965)
                assert len(h.pool_calls)==2 and sum(h.remaining)==10
        assert h.xp==8965;cases.append(mode)
    # Execute the actual stock category guard, independently of the fixture
    # initializer: zero denies a purchase; one permits exactly one debit.
    for remaining in [0,1]:
        h=PoolHarness(p);h.purchase_guard=True
        h.u.mem_write(CBASE+0x180ab4,image[0x180ab4:0x180b00])
        h.w(h.sheet+0xb4,0);h.w(h.sheet+0xb8,1)
        h.w(h.sheet+0x80,remaining);h.w(h.sheet+0x2e4,0)
        h.u.reg_write(UC_X86_REG_ESI,h.sheet);h.u.reg_write(UC_X86_REG_ESP,STACK+0x7000)
        h.u.emu_start(CBASE+0x180ab4,STOP,count=100)
        assert h.purchase_rejected==(remaining==0)
        assert h.r(h.sheet+0x80)==0 and h.r(h.sheet+0x2e4)==remaining
        cases.append('native_purchase_guard:'+str(remaining))
    print(json.dumps({'result':'PASS','sha256':sha,'client_hash':CLIENT_HASH,'cases':cases,
                      'scope':'Exact PE, relocated native signatures, existing server ABI, creation-only UI initialization and XP preservation'}))

if __name__=='__main__':main()
