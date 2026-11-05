"""Bounded integration check; avoids repeating the historical full game matrix."""
from pathlib import Path
import argparse,sys,os,subprocess,json,hashlib,concurrent.futures
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser()
for key in ['zig','deps','game','plugin','guard','out']:ap.add_argument('--'+key,type=Path,required=True)
a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);sys.path[:0]=[str(a.deps),str(HERE/'_support')]
from clean_pe import clean
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plugin=a.plugin.resolve();guard=a.guard.resolve();before=sha(plugin);guard_hash=sha(guard);env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'zig-global'),ZIG_LOCAL_CACHE_DIR=str(out/'zig-local'))
def compile(name):
 exe=out/(name+'.exe');subprocess.run([str(a.zig),'cc','-target','x86-windows-gnu','-O2','-g0','-Wall','-Wextra','-Werror','-I',str(HERE/'_support'),str(HERE/'tests'/(name+'.c')),'-o',str(exe)],env=env,check=True);return name,exe
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:exes=dict(pool.map(compile,['configuration','hud_side','hud_victim']))
paths=[a.game/'Bin/engine.dll',a.game/'Vampire/cl_dlls/client.dll',a.game/'Vampire/dlls/vampire.dll',a.game/'Vampire/cl_dlls/GameUI.dll'];rows=[]
def run(name,args,label):
 r=subprocess.run([str(exes[name]),*[str(x) for x in args]],capture_output=True,text=True,timeout=25);row={'label':label,'passed':r.returncode==0,'output':r.stdout+r.stderr};rows.append(row);(out/'progress.json').write_text(json.dumps(rows,indent=2));print(row,flush=True);assert r.returncode==0,row
for mask,invalid,reverse in [(0,-1,False),(127,-1,False),(128,-1,False),(255,-1,False),(255,7,True)]:run('configuration',[plugin,*paths,mask,invalid,*(['reverse'] if reverse else [])],f'configuration-{mask}-{invalid}-{reverse}')
for name,case in [('hud_side','normal'),('hud_side','disabled'),('hud_victim','normal')]:run(name,[plugin,paths[1],case],name+'-'+case)
receipt=clean(plugin,['loaded_engine','loaded_client','loaded_gameui','loaded_vampire','loaded_server','casting_cleanup_status','hud_fix_status','victim_bar_status'])
receipt.update(passed=True,hud_integration_passed=True,plugin_sha256=before,plugin_unchanged=sha(plugin)==before,guard_sha256=guard_hash,guard_unchanged=sha(guard)==guard_hash,case_count=len(rows),results=rows,scope='Focused HUD integration: central toggle, existing feature routing, exact HUD callbacks. Historical broader qualification separate.')
(out/'results.json').write_text(json.dumps(receipt,indent=2));print('PASS bounded integration',before)
