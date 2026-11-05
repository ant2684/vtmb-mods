"""Build one clean VTM from the approved original components; no game writes."""
import argparse,hashlib,json,os,re,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
KEYS=['ConsolePauseFix','SubtitlePauseRadioFix','HistoryStatResetFix','ContainerStackFix','ContainerInputGuard','FlamethrowerDamageNumbers','CastingAnimationCleanup','HUDIndicatorsFix']
EXPORTS=['loaded_engine','loaded_client','loaded_gameui','loaded_vampire','loaded_server','casting_cleanup_status','hud_fix_status','victim_bar_status']
ap=argparse.ArgumentParser();ap.add_argument('--zig',type=Path,required=True);ap.add_argument('--deps',type=Path,required=True);ap.add_argument('--game',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
sys.path[:0]=[str(a.deps),str(HERE/'_support')]
import pefile
from finalize_pe import finalize
from clean_pe import clean
out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
assert not (out/'accepted.json').exists(),'Final bytes already sealed; use a fresh output for changed source'
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'zig-global'),ZIG_LOCAL_CACHE_DIR=str(out/'zig-local'))
reference=json.loads((HERE/'loading-guard-reference.json').read_text())
pes={}
for key,rel in [('engine','Bin/engine.dll'),('client','Vampire/cl_dlls/client.dll')]:
    p=a.game/rel;assert hashlib.sha256(p.read_bytes()).hexdigest()==reference['modules'][key]
    pes[key]=pefile.PE(str(p))
header=[];setup=['memset(hooks,0,sizeof(Hook)*5);']
for key,pe in pes.items():header+=['#define '+key.upper()+'_TIMESTAMP 0x%xu'%pe.FILE_HEADER.TimeDateStamp,'#define '+key.upper()+'_SIZE 0x%xu'%pe.OPTIONAL_HEADER.SizeOfImage]
header.append('#define DISPATCH_IAT 0x%xu'%reference['dispatch_iat'])
specs=[('key_event','native_key'),('begin_load','native_begin'),('end_load','native_end'),('attack_down','native_down'),('get_bits','native_bits')]
for i,(h,(replacement,original)) in enumerate(zip(reference['hooks'],specs)):
    key=h['module'];pe=pes[key];expected=bytes.fromhex(h['signature']);assert pe.get_data(h['rva'],h['length'])==expected
    header.append('static const B guard_sig_%d[]={%s};'%(i,','.join('0x%02x'%b for b in expected)))
    relocations=[e.rva-h['rva'] for b in pe.DIRECTORY_ENTRY_BASERELOC for e in b.entries
                 if e.type==3 and h['rva']<=e.rva<=h['rva']+h['length']-4]
    header.append('static const B guard_reloc_%d[]={%s};'%(i,','.join(map(str,relocations+[255]))))
    setup.append('hooks[%d]=(Hook){.module=%s,.preferred=0x%xu,.rva=0x%xu,.length=%d,.call_offset=0x%xu,.signature=guard_sig_%d,.relocations=guard_reloc_%d,.replacement=%s,.original=(void **)&%s};'%(i,key,pe.OPTIONAL_HEADER.ImageBase,h['rva'],h['length'],h['call_offset'],i,i,replacement,original))
header.append('static void setup_hooks(Hook *hooks){'+''.join(setup)+'}')
(out/'loading_guard_signatures.inc').write_bytes(('\n'.join(header)+'\n').encode())
# HUD signatures use the original input and explicit build-time relocations.
hud_anchors={
 'hud_side':[(0x79440,0x22),(0x79467,2),(0x79470,6),(0x7a740,0x48),(0x7a810,0x30),(0x59250,12),(0x4d300,0x89)],
 'hud_victim':[(0x503d0,0x22),(0x50560,0x16),(0x5057c,4),(0x507a1,0x44),(0x507ed,0x38),(0x50871,0x79),(0x508ee,0x2c)]}
for component,anchors in hud_anchors.items():
 pe=pes['client'];lines=['#define CLIENT_TIMESTAMP 0x%xu'%pe.FILE_HEADER.TimeDateStamp,'#define CLIENT_SIZE 0x%xu'%pe.OPTIONAL_HEADER.SizeOfImage]
 for i,(rva,n) in enumerate(anchors):
  data=pe.get_data(rva,n);relocs={e.rva-rva for b in pe.DIRECTORY_ENTRY_BASERELOC for e in b.entries if e.type==3 and rva<=e.rva<=rva+n-4}
  lines.append('static const B anchor_%d[]={%s};'%(i,','.join(str(x) for x in data)))
  lines.append('static int check_%d(B *m){unsigned j;for(j=0;j<%d;j++){'%(i,n))
  for off in sorted(relocs):lines.append('if(j==%d){U want=*(const U *)(anchor_%d+j)+(U)(uintptr_t)m-0x%xu;if(rd(m,0x%x + j)!=want)return 0;j+=3;continue;}'%(off,i,pe.OPTIONAL_HEADER.ImageBase,rva))
  lines.append('if(m[0x%x + j]!=anchor_%d[j])return 0;}return 1;}'%(rva,i))
 lines.append('static int anchors_match(B *m){return '+'&&'.join('check_%d(m)'%i for i in range(len(anchors)))+';}')
 (out/(component+'_signatures.inc')).write_bytes(('\n'.join(lines)+'\n').encode())
objects=[];source_manifest={}
for component in ['console','subtitle','history','container','flame','cast','input','hud_side','hud_victim']:
    if component.startswith('hud_'):src=HERE/'native/hud'/(component+'.c')
    elif component=='input':src=HERE/'native/container_input.c'
    else:src=next((HERE/'native'/component).glob('*.c'))
    raw=src.read_text();macros=[]
    for name in ['loaded_engine','loaded_gameui','loaded_client','loaded_vampire','loaded_server','DllMain']:
        macros.append('#define '+name+' vf_'+component+'_'+name)
    # Callbacks become internal functions; retain the two existing production
    # status exports used to distinguish installation/refusal from active fixes.
    raw=re.sub(r'__declspec\(dllexport\)(\s+void\s+loaded_)',r'\1',raw)
    # The subtitle callbacks live in an included original header. Redefine
    # dllexport only for that component by generating its one header copy.
    include=out/('include-'+component);include.mkdir(exist_ok=True)
    if src.parent.is_dir():
        for h in src.parent.glob('*.h'):
            text=h.read_text();text=re.sub(r'__declspec\(dllexport\)(\s+void\s+loaded_)',r'\1',text)
            (include/h.name).write_bytes(text.encode())
    generated=out/(component+'.c');generated.write_bytes(('\n'.join(macros)+'\n'+raw).encode())
    obj=out/(component+'.o')
    subprocess.run([str(a.zig),'cc','-target','x86-windows-gnu','-O2','-g0','-Wall','-Wextra','-Werror','-I',str(include),'-I',str(out),'-c',str(generated),'-o',str(obj)],env=env,check=True)
    objects.append(obj);source_manifest[src.relative_to(HERE).as_posix()]=hashlib.sha256(src.read_bytes()).hexdigest()
obj=out/'runtime.o'
subprocess.run([str(a.zig),'cc','-target','x86-windows-gnu','-O2','-g0','-Wall','-Wextra','-Werror','-c',str(HERE/'native/runtime.c'),'-o',str(obj)],env=env,check=True);objects.append(obj)
plugin=out/'ant2684-fixes-adjustments.vtm'
subprocess.run([str(a.zig),'cc','-target','x86-windows-gnu','-shared','-s','-Wl,--build-id=none',*[str(p) for p in objects],'-o',str(plugin)],env=env,check=True)
finalize(plugin)
# Advanced EXE has six historical size exclusions. Match the established
# release finalizer policy with real PE-section padding if necessary.
blocked={0x13400,0x12800,0x12a00,0x12c00,0x12e00,0x13000}
if plugin.stat().st_size in blocked:
    raise RuntimeError('Loader size exclusion: adjust linker section alignment before sealing')
source_manifest={p.relative_to(HERE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((HERE/'native').rglob('*')) if p.is_file() and p.suffix in ['.c','.h','.inc']}
guard=out/'vtmb-loading-input-guard.vtm'
subprocess.run([str(a.zig),'cc','-target','x86-windows-gnu','-O2','-g0','-Wall','-Wextra','-Werror',
                '-shared','-s','-Wl,--build-id=none','-I',str(out),
                str(HERE/'native/loading/loading_input_guard.c'),'-o',str(guard)],env=env,check=True)
finalize(guard)
assert guard.stat().st_size not in blocked,'Loader size exclusion for standalone guard'
guard_receipt=clean(guard,['loaded_engine','loaded_client','loaded_gameui','loaded_vampire','loading_input_status'])
receipt=clean(plugin,EXPORTS)
receipt['guard']=guard_receipt
receipt.update(keys=KEYS,source_sha256=source_manifest,scope='Clean build only; exact native and gameplay verification required')
(out/'build.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode())
print(json.dumps(receipt,indent=2))
