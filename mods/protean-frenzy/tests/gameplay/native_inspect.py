"""Read-only inspection of the pinned local Bloodlines image and resources."""
import sys, struct, re, json
from pathlib import Path
from local_runtime import path,COMMON
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
GAME=path('game')
pe=pefile.PE(str(GAME/'Vampire/dlls/vampire.dll'))
mem=pe.get_memory_mapped_image(); base=pe.OPTIONAL_HEADER.ImageBase
md=Cs(CS_ARCH_X86,CS_MODE_32)
def dis(a,z):
    for ins in md.disasm(mem[a:z],base+a):
        if ins.mnemonic not in ('int3','nop'): print(hex(ins.address-base),ins.mnemonic,ins.op_str)
def thunk(a):
    if mem[a]==0xe9: return a+5+struct.unpack_from('<i',mem,a+1)[0]
    return a
def calls(a):
    target=thunk(a); aliases={target}
    for x in re.finditer(b'\xe9',mem[:0x16000]):
        off=x.start()
        if thunk(off)==target: aliases.add(off)
    result=[]
    for x in re.finditer(b'\xe8',mem[:0x440000]):
        off=x.start()
        if off+5+struct.unpack_from('<i',mem,off+1)[0] in aliases:result.append(hex(off))
    return result
def assets():
    for folder in ('Vampire','Unofficial_Patch'):
        for pack in sorted((GAME/folder).glob('pack*.vpk')):
            with pack.open('rb') as f:
                f.seek(-9,2);n,t=struct.unpack('<II',f.read(8));f.seek(t);d=f.read();q=0
                for _ in range(n):
                    l=struct.unpack_from('<I',d,q)[0];q+=4;name=d[q:q+l].decode();q+=l
                    start,size=struct.unpack_from('<II',d,q);q+=8
                    yield name,pack,start,size
def asset(name):
    loose=GAME/'Unofficial_Patch'/name
    if loose.exists():return loose.read_bytes()
    rows=[v for v in assets() if v[0].lower()==name.lower()]
    if not rows:raise KeyError(name)
    _,pack,off,size=rows[-1]
    with pack.open('rb') as f:f.seek(off);return f.read(size)
if __name__=='__main__':
    if sys.argv[1]=='dis':
        for pair in sys.argv[2:]:
            a,z=[int(v,16) for v in pair.split(':')];print('DISASM',hex(a));dis(a,z)
    elif sys.argv[1]=='calls':
        for s in sys.argv[2:]:a=int(s,16);print(hex(a),'target',hex(thunk(a)),'calls',calls(a))
    elif sys.argv[1]=='model':
        sys.path.insert(0,str(COMMON))
        import mdl
        d=asset(sys.argv[2]);aa=list(mdl.anims(d).items())
        for n,q in mdl.seqs(d).items():
            j=struct.unpack_from('<h',d,q+56)[0];raw,ad=aa[j]
            print(n,mdl.cs(d,q+mdl.i(d,q+4)) if mdl.i(d,q+4) else '', 'flags',hex(mdl.i(d,q+8)), 'raw',raw,'frames',mdl.i(d,ad+12),'fps',mdl.f(d,ad+4))
