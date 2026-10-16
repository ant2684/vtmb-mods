"""Execute the exact installed helper from the finalized native candidate."""
import argparse
import hashlib
import json
import random
import struct
from pathlib import Path
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *

PIN = 'E88BEAE0DD03AF06493C71C5E8D87A6993B54E590CB6AD37CD3513C588582870'
ORIGINAL = bytes.fromhex('8b4424348a888101000084c90f8401070000')
SERVER_PIN = 'C546F4DE2003624D72F54D03805E0DBE1D8157231ADCC62368FF53FE6E48A76F'
PRICE_ORIGINAL = bytes.fromhex('0f8486000000')
BUY_ANCHOR = bytes.fromhex('85c07405c6442410018b078bcfff90cc05000084c00f8486000000578bcde8a7f0f2ff')
REGS = [UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
        UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EFLAGS]

def require(ok, message):
    if not ok: raise RuntimeError(message)

def execute(code, start, base, helper, mode, stackable, native=False, null=False, seed=1):
    u = Uc(UC_ARCH_X86, UC_MODE_32)
    for address, size in [(base,0x6e9000),(helper&~4095,4096),(0x20000000,0x10000)]:
        u.mem_map(address,size)
    u.mem_write(start,code)
    sp, ui, item, vt, getter = 0x20008000,0x20001000,0x20002000,0x20003000,0x20004000
    u.mem_write(sp+0x34,struct.pack('<I',ui));u.mem_write(ui+0x181,bytes([mode]))
    u.mem_write(item,struct.pack('<I',vt));u.mem_write(vt+0x3e8,struct.pack('<I',getter))
    # Thiscall accessor deliberately clobbers all volatile registers/flags.
    u.mem_write(getter,b'\xb8'+struct.pack('<I',0x12345600|stackable)+b'\xb9\x55\x55\x55\x55\xba\xaa\xaa\xaa\xaa\x83\xfa\x00\xc3')
    rng=random.Random(seed)
    for reg in REGS[:-2]:u.reg_write(reg,rng.getrandbits(32))
    u.reg_write(UC_X86_REG_ESI,0 if null else item);u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_EFLAGS,0x246)
    calls=[];end=[]
    def observe(uc,address,size,data):
        if address==getter:
            require(uc.reg_read(UC_X86_REG_ECX)==item,'thiscall donor differs');calls.append(address)
        if address in [base+0x16dfb6,base+0x16e6b7]:end.append(address);uc.emu_stop()
    u.hook_add(UC_HOOK_CODE,observe)
    u.emu_start(start,0,count=100)
    require(len(end)==1,'helper did not reach a native continuation')
    return end[0], [u.reg_read(r) for r in REGS],len(calls)

def price_execute(code,start,base,helper,stackable,owned,seed):
    u=Uc(UC_ARCH_X86,UC_MODE_32)
    for address,size in [(base,0xab9000),(helper&~4095,4096),(0x20000000,0x10000)]:u.mem_map(address,size)
    u.mem_write(start,code);sp=0x20008000;rng=random.Random(seed)
    local=bytearray(rng.randbytes(64));local[0x10]=owned;u.mem_write(sp,bytes(local))
    for reg in REGS[:-2]:u.reg_write(reg,rng.getrandbits(32))
    u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_EFLAGS,0x202 if stackable else 0x246)
    initial=[u.reg_read(r) for r in REGS];end=[]
    def observe(uc,address,size,data):
        if address in [base+0xda457,base+0xda3d1]:end.append(address);uc.emu_stop()
    u.hook_add(UC_HOOK_CODE,observe);u.emu_start(start,0,count=10)
    require(len(end)==1,'price helper did not reach native continuation')
    require([u.reg_read(r) for r in REGS]==initial,'price helper changed registers/flags/ESP')
    return end[0],bytes(u.mem_read(sp,64)),bytes(local)

def capacity_execute(code,start,base,helper,kind=2,mode=0,stack=1,quantity=10,full=0,matching=True,valid=True):
    u=Uc(UC_ARCH_X86,UC_MODE_32)
    for a,n in [(base,0x6e9000),(helper&~4095,4096),(0x20000000,0x100000)]:u.mem_map(a,n)
    u.mem_write(start,code);sp=0x20008000;ui=0x20001000;item=0x20002000;vt=0x20003000;getter=0x20004000;data=0x20010000;receiver=0x20090000;handles=0x200a0000;table=0x200b0000
    u.mem_write(ui+0x181,bytes([mode]));u.mem_write(ui+0x4d4,struct.pack('<I',kind))
    u.mem_write(item,struct.pack('<I',vt));u.mem_write(item+0x95e,b'\x17\x00')
    u.mem_write(vt+0x3e8,struct.pack('<I',getter))
    u.mem_write(getter,b'\xb8'+struct.pack('<I',stack)+b'\xb9\x55\x55\x55\x55\xba\xaa\xaa\xaa\xaa\xc3')
    u.mem_write(base+0x7b160,b'\xb8'+struct.pack('<I',data)+b'\xb9\x55\x55\x55\x55\xba\xaa\xaa\xaa\xaa\xc3')
    u.mem_write(data+0x4fea8,struct.pack('<I',10))
    for off,val in [(0x49d984,3),(0x49d978,handles),(0x2b8e98,table)]:u.mem_write(base+off,struct.pack('<I',val))
    # Empty, stale and valid entries ensure the scan validates handles before dereferencing.
    u.mem_write(handles,struct.pack('<III',0xffffffff,3|(2<<13),4|(3<<13)))
    u.mem_write(table+3*12+4,struct.pack('<II',0,1))
    u.mem_write(table+4*12+4,struct.pack('<II',receiver,3 if valid else 2))
    u.mem_write(receiver+0x95e,struct.pack('<H',23 if matching else 24));u.mem_write(receiver+0x954,struct.pack('<I',quantity))
    local=bytearray(random.Random(12).randbytes(96));local[0x13]=full;u.mem_write(sp,bytes(local))
    for reg in REGS[:-2]:u.reg_write(reg,0x12345678)
    u.reg_write(UC_X86_REG_ESI,ui);u.reg_write(UC_X86_REG_EBX,item);u.reg_write(UC_X86_REG_ESP,sp);u.reg_write(UC_X86_REG_EFLAGS,0x246)
    endpoint=[]
    def stop(uc,a,n,d):
        if a in [base+0x16fe56,base+0x16ff00]:endpoint.append(a);uc.emu_stop()
    u.hook_add(UC_HOOK_CODE,stop);u.emu_start(start,0,count=150)
    require(len(endpoint)==1,'capacity helper continuation missing')
    return endpoint[0],[u.reg_read(r) for r in REGS],bytes(u.mem_read(sp,96))


def capacity_verify(row):
    base=row['client_base'];helper=row['cap_helper_base'];code=bytes.fromhex(row['cap_helper_hex'])
    original=bytes.fromhex('8a44241384c00f85aa000000');cases=0
    contexts=[dict(kind=k,quantity=q) for k in [1,2,3,4,8] for q in [9,10,11]]
    contexts += [dict(mode=1),dict(stack=0),dict(matching=False),dict(valid=False),dict(full=1)]
    for kw in contexts:
        full=int(kw.get('full',0) or (kw.get('kind',2) in [2,4] and not kw.get('mode',0) and kw.get('stack',1) and kw.get('matching',True) and kw.get('valid',True) and kw.get('quantity',10)>=10))
        end,regs,local=capacity_execute(code,helper,base,helper,**kw)
        expected_kw={**kw,'full':full}
        expected_end,expected_regs,expected_local=capacity_execute(original,base+0x16fe4a,base,helper,**expected_kw)
        require((end,regs,local)==(expected_end,expected_regs,expected_local),'capacity branch/ABI/original locals differ: '+str(kw));cases+=1
    print('PASS exact receiver capacity helper:',cases,'Give/Sell/native-path/handle/ABI contexts')


def verify(certificate, client=None, server=None):
    row=json.loads(Path(certificate).read_text());capacity_verify(row);base=row['client_base'];helper=row['helper_base'];code=bytes.fromhex(row['helper_hex'])
    if client:
        data=Path(client).read_bytes();require(hashlib.sha256(data).hexdigest().upper()==PIN,'unsupported client fixture')
        mem=pefile.PE(data=data).get_memory_mapped_image()
        require(mem[0x16dfa4:0x16dfb6]==ORIGINAL,'native filter differs')
        require(mem.count(ORIGINAL)==1,'filter signature is not unique')
    count=0
    for mode in [0,1,2,255]:
        for stack in [0,1]:
            for null in [False,True]:
                for seed in [1,31,997]:
                    endpoint,registers,calls=execute(code,helper,base,helper,mode,stack,null=null,seed=seed)
                    original_end,original_regs,_=execute(ORIGINAL,base+0x16dfa4,base,helper,mode,stack,native=True,null=null,seed=seed)
                    require(registers==original_regs,'register/ESP/flags changed')
                    require(endpoint==(base+0x16dfb6 if mode or stack and not null else base+0x16e6b7),'wrong visibility branch')
                    require(calls==(1 if not mode and not null else 0),'accessor called outside duplicate loot filter')
                    if mode or not stack or null:require(endpoint==original_end,'unaffected native path changed')
                    count+=1
    print('PASS exact helper ABI/flags/thiscall/visibility:',count,'contexts; OS harness uses relocated candidate and module')
    base=row['server_base'];helper=row['price_helper_base'];code=bytes.fromhex(row['price_helper_hex'])
    if server:
        data=Path(server).read_bytes();require(hashlib.sha256(data).hexdigest().upper()==SERVER_PIN,'unsupported server fixture')
        mem=pefile.PE(data=data).get_memory_mapped_image()
        require(mem[0xda3cb:0xda3d1]==PRICE_ORIGINAL and mem.count(BUY_ANCHOR)==1,'server buy branch/unique anchor differs')
    count=0
    for stack in [False,True]:
        for owned in [0,1,255]:
            for seed in [1,31,997]:
                endpoint,local,before=price_execute(code,helper,base,helper,stack,owned,seed)
                original_end,original_local,_=price_execute(PRICE_ORIGINAL,base+0xda3cb,base,helper,stack,owned,seed)
                expected=bytearray(before)
                if stack:expected[0x10]=0
                require(endpoint==original_end,'price native branch changed')
                require(local==bytes(expected),'price helper changed another local or failed to clear stack price flag')
                if not stack:require(local==original_local,'nonstack/ammunition pricing changed')
                count+=1
    print('PASS exact server buy price flag ABI/locals/nonstack:',count,'contexts')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--certificate',required=True);p.add_argument('--client');p.add_argument('--server');a=p.parse_args();verify(a.certificate,a.client,a.server)
