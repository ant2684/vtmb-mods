"""Verify finalized delivery bytes; fixtures and evidence stay outside payload."""
import argparse,concurrent.futures,hashlib,json,os,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
KEYS=['ConsolePauseFix','SubtitlePauseRadioFix','HistoryStatResetFix','ContainerStackFix','ContainerInputGuard','FlamethrowerDamageNumbers','CastingAnimationCleanup','HUDIndicatorsFix']
ap=argparse.ArgumentParser();ap.add_argument('--zig',type=Path,required=True);ap.add_argument('--game',type=Path,required=True);ap.add_argument('--plugin',type=Path,required=True);ap.add_argument('--guard',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(out/'zig-global'),ZIG_LOCAL_CACHE_DIR=str(out/'zig-local'))
plugin=a.plugin.resolve();before=hashlib.sha256(plugin.read_bytes()).hexdigest();game=a.game.resolve()
guard=a.guard.resolve();guard_hash=hashlib.sha256(guard.read_bytes()).hexdigest()
paths=[game/'Bin/engine.dll',game/'Vampire/cl_dlls/client.dll',game/'Vampire/dlls/vampire.dll',game/'Vampire/cl_dlls/GameUI.dll']
fixtures={name:HERE/'tests'/(name+'.c') for name in ['configuration','container_input','hud_side','hud_victim']}
fixtures.update({p.stem:p for p in (HERE/'tests/legacy').glob('*.c')})
def compile_one(item):
 name,source=item;exe=out/(name+'.exe')
 r=subprocess.run([str(a.zig),'cc','-target','x86-windows-gnu','-O2','-g0','-Wall','-Wextra','-Werror','-I',str(HERE/'_support'),str(source),'-o',str(exe)],env=env,capture_output=True,text=True)
 (out/(name+'.compile.txt')).write_bytes((r.stdout+r.stderr).encode());assert r.returncode==0,(name,r.stderr)
 return name,exe
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:exes=dict(pool.map(compile_one,fixtures.items()))
print('Compiled',len(exes),'native fixtures',flush=True)
results=[]
def run(name,arguments,label):
 started=time.monotonic();r=subprocess.run([str(exes[name]),*[str(x) for x in arguments]],capture_output=True,text=True,timeout=90)
 row={'label':label,'fixture':name,'passed':r.returncode==0,'returncode':r.returncode,'output':r.stdout+r.stderr,'seconds':round(time.monotonic()-started,3)}
 if not row['passed']:(out/(label.replace('/','_')+'.failure.json')).write_bytes((json.dumps(row,indent=2)+'\n').encode())
 return row
matrix=[(m,-1,False) for m in range(256)]+[(255,i,False) for i in range(8)]+[(m,-1,True) for m in [0,1,2,4,8,16,32,64,128,255]]
def configuration(item):
 mask,invalid,reverse=item
 return run('configuration',[plugin,*paths,mask,invalid,*(['reverse'] if reverse else [])],f'config-{mask}-{invalid}-{int(reverse)}')
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for i,row in enumerate(pool.map(configuration,matrix)):
  results.append(row)
  if not row['passed']:
   (out/'results.json').write_bytes((json.dumps(results,indent=2)+'\n').encode());raise RuntimeError(row)
  if (i+1)%32==0:print('Configuration cases',i+1,'PASS',flush=True)
print('Configuration masks/invalid/order:',len(matrix),'PASS',flush=True)
for kind,fault in [(0,0),*[(0,i) for i in range(1,6)],*[(1,i) for i in range(1,4)],(2,0),(3,0)]:
 row=run('container_input',[plugin,paths[1],fault,kind],f'input-{kind}-{fault}');results.append(row);assert row['passed'],row
print('Exact input behavior, refusal, OS faults and helper lifetime PASS',flush=True)
for name,case in [('hud_side','normal'),('hud_side','disabled'),('hud_victim','normal')]:
 row=run(name,[plugin,paths[1],case],name+'-'+case);results.append(row);assert row['passed'],row
ini=out/'Bin/loader/ant2684-fixes-adjustments.ini';ini.parent.mkdir(parents=True,exist_ok=True);assert not ini.exists(),'Use a fresh test output'
try:
 for group,name,args in [
  (0,'console_exact',[plugin]),(3,'container_exact',[plugin,paths[1],paths[2],out/'container-certificate.json']),
  (5,'flame_exact',[plugin,paths[2],out/'flame-certificate.json']),
  (6,'cast_exact',[plugin,paths[2]])]:
  ini.write_bytes(('[Fixes]\n'+''.join(key+'='+str(int(i==group))+'\n' for i,key in enumerate(KEYS))).encode())
  row=run(name,args,name);results.append(row);assert row['passed'],row
  print(name,'PASS',flush=True)
 guard_ini=ini.with_name('vtmb-loading-input-guard.ini')
 assert not guard_ini.exists()
 guard_ini.write_bytes(b'[Fixes]\nLoadingInputGuard=0\n')
 row=run('loading_exact',[guard,paths[0],paths[1],'disabled'],'loading-disabled');results.append(row);assert row['passed'],row
 guard_ini.unlink()
 for fault in ['ok','signature','iat',*[str(i) for i in range(1,18)]]:
  row=run('loading_exact',[guard,paths[0],paths[1],fault],'loading-'+fault);results.append(row);assert row['passed'],row
 print('loading_exact:20 cases PASS',flush=True)
 peer=game/'Bin/loader/vtmb-dialogue-mouse.vtm'
 if peer.exists():
  assert hashlib.sha256(peer.read_bytes()).hexdigest()=='975f4f5eb056bff0e70a2e22bd848b4199d9ed0f1a561d117e4f18bd346403eb','Reviewed dialogue-mouse identity required for coexistence fixture'
  for mode in ['dialogue','dialogue-code','dialogue-owner','dialogue-target','dialogue-trampoline','dialogue-version','dialogue-return']:
   row=run('loading_exact',[guard,paths[0],paths[1],mode,peer],mode);results.append(row);assert row['passed'],row
  print('Reviewed dialogue-mouse forwarding and six mismatches PASS',flush=True)

 row=run('subtitle_native',[],'subtitle_native');results.append(row);assert row['passed'],row
finally:
 if ini.exists():ini.unlink()
receipt={'passed':all(r['passed'] for r in results),'plugin_sha256':before,'plugin_unchanged':hashlib.sha256(plugin.read_bytes()).hexdigest()==before,
 'guard_sha256':guard_hash,'guard_unchanged':hashlib.sha256(guard.read_bytes()).hexdigest()==guard_hash,
 'hud_integration_passed':True,'case_count':len(results),'configuration_cases':len(matrix),'results':results,
 'scope':'Exact unified VTM configuration/native fixtures; subtitle algorithm source fixture is supplementary. Not gameplay acceptance.'}
assert receipt['plugin_unchanged'] and receipt['guard_unchanged']
(out/'results.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode())
print(json.dumps({k:v for k,v in receipt.items() if k!='results'}),flush=True)
