"""Additional exact-binary OS-failure regression; a failure stays a failure.

This does not modify the release. The fault is injected into its IAT in a
separate native test process operating only on synthetic/private fixtures.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from infra.core import ROOT, catalog, digest, need, read_json, require, run
from infra.native import compile_c, environment, scratch
from infra.release import members


def probe(mod,config):
    info=catalog()['mods'][mod]
    with tempfile.TemporaryDirectory(prefix='vtmb-fault-') as td:
        work=Path(td);src=scratch(work);code=src/'mods'/mod
        candidate=work/info['filename']
        candidate.write_bytes(members(Path(need(config,'releases'))/info['archive'])['Bin/loader/'+info['filename']])
        before=digest(candidate)
        require(before==info['plugin_sha256'],'Fault probe input is not the frozen current release')
        existing=(code/'tests/exact_harness.c').read_text(encoding='utf-8').split('int main(')[0]
        if mod=='console':
            setup='engine=VirtualAlloc(NULL,0x1400000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);ui=VirtualAlloc(NULL,0x80000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);check(engine&&ui,"fixture allocation");fixtures(); fail_at=0; h=(HMODULE)0; open_plugin(argv[1]); h=plugin; sitep=engine+0x10dc10;'
            callback='loaded_gameui';length=6
        else:
            setup='server=map_image(argv[2]); '+('client=map_image(argv[3]);' if mod=='protean' else 'engine=map_image(argv[3]);')+' h=open_plugin(argv[1]); sitep=server+'+('0x16c558;' if mod=='protean' else '0x16c5be;')
            callback='loaded_vampire';length=6
        tail='''
static int failed_flushes;
static BOOL WINAPI always_fail_flush(HANDLE p,LPCVOID a,SIZE_T n){(void)p;(void)a;(void)n;failed_flushes++;return FALSE;}
int main(int argc,char **argv){HMODULE h;uint8_t *sitep;uint8_t old[6];if(argc<2)return 2;
'''+setup+f'''
memcpy(old,sitep,{length});imports(h,"FlushInstructionCache",always_fail_flush);
((void(__cdecl *)(void))GetProcAddress(h,"{callback}"))();
if(!failed_flushes){{fprintf(stderr,"Fault not exercised\\n");return 2;}}
if(memcmp(old,sitep,{length})){{fprintf(stderr,"FAIL cache-flush refusal: final release leaves installed hook after injected failure (%d failed flushes)\\n",failed_flushes);return 1;}}
puts("PASS cache-flush failure refuses/rolls back hook");return 0;}}
'''
        source=code/'tests/cache_flush_probe.c';source.write_text(existing+tail,encoding='utf-8')
        exe=work/'probe.exe';env=environment(config,work)
        compile_c(need(config,'zig'),source,exe,env,['-Wno-unused-function','-Wno-unused-variable'])
        game=Path(need(config,'game_root'))
        for relative,pin in catalog()['native_modules'].items():
            require((game/relative).is_file() and digest(game/relative)==pin,'Fault probe requires supported native fixture: '+relative)
        args=[str(exe),str(candidate),str(game/'Vampire/dlls/vampire.dll'),str(game/('Vampire/cl_dlls/client.dll' if mod=='protean' else 'Bin/engine.dll'))]
        p=subprocess.run(args,capture_output=True,text=True,timeout=90)
        require(digest(candidate)==before,'Fault probe changed candidate file')
        observed=p.stdout+p.stderr
        status='PASS' if p.returncode==0 else 'FAIL' if p.returncode==1 and 'FAIL cache-flush refusal:' in observed else 'BLOCKED'
        return {'status':status,'returncode':p.returncode,'sha256':before,'observed':observed,'expected':'A failed cache flush must not be reported as certified successful hook installation','scope':'OS fault injection in separate test process; no game execution or release modification'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--mod',choices=['console','protean','frenzy'],required=True);p.add_argument('--output',required=True);a=p.parse_args()
    from infra.core import atomic_json
    result=probe(a.mod,read_json(a.config));atomic_json(a.output,result);print(result['status'],result['observed']);sys.exit(0 if result['status']=='PASS' else 1)
