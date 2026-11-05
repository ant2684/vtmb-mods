"""Complete owned-process scenarios against the already staged clean delivery.

This runner never replaces a production binary, game DLL or video setting.
deployment.py owns one recovery transaction around the requested scenarios.
"""
import configparser
import argparse,ctypes as C,ctypes.wintypes as W,hashlib,json,os,re,shutil,struct,subprocess,sys,time,traceback
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('scenario',choices=['smoke','cast','history','container-baseline','container','radio','console','loading','protean','flame'])
ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--game',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
ap.add_argument('--seed',type=Path);ap.add_argument('--seed-sha');ap.add_argument('--zig',type=Path);ap.add_argument('--deps',type=Path,required=True);ap.add_argument('--baseline',type=Path);ap.add_argument('--log-files',action='store_true');ap.add_argument('--mask',type=int);ap.add_argument('--isolate-dialogue',action='store_true')
a=ap.parse_args();repo=a.repo.resolve();game=a.game.resolve();folder=a.out.resolve();folder.mkdir(parents=True,exist_ok=False)
if a.log_files:
 sys.stdout=(folder/'stdout.txt').open('w',buffering=1,encoding='utf-8');sys.stderr=(folder/'stderr.txt').open('w',buffering=1,encoding='utf-8')
sys.path[:0]=[str(repo),str(repo/'infra/common'),str(a.deps)]
from process_reader import Process,k
from observe import snapshot
import driver
from driver import u,INPUT,U,KI,MI
sys.path.insert(0,str(repo/'mods/protean-frenzy/tests/gameplay'))
import transaction as tr
class OwnedProcess:
 def __init__(self,pid):
  self.pid=pid;self.returncode=None
  k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
  self.h=k.OpenProcess(0x1000|0x100000,False,pid)
  if not self.h:raise C.WinError()
 def poll(self):
  code=W.DWORD();k.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)]
  if not k.GetExitCodeProcess(self.h,C.byref(code)):raise C.WinError()
  self.returncode=None if code.value==259 else code.value;return self.returncode
 def terminate(self):
  # Close only the PID returned by our launch; never enumerate/stop user games.
  r=subprocess.run(['taskkill','/PID',str(self.pid)],capture_output=True,text=True)
  if r.returncode and self.poll() is None:raise RuntimeError('Owned game did not accept ordinary close: '+r.stderr)
 def wait(self,seconds):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   if self.poll() is not None:return self.returncode
   time.sleep(.1)
  raise TimeoutError('Owned game exit timeout')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
def key(p,vk):
 hwnd=p.window();u.ShowWindow(hwnd,9);u.SetForegroundWindow(hwnd);time.sleep(.1)
 assert u.GetForegroundWindow()==hwnd,'Owned game is not foreground'
 event=INPUT(1,U(ki=KI(0,u.MapVirtualKeyW(vk,0),8,0,0)))
 try:assert u.SendInput(1,C.byref(event),C.sizeof(event))==1;time.sleep(.06)
 finally:event.value.ki.flags=10;assert u.SendInput(1,C.byref(event),C.sizeof(event))==1
 time.sleep(.15)
def process_receipt(p):
 ft=[W.FILETIME() for _ in range(4)];k.GetProcessTimes.argtypes=[W.HANDLE]+[C.POINTER(W.FILETIME)]*4
 assert k.GetProcessTimes(p.h,*[C.byref(v) for v in ft])
 return {'Id':p.pid,'Ticks':((ft[0].dwHighDateTime<<32)|ft[0].dwLowDateTime)+504911232000000000}
KEYS=['ConsolePauseFix','SubtitlePauseRadioFix','HistoryStatResetFix','ContainerStackFix','ContainerInputGuard','FlamethrowerDamageNumbers','LoadingInputGuard','CastingAnimationCleanup']
def options():
 config=configparser.ConfigParser();config.read([game/'Bin/loader/ant2684-fixes-adjustments.ini',game/'Bin/loader/vtmb-loading-input-guard.ini'])
 return {key:config.get('Fixes',key,fallback='1')=='1' for key in KEYS}
def verify_loaded(p):
 expected={f.name.lower():sha(f) for f in (game/'Bin/loader').glob('*.vtm') if not f.name.startswith('zz-vf-')}
 assert len(expected)==(8 if a.isolate_dialogue else 9),expected
 if a.isolate_dialogue:assert 'vtmb-dialogue-mouse.vtm' not in p.modules,'Diagnostic owner must actually be absent'
 p.refresh();actual={}
 for name,digest in expected.items():
  assert name in p.module_paths,('Clean plugin not loaded',name)
  path=p.module_paths[name];assert sha(path)==digest;actual[name]={'path':path,'sha256':digest,'base':p.modules[name]}
 vf=p.modules['ant2684-fixes-adjustments.vtm'];sv=p.modules['vampire.dll'];cl=p.modules['client.dll'];en=p.modules['engine.dll'];ui=p.modules['gameui.dll']
 # All optional groups must actually install, alongside the unchanged Protean.
 sites=[('console',en+0x10dc10,0xe9),('history',sv+0xd6dd8,0xe9),('container',cl+0x16dfa4,0xe9),
        ('input',cl+0x102150,0xe9),('loading',en+0xa38a0,0xe9),('casting',sv+0x3275cb,0xe8),
        ('protean_filter',cl+0x19da73,0xe9),('protean_pools',sv+0x8dac0,0xe9),('protean_inventory',sv+0x3daf,0xe9)]
 sites += [('subtitle_clock',en+0x1188b0,0xe8),('subtitle_pause',en+0x2d130,0xe8),('radio_tick',sv+0x22c807,0xe8),('radio_activate',sv+0x22c50f,0xe8),('radio_spawn',sv+0x22c360,0xe8),('radio_static',en+0x2b97b,0xe8)]
 enabled=options();groups={'console':0,'history':2,'container':3,'input':4,'loading':6,'casting':7}
 sites=[site for site in sites if site[0].startswith('protean_') or enabled[KEYS[groups.get(site[0],1)]]]

 values={name:p.read(at,5).hex() for name,at,_ in sites}
 import pefile
 pe=pefile.PE(str(game/'Bin/loader/ant2684-fixes-adjustments.vtm'));exports={e.name.decode():e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
 guard_base=p.modules['vtmb-loading-input-guard.vtm']
 guard_image=pefile.PE(str(game/'Bin/loader/vtmb-loading-input-guard.vtm'))
 guard_status=next(e.address for e in guard_image.DIRECTORY_ENTRY_EXPORT.symbols if e.name==b'loading_input_status')
 loading=struct.unpack('<3I',p.read(guard_base+guard_status,12));casting=p.u(vf+exports['casting_cleanup_status'])
 if enabled[KEYS[6]] and 'vtmb-dialogue-mouse.vtm' in p.modules:
  peer=p.modules['vtmb-dialogue-mouse.vtm']
  trampoline=p.u(peer+0x18b44)
  assert p.u(peer+0x18b20)==cl and trampoline,'Dialogue mouse native hook did not initialize'
  attack_site=cl+0x102270
  branch=p.read(attack_site,5)
  target=attack_site+5+struct.unpack_from('<i',branch,1)[0]
  assert branch[0]==0xe9 and guard_base<=target<guard_base+guard_image.OPTIONAL_HEADER.SizeOfImage
  assert p.read(trampoline,1)==b'\x8b','Dialogue mouse lost its native trampoline'
 result={'plugins':actual,'sites':values,'loading_status':loading,'casting_status':casting,'options':enabled,'dialogue_guard_chained':bool(enabled[KEYS[6]] and 'vtmb-dialogue-mouse.vtm' in p.modules)}
 reference=json.loads((repo/'mods/vtmb-fixes/loading-guard-reference.json').read_text())
 result['loading_sites']=[dict(h,actual=p.read(p.modules[h['module']+'.dll']+h['rva'],h['length']).hex()) for h in reference['hooks']]
 result['dispatch_pointer']=hex(p.u(en+reference['dispatch_iat']))
 result['dispatch_code']=p.read(p.u(en+reference['dispatch_iat']),32).hex()
 dump(folder/'loaded-clean-inputs.json',result)
 for name,at,opcode in sites:assert p.read(at,1)==bytes([opcode]),('Native site inactive',name,values[name])
 assert p.read(sv+0x3e3674,1)==bytes([0 if enabled[KEYS[5]] else 1]),'Flamethrower option mismatch'
 assert loading[1:]==(int(enabled[KEYS[6]]),0) and casting==int(enabled[KEYS[7]]),(loading,casting)
 return result
def player(p):
 sv=p.modules['vampire.dll'];table=p.u(sv+0x566458)
 if not table:return None
 _,pc,serial=struct.unpack('<3I',p.read(table+12,12))
 if not pc:return None
 if p.read(p.u(pc+0x11c),7)!=b'player\0':return None
 return pc,1|(serial<<13)
def wait_world(proc,p,continue_loading=True):
 deadline=time.monotonic()+70;enter_sent=0;last_enter=0;last_clock=None;last_console=0
 while time.monotonic()<deadline:
  assert proc.poll() is None,'Owned game exited before readiness'
  try:
   p.refresh();pc=player(p)
   if pc:
    en=p.modules['engine.dll'];sv=p.modules['vampire.dll'];plaque=p.u(en+0xb42318)
    now=p.f(p.u(sv+0x70b228)+12)
    state=snapshot(p);waiting=p.read(p.modules['vampire.exe']+0x3f32c,1)[0]
    advanced=last_clock is not None and state['client_time']>last_clock+.03
    last_clock=state['client_time']
    # A console used to issue load can remain visible because the loader's
    # wait loop consumes the earlier attempted close key. Close it only after
    # that loop has completed, then wait for native world/input readiness.
    obj=p.u(en+0x13064a8);dlg=p.u(obj+8) if obj and p.u(obj+4) else 0
    console_visible=bool(dlg and p.read(p.u(dlg+4)+0x42,1)[0])
    if not waiting and console_visible and time.monotonic()-last_console>1:
     key(p,0xc0);last_console=time.monotonic()
    cp=p.u(p.modules['client.dll']+0x27ba58);mouse=p.u(cp+0x28) if cp else 0
    if now>0 and not plaque and not waiting and advanced and not state['paused'] and not state['server_paused'] and state['menu_pause_depth']==0 and mouse==1:return pc
   if continue_loading and p.read(p.modules['vampire.exe']+0x3f32c,1)[0] and time.monotonic()-last_enter>3 and enter_sent<3:
    # Exercise the installed click-to-continue loading mode with a physical click.
    hwnd=p.window();u.ShowWindow(hwnd,9);u.SetForegroundWindow(hwnd);time.sleep(.1)
    assert u.GetForegroundWindow()==hwnd,'Own game is not foreground'
    try:assert u.SendInput(1,C.byref(INPUT(0,U(mi=MI(0,0,0,2,0,0)))),C.sizeof(INPUT))==1;time.sleep(.15)
    finally:assert u.SendInput(1,C.byref(INPUT(0,U(mi=MI(0,0,0,4,0,0)))),C.sizeof(INPUT))==1
    enter_sent+=1;last_enter=time.monotonic()
    dump(folder/'loading-continue-input.json',{'left_clicks':enter_sent,'reason':'Preserve and exercise existing loading click-to-continue mode'})
  except (OSError,RuntimeError,KeyError,ValueError):pass
  time.sleep(.15)
 raise RuntimeError('World did not become ready')

def main():
 assert not tr.running_games(),'User game is running'
 assert (game/'.vtmb-regression.lock').exists(),'Run inside the preserved task transaction'
 assert sha(game/'Bin/loader/ant2684-fixes-adjustments.vtm')=='2db0d54fee2eff63e79a7ac5307c0070f229b99ce4f2478987de598498137a9d'
 assert sha(game/'Bin/loader/vtmb-loading-input-guard.vtm')=='2f9b26347616c0cf1311b34e6cc58b091e24c6ee8c72f0c387bf726d44d3804b'
 global k
 before_video=tr.video_snapshot();proc=None;p=None;owned_seed=None;original_ini=None;original_guard_ini=None;isolated_plugin=None;result={'scenario':a.scenario,'passed':False}
 state=Path(json.loads((game/'.vtmb-regression.lock').read_text())['state'])
 preserved=json.loads((state/'transaction.json').read_text())['files']
 for rel,record in preserved.items():
  if rel.lower() in ['unofficial_patch\\cfg\\config.cfg','vampire\\cfg\\config.cfg']:
   original=state/'backup'/rel;assert sha(original)==record['sha256'];shutil.copy2(original,game/rel)
 if a.mask is not None or a.scenario=='container-baseline':
  mask=a.mask if a.mask is not None else 247;assert 0<=mask<256
  ini=game/'Bin/loader/ant2684-fixes-adjustments.ini';original_ini=ini.read_bytes()
  ini.write_bytes(('[Fixes]\n'+''.join(key+'='+str((mask>>i)&1)+'\n' for i,key in enumerate(KEYS) if i!=6)).encode())
  guard_ini=game/'Bin/loader/vtmb-loading-input-guard.ini';original_guard_ini=guard_ini.read_bytes()
  guard_ini.write_bytes(('[Fixes]\nLoadingInputGuard='+str((mask>>6)&1)+'\n').encode())
 stem='rc_vf_'+a.scenario.replace('-','_');args=[str(game/'Vampire.exe'),'-game','Unofficial_Patch','-dev','-novid']
 cfg=game/'Unofficial_Patch/cfg/vf_owned.cfg';cfg.write_bytes(b'developer 0\nbind F8 "vchargen_key 2"\n' if a.scenario=='history' else b'developer 0\nsv_cheats 1\ngod\nnotarget\nhideconsole\n')
 try:
  if a.isolate_dialogue:
   original=game/'Bin/loader/vtmb-dialogue-mouse.vtm';assert sha(original)=='975f4f5eb056bff0e70a2e22bd848b4199d9ed0f1a561d117e4f18bd346403eb'
   isolated_plugin=folder/'temporarily-disabled-dialogue-mouse.vtm';assert not isolated_plugin.exists()
   shutil.move(original,isolated_plugin)
   dump(folder/'diagnostic-isolation.json',{'temporary_absence':'vtmb-dialogue-mouse.vtm','sha256':sha(isolated_plugin),'scope':'Diagnostic control only; restore after owned process exits'})
  if a.seed:
   assert a.seed_sha and sha(a.seed).lower()==a.seed_sha.lower(),'Exact nominated seed required'
   target=game/'Unofficial_Patch/save'/(stem+'.sav');assert not target.exists();shutil.copy2(a.seed,target);owned_seed=target
   args+=['+load',stem]
  elif a.scenario=='radio':args+=['+map','sm_pawnshop_1']
  elif a.scenario=='history':pass
  else:raise RuntimeError('Scenario requires a nominated save')
  if a.scenario=='cast':
   source=(repo/'mods/casting-animation-cleanup/tests/casting_gameplay_bootstrap.c').read_text()
   source='#define CAST_TEST_LOG "'+(folder/'cast-events.jsonl').as_posix()+'"\n'+source
   c=folder/'bootstrap.c';c.write_bytes(source.encode());boot=folder/'bootstrap.vtm'
   env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(folder.parent/'zig-global'),ZIG_LOCAL_CACHE_DIR=str(folder.parent/'zig-local'))
   subprocess.run([str(a.zig),'cc','-target','x86-windows-gnu','-shared','-O2','-g0','-s',str(c),'-o',str(boot)],env=env,check=True)
   shutil.copy2(boot,game/'Bin/loader/zz-vf-casting-bootstrap.vtm')
   with cfg.open('ab') as f:f.write(('alias cycle_reload "load '+stem+'"\nalias cycle_quit "quit"\n').encode())
  if a.scenario=='flame':
   source='#define FLAME_TEST_LOG '+json.dumps((folder/'flame-queue.jsonl').as_posix())+'\n'+Path(__file__).with_name('flame_bootstrap.c').read_text()
   src=folder/'flame-bootstrap.c';src.write_bytes(source.encode());boot=folder/'flame-bootstrap.vtm'
   env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(folder.parent/'zig-global'),ZIG_LOCAL_CACHE_DIR=str(folder.parent/'zig-local'))
   subprocess.run([str(a.zig),'cc','-target','x86-windows-gnu','-shared','-O2','-g0','-s',str(src),'-o',str(boot)],env=env,check=True)
   shutil.copy2(boot,game/'Bin/loader/zz-vf-flame-bootstrap.vtm')
  if a.scenario=='history':
   source='#define WIZARD_TEST_LOG '+json.dumps((folder/'wizard-events.jsonl').as_posix())+'\n'+Path(__file__).with_name('wizard_bootstrap.c').read_text()
   src=folder/'wizard-bootstrap.c';src.write_bytes(source.encode());wizard=folder/'wizard-bootstrap.vtm'
   env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(folder.parent/'zig-global'),ZIG_LOCAL_CACHE_DIR=str(folder.parent/'zig-local'))
   subprocess.run([str(a.zig),'cc','-target','x86-windows-gnu','-shared','-O2','-g0','-s',str(src),'-o',str(wizard),'-luser32'],env=env,check=True)
   shutil.copy2(wizard,game/'Bin/loader/zz-vf-wizard-bootstrap.vtm')
  args+=['+exec','vf_owned.cfg']
  launch={'GameRoot':str(game),'Arguments':args[1:],'Save':stem,'SaveHash':sha(a.seed) if a.seed else None}
  dump(folder/'launch.json',launch)
  # Direct CreateProcess has no shell or elevation fallback. Error740 creates
  # no game process. The owner removed the incompatible Windows flags.
  child=subprocess.Popen(args,cwd=str(game))
  proc=OwnedProcess(child.pid);proc.child=child
  dump(folder/'launched-process.json',{'Id':proc.pid,'Launch':'direct CreateProcess, no shell/elevation fallback'})
  print('OWNED',proc.pid,a.scenario,folder,flush=True)
  import pefile
  image=pefile.PE(str(game/'Bin/loader/vtmb-loading-input-guard.vtm'))
  ready_offset=next(e.address for e in image.DIRECTORY_ENTRY_EXPORT.symbols if e.name==b'loading_input_status')
  deadline=time.monotonic()+40
  while time.monotonic()<deadline:
   try:
    p=Process(proc.pid);p.refresh()
    if all(name in p.modules for name in ['gameui.dll','client.dll','vampire.dll']):
     assert p.u(p.modules['vtmb-loading-input-guard.vtm']+ready_offset+4)==int(options()[KEYS[6]]),'Wait for native loader callbacks, not only mapped DLLs'
     exe=p.modules['vampire.exe'];dump(folder/'loader-context.json',{'modules':p.module_paths,'loader_windows_major':p.u(exe+0x3ee28),'check_windows':p.u(exe+0x3efd8)})
     if 'ant2684-fixes-adjustments.vtm' not in p.modules:raise RuntimeError('Loader initialized without unified VTM; inspect loader-context and loader.log')
     p.window();break
   except (OSError,RuntimeError,KeyError,AssertionError):
    if p:k.CloseHandle(p.h);p=None
    assert proc.poll() is None,'Owned game exited at startup';time.sleep(.2)
  assert p is not None,'Owned modules/window not initialized'
  dump(folder/'process.json',process_receipt(p))
  if a.scenario=='cast':
   wait_world(proc,p)
   result['coexistence']=verify_loaded(p)
   until=time.monotonic()+105;last_continue=0
   while proc.poll() is None and time.monotonic()<until:
    p.refresh()
    if time.monotonic()-last_continue>12:
     try:
      en=p.modules['engine.dll']
      if p.read(p.modules['vampire.exe']+0x3f32c,1)[0]:key(p,0x0d);last_continue=time.monotonic()
     except (OSError,RuntimeError,KeyError):pass
    time.sleep(.08)
   assert proc.poll() is not None,'Cast scenario did not finish'
   events=[json.loads(x) for x in (folder/'cast-events.jsonl').read_text().splitlines()]
   by={e['event']:e for e in events}
   assert by['normal_expired']['flag']==0 and by['before_reload']['flag']==1
   assert by['after_reload']['flag']==by['settled_after_reload']['flag']==0
   assert by['before_reload']['handle']!=by['after_reload']['handle']
   assert by['fixed_finished']['flag']==0
   result['events']=events;result['passed']=True
  else:
   if a.scenario!='history':wait_world(proc,p)
   result['coexistence']=verify_loaded(p)
   if a.scenario=='smoke':
    d=driver.Driver(folder)
    if d.snap()['console']['visible']:d.click_x()
    if d.snap()['menu']['visible']:d.key(0x1b)
    wait_world(proc,p)
    before=d.snap();d.delay(.8);after=d.snap()
    result.update(before=before,after=after)
    dump(folder/'smoke-world-samples.json',{'before':before,'after':after})
    assert after['client_time']>before['client_time'] and not after['server_paused']
    result['passed']=True
   else:
    import scenarios
    observed=scenarios.run({'repo':repo,'game':game,'folder':folder,'scenario':a.scenario,'seed':a.seed,'baseline':a.baseline,'sha':sha,'stem':stem,'proc':proc,'p':p,'wait_world':wait_world,'key':key})
    assert observed.get('status')=='PASS' or observed.get('passed') or observed.get('result')=='PASS',observed
    result.update(passed=True,observed=observed)
 except BaseException as error:
  dump(folder/'scenario-first-error.json',{'error':repr(error),'traceback':traceback.format_exc()})
  raise
 finally:
  if p:k.CloseHandle(p.h)
  if proc and proc.poll() is None:
   proc.terminate()
   try:proc.wait(10)
   except TimeoutError:
    assert hasattr(proc,'child'),'Only a direct task child may be forcibly stopped'
    proc.child.terminate();proc.wait(5)
  if proc:
   k.CloseHandle(proc.h)
   if hasattr(proc,'child'):
    proc.child.wait(timeout=1);proc.child._handle.Close()
  if a.scenario=='cast':
   boot=game/'Bin/loader/zz-vf-casting-bootstrap.vtm'
   for retry in range(50):
    try:
     if boot.exists():boot.unlink()
     break
    except PermissionError:
     if retry==49:raise
     time.sleep(.1)
  if a.scenario=='history':
   wizard=game/'Bin/loader/zz-vf-wizard-bootstrap.vtm'
   for retry in range(50):
    try:
     if wizard.exists():wizard.unlink()
     break
    except PermissionError:
     if retry==49:raise
     time.sleep(.1)
  if a.scenario=='flame':
   helper=game/'Bin/loader/zz-vf-flame-bootstrap.vtm'
   for retry in range(50):
    try:
     if helper.exists():helper.unlink()
     break
    except PermissionError:
     if retry==49:raise
     time.sleep(.1)
  if isolated_plugin is not None and isolated_plugin.exists():
   assert not (game/'Bin/loader/vtmb-dialogue-mouse.vtm').exists();shutil.move(isolated_plugin,game/'Bin/loader/vtmb-dialogue-mouse.vtm')
  if original_guard_ini is not None:(game/'Bin/loader/vtmb-loading-input-guard.ini').write_bytes(original_guard_ini)
  if original_ini is not None:(game/'Bin/loader/ant2684-fixes-adjustments.ini').write_bytes(original_ini)
  if owned_seed and owned_seed.exists():
   if sha(owned_seed)!=sha(a.seed):shutil.copy2(owned_seed,folder/'modified-task-seed.sav')
   owned_seed.unlink()
  result['video_unchanged']=tr.video_snapshot()==before_video
  dump(folder/'result.json',result)
 assert result['video_unchanged'],'Video settings changed'
 print('PASS',a.scenario,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as error:
  dump(folder/'first-error.json',{'error':repr(error),'traceback':traceback.format_exc()});raise
