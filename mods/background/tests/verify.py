"""Pinned PE/disassembly and original native PaintBackground semantic regression."""
import argparse, hashlib, json, struct, sys, subprocess
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--client',required=True);ap.add_argument('--plugin',required=True);ap.add_argument('--dependency-dir',required=True);ap.add_argument('--output');a=ap.parse_args()
    sys.path.insert(0,a.dependency_dir)
    import pefile,capstone
    from clean_payload import verify_clean
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP,UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_FPCW,UC_X86_REG_FPSW
    raw=Path(a.client).read_bytes()
    assert hashlib.sha256(raw).hexdigest().upper()=='E88BEAE0DD03AF06493C71C5E8D87A6993B54E590CB6AD37CD3513C588582870'
    client=pefile.PE(data=raw);data=client.get_memory_mapped_image();base=0x10000000
    plugin=pefile.PE(a.plugin);assert plugin.FILE_HEADER.Machine==0x14c and plugin.OPTIONAL_HEADER.Magic==0x10b
    exports=[e.name.decode() for e in plugin.DIRECTORY_ENTRY_EXPORT.symbols];assert exports==['loaded_client'],exports
    cleanliness=verify_clean(a.plugin, ['loaded_client'], Path(__file__).resolve().parents[1]/'plugin')
    native_load=subprocess.run([str(Path(__file__).resolve().parents[1]/'build/load-clean.exe'),str(Path(a.plugin).resolve()),'loaded_client'],capture_output=True,text=True)
    assert native_load.returncode==0,native_load.stdout+native_load.stderr
    patch=bytes.fromhex('e9bf00000090');cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    assert [(i.mnemonic,i.size) for i in cs.disasm(data[0xf1ae5:0xf1aeb],base+0xf1ae5)]==[('je',6)]
    assert [(i.mnemonic,i.op_str) for i in cs.disasm(patch,base+0xf1ae5)]==[('jmp','0x100f1ba9'),('nop','')]
    # The original block contains only reading, float math and two surface draws.
    instructions=list(cs.disasm(data[0xf1aeb:0xf1ba9],base+0xf1aeb))
    assert len([i for i in instructions if i.mnemonic=='call' and i.op_str=='dword ptr [edx + 0x30]'])==1
    assert len([i for i in instructions if i.mnemonic=='call' and i.op_str=='dword ptr [edx + 0x34]'])==1
    assert all(i.op_str.startswith(('dword ptr [esp','byte ptr [esp')) or i.mnemonic not in ('mov','fstp') or '[' not in i.op_str.split(',')[0] for i in instructions)
    cases=[]
    def run(patched,fade,width=1100,height=57,dialog=False,hidden=False,captions=True):
        uc=Uc(UC_ARCH_X86,UC_MODE_32);uc.mem_map(base,(client.OPTIONAL_HEADER.SizeOfImage+0xfff)&~0xfff);uc.mem_write(base,data)
        uc.mem_map(0x30000000,0x10000);uc.mem_map(0x40000000,0x10000)
        def w(addr,value):uc.mem_write(addr,struct.pack('<I',value))
        self=0x30001000;surface=0x30002000;vt=0x30003000;cv1=0x30004000;cv2=0x30004100;player=0x30005000;cvvt=0x30006000
        if patched:uc.mem_write(base+0xf1ae5,patch)
        w(self+0x8c,height);w(self+0x88,width);w(self+0x84,9)
        uc.mem_write(base+0x4d0f50,b'\x01');w(base+0x4cff44,cv1);w(base+0x5faa34,cv2)
        w(cv1,cvvt);w(cv2,cvvt);w(cv1+4,cv1);w(cv2+4,cv2)
        w(cv1+0x2c,1 if hidden else 0);w(cv2+0x2c,1 if captions else 0)
        w(cvvt+4,0x30008000);w(surface,vt)
        for slot,offset in [(0x28,0),(0x30,16),(0x34,32)]:w(vt+slot,0x30008100+offset)
        uc.mem_write(base+0x5fbf38+0x450,struct.pack('<f',fade))
        # _ftol external helper replaced only in the emulator, preserving x87 pop.
        uc.mem_write(base+0x1d0ed4,bytes.fromhex('83ec04db1c2458c3'))
        # Seed a caller-owned x87 value and return to the actual original entry.
        uc.mem_write(0x30009000,bytes.fromhex('d90510900030e905000000'));uc.mem_write(0x30009010,struct.pack('<f',3.25))
        w(0x30009010+4,0)
        # Run the fld only, then start native PaintBackground separately.
        uc.emu_start(0x30009000,0x30009006,count=1)
        uc.reg_write(UC_X86_REG_FPCW,0x0f7f)
        stack=0x40008000;w(stack,0x3000f000);uc.reg_write(UC_X86_REG_ESP,stack);uc.reg_write(UC_X86_REG_ECX,self)
        preserved={UC_X86_REG_EBX:0x23456789,UC_X86_REG_EDI:0x34567890,UC_X86_REG_ESI:0x456789ab,UC_X86_REG_EBP:0x56789abc}
        for reg,val in preserved.items():uc.reg_write(reg,val)
        events=[]
        def ret(pop=0,eax=None):
            sp=uc.reg_read(UC_X86_REG_ESP);addr=struct.unpack('<I',uc.mem_read(sp,4))[0]
            if eax is not None:uc.reg_write(UC_X86_REG_EAX,eax)
            uc.reg_write(UC_X86_REG_ESP,sp+4+pop);uc.reg_write(UC_X86_REG_EIP,addr)
        def hook(uc,addr,size,unused):
            if addr==base+0x4dc30:ret(eax=player if dialog else 0)
            elif addr==0x30008000:ret(eax=0)
            elif addr==base+0x1ac8d0:ret(eax=surface)
            elif addr==base+0xf2600:events.append('hide');ret()
            elif addr in [0x30008100,0x30008110,0x30008120]:
                sp=uc.reg_read(UC_X86_REG_ESP)
                if addr==0x30008100:events.append(('color',struct.unpack('<I',uc.mem_read(sp+4,4))[0]));ret(4)
                else:events.append(('fill' if addr==0x30008110 else 'outline',struct.unpack('<4I',uc.mem_read(sp+4,16))));ret(16)
            elif addr==0x30008200:ret(eax=1)
        if dialog:w(player+0x170,cvvt);w(cvvt+0x18,0x30008200)
        uc.hook_add(UC_HOOK_CODE,hook)
        uc.emu_start(base+0xf1a10,0x3000f000,count=5000)
        assert uc.reg_read(UC_X86_REG_EIP)==0x3000f000
        assert uc.reg_read(UC_X86_REG_ESP)==stack+4
        for reg,val in preserved.items():assert uc.reg_read(reg)==val
        assert ((uc.reg_read(UC_X86_REG_FPSW)>>11)&7)==7,'Caller x87 stack changed'
        return events,bytes(uc.mem_read(self,0xa0))
    for fade in [0,.25,1]:
        old,state=run(False,fade);new,newstate=run(True,fade);assert state==newstate
        if fade:assert [e[0] for e in old]==['color','fill','color','outline'] and new==[]
        else:assert old==new==[]
        cases.append({'fade':fade,'original':old,'patched':new})
    for opts in [{'width':0},{'height':0},{'dialog':True},{'hidden':True},{'captions':False}]:
        old,state=run(False,1,**opts);new,newstate=run(True,1,**opts);assert old==new and state==newstate
        cases.append({'control':opts,'events':new})
    result={'passed':True,'plugin_hash':hashlib.sha256(Path(a.plugin).read_bytes()).hexdigest().upper(),'exports':exports,'cases':cases,'cleanliness':cleanliness,'native_load':native_load.stdout.strip()}
    if a.output:Path(a.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('PASS PE32/export, whole branch/epilogue, original cinematic fill+outline, unchanged inactive/dialog/disabled/empty paths, nonvolatile registers/stack/x87')
if __name__=='__main__':main()
