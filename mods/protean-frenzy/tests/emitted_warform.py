"""Execute the generated x86 in Unicorn at two DLL bases with synthetic objects.

External game functions are stubs; this verifies machine-code control flow,
handle validation, model targets, untouched Frenzy state, and stack balance.
Gameplay acceptance remains a separate requirement.
"""
import sys, struct
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import json
META=json.loads((Path(sys.argv[1])/'emitted.json').read_text())
DELTA=META['server']-0x10000000
CODE=META['server_code']
BLOB=(Path(sys.argv[1])/'server-code.bin').read_bytes()


def test(delta, frenzy, handle_valid=True, missing=False):
    u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(CODE,0x1000)
    u.mem_map(0x10000000+delta,0xb00000)
    u.mem_map(0x20000000,0x20000)
    u.mem_map(0x30000000,0x10000)
    player,shadow,table,vtable=0x20000000,0x20004000,0x20008000,0x2000c000
    stack=0x30008000
    def w(a,v):u.mem_write(a,struct.pack('<I',v))
    def r(a):return struct.unpack('<I',u.mem_read(a,4))[0]
    w(player, vtable);w(shadow,vtable)
    w(player+0xa8,player);w(player+0x146c,frenzy);w(player+0x1edc,1)
    w(player+0x1db0,0xffffffff if missing else (7<<13)|1)
    w(0x10566458+delta,table)
    w(table+16,shadow);w(table+20,7 if handle_valid else 8)
    w(0x1070b228+delta,table+0x100);w(table+0x10c,0x447a0000)
    model_stub=0x10017000+delta; w(vtable+0x1a4,model_stub)
    u.mem_write(model_stub,b'\xc2\x04\x00')
    u.mem_write(0x10227a30+delta,b'\xc2\x08\x00')
    u.mem_write((CODE-DELTA+512)+delta,BLOB[0x200:0x300])
    u.reg_write(UC_X86_REG_EBP,player);u.reg_write(UC_X86_REG_ESP,stack)
    calls=[];exit_address=[]
    def trace(uc,addr,size,_):
        if addr==model_stub:
            calls.append(('model',uc.reg_read(UC_X86_REG_ECX),r(uc.reg_read(UC_X86_REG_ESP)+4)))
        if addr==0x10227a30+delta:
            calls.append(('event',uc.reg_read(UC_X86_REG_ECX),r(uc.reg_read(UC_X86_REG_ESP)+4),r(uc.reg_read(UC_X86_REG_ESP)+8)))
        if addr in (0x101f8fa3+delta,0x101f917d+delta):
            exit_address.append(addr);uc.emu_stop()
    u.hook_add(UC_HOOK_CODE,trace)
    u.emu_start((CODE-DELTA+512)+delta,0,count=300)
    active=frenzy>0 and handle_valid and not missing
    assert exit_address==[(0x101f8fa3 if active else 0x101f917d)+delta]
    assert u.reg_read(UC_X86_REG_ESP)==stack
    assert r(player+0x146c)==frenzy
    assert r(player+0x1db0)==(0xffffffff if missing else (7<<13)|1)
    if active:
        assert calls==[('model',player,player+0x23d4),('model',shadow,player+0x23d4),('event',0x10750cb4+delta,player,2)]
        assert r(player+0x1edc)==0 and r(player+0x1c68)==0x447a0000
    else:assert calls==[] and r(player+0x1edc)==1
    print('PASS expiration',hex(delta),frenzy,handle_valid,missing)

def test_reentry(delta,count):
    u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(CODE,0x1000);u.mem_map(0x10000000+delta,0x400000)
    u.mem_map(0x20000000,0x10000)
    u.mem_write((CODE-DELTA+256)+delta,BLOB[0x100:0x200])
    u.mem_write(0x2000146c,struct.pack('<i',count))
    u.reg_write(UC_X86_REG_EAX,0x20000000);u.reg_write(UC_X86_REG_ESP,0x20008000)
    exits=[]
    def trace(uc,a,s,_):
        if a in (0x1033e9c3+delta,0x1033e9d4+delta):exits.append(a);uc.emu_stop()
    u.hook_add(UC_HOOK_CODE,trace);u.emu_start((CODE-DELTA+256)+delta,0,count=20)
    assert exits==[(0x1033e9d4 if count>0 else 0x1033e9c3)+delta]
    assert u.reg_read(UC_X86_REG_ESP)==0x20008000-(0 if count>0 else 4)
    print('PASS reentry',hex(delta),count)

def test_input(delta,count,wolf):
    u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(CODE,0x1000);u.mem_map(0x10000000+delta,0x400000)
    u.mem_map(0x20000000,0x10000)
    u.mem_write((CODE-DELTA+1024)+delta,BLOB[0x400:0x500])
    u.mem_write(0x2000146c,struct.pack('<i',count));u.mem_write(0x20001edc,bytes([wolf]))
    u.reg_write(UC_X86_REG_EDI,0x20000000);u.reg_write(UC_X86_REG_ECX,0)
    u.reg_write(UC_X86_REG_ESP,0x20008000)
    u.emu_start((CODE-DELTA+1024)+delta,0x103510dd+delta,count=30)
    zero=bool(u.reg_read(UC_X86_REG_EFLAGS)&0x40)
    assert zero==(count>0 or not wolf)
    assert u.reg_read(UC_X86_REG_ESP)==0x20008000
    assert u.reg_read(UC_X86_REG_EDI)==0x20000000 and u.reg_read(UC_X86_REG_ECX)==0
    print('PASS input',hex(delta),count,wolf)

for delta in (DELTA,):
    for n in (0,1):test(delta,n)
    test(delta,1,False);test(delta,1,missing=True)
    for n in (0,1):test_reentry(delta,n)
    for n in (0,1):
        for wolf in (0,1):test_input(delta,n,wolf)
