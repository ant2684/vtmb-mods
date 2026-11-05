"""Short integrated startup check; restores all temporary writes."""
from pathlib import Path
import argparse,sys,subprocess,os,time,json,hashlib,shutil,re,struct,traceback
ap=argparse.ArgumentParser()
for key in ['repo','game','save','zig','out','deps']:ap.add_argument('--'+key,type=Path,required=True)
a=ap.parse_args();G=a.game.resolve();O=a.out.resolve();O.mkdir(parents=True,exist_ok=False)
sys.path[:0]=[str(a.deps),str(a.repo/'infra/common'),str(a.repo/'mods/protean-frenzy/tests/gameplay'),str(a.repo/'mods/hud-indicators/tests')]
import transaction as tr
from process_reader import Process,k
from observer import hud
def dump(name,data):(O/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not tr.running_games(),'User game running'
request=O/'request.txt';response=O/'response.jsonl';receipt=O/'complete.txt';request.write_bytes(b'0\n')
source='#define HUD_REQUEST '+json.dumps(request.as_posix())+'\n#define HUD_RESPONSE '+json.dumps(response.as_posix())+'\n'+Path(__file__).with_name('hud_smoke_controller.c').read_text()
(O/'controller.c').write_text(source);controller=O/'controller.vtm';env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(O/'cache-global'),ZIG_LOCAL_CACHE_DIR=str(O/'cache-local'))
subprocess.run([str(a.zig),'cc','-target','x86-windows-gnu','-O2','-g0','-shared','-s',str(O/'controller.c'),'-o',str(controller)],env=env,check=True)
tx=tr.Transaction(G,O);tx.begin();child=None;p=None;seq=0;result={'passed':False,'plugin_sha256':sha(G/'Bin/loader/ant2684-fixes-adjustments.vtm')}
for rel in ['Bin/loader/zz-hud-owned-controller.vtm','Bin/loader/loader.ini','Loader.log','Unofficial_Patch/stats.txt','Unofficial_Patch/vidcfg.bin']:
 tx.single.append(rel);path=G/rel
 if path.is_file():
  dest=O/'backup'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);tx.records[rel]={'sha256':sha(path),'mtime_ns':path.stat().st_mtime_ns}
for tree in ['Unofficial_Patch/materials/hud','Unofficial_Patch/materials/interface/charactermaintenance','Unofficial_Patch/sound/interface/infobar','Unofficial_Patch/screenshots','Vampire/screenshots','screenshots']:
 tx.trees.append(tree);tx.directories[tree]=[str(p.relative_to(G)) for p in (G/tree).rglob('*') if p.is_dir()]
 for path in (G/tree).rglob('*'):
  if path.is_file():
   rel=str(path.relative_to(G));dest=O/'backup'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);tx.records[rel]={'sha256':sha(path),'mtime_ns':path.stat().st_mtime_ns}
dump('transaction.json',dict(game=str(G),trees=tx.trees,single=tx.single,files=tx.records,directories=tx.directories))
def command(code,console=False):
 global seq
 seq+=1;body="import sys\nsys.stderr=open("+repr((O/'python-errors.txt').as_posix())+",'a',0)\n"+code+"\nf=open("+repr(receipt.as_posix())+",'a');f.write("+repr(str(seq)+'\n')+");f.close()\n"
 if console:body='VB_CONSOLE\n'+code+'\n'
 pending=request.with_suffix('.pending');pending.write_bytes((str(seq)+'\n'+body).encode());os.replace(pending,request)
 end=time.monotonic()+8
 while time.monotonic()<end:
  assert child.poll() is None,'Owned game exited'
  if console and response.exists():
   matches=[json.loads(x) for x in response.read_text().splitlines() if x.strip()];matches=[x for x in matches if x['sequence']==seq and x['pid']==child.pid]
   if matches:assert matches[-1]['result']==0,matches[-1];return
  if receipt.exists() and str(seq) in receipt.read_text().splitlines():return
  time.sleep(.05)
 raise RuntimeError('Command did not complete: '+code+' '+((O/'python-errors.txt').read_text(errors='replace') if (O/'python-errors.txt').exists() else ''))
def snapshot():
 r=hud(p);c=p.modules['client.dll'];pl=p.u(c+0x4a0d50);node=p.u(p.u(c+0x3eec98)+0x170);seen=set()
 while node and node not in seen:
  seen.add(node);obj=p.u(node)-0x170
  if p.u(obj)==c+0x228784:
   r['feed']={'visible':p.read(obj+0x1a4,1)[0],'blood':p.u(c+0x3ede94),'maximum':p.u(obj+0x1ac),'percent':p.u(obj+0x1a8),'interpolation':p.u(c+0x3ede90),'epoch':p.f(obj+0x1b0)};break
  node=p.u(node+4)
 if pl:r['feeding']={'drinking':p.read(pl+0x14d4,1)[0],'duration':p.f(pl+0x14d0),'maximum':p.u(pl+0x14cc)}
 return r
def observe(label,seconds):
 rows=[];end=time.monotonic()+seconds
 while time.monotonic()<end:rows.append(snapshot());time.sleep(.04)
 dump(label+'.json',rows);return rows
def ready():
 global p
 end=time.monotonic()+55;last=None;stable=0
 while time.monotonic()<end:
  assert child.poll() is None
  try:
   if p is None:p=Process(child.pid)
   p.refresh();r=snapshot();delta=r['time']-last if last is not None else 0;last=r['time']
   stable=stable+1 if 'feed' in r and r['time']>0 and .03<delta<.8 and not p.u(p.modules['engine.dll']+0xb42318) else 0
   if stable>=5:return
  except (OSError,KeyError,RuntimeError):pass
  time.sleep(.15)
 raise TimeoutError('Owned save not ready')
def shot(label):
 before={str(x) for x in (G/'Unofficial_Patch/screenshots').glob('*.tga')};command("__import__('__main__').ccmd.screenshot=''");time.sleep(.3)
 after=[x for x in (G/'Unofficial_Patch/screenshots').glob('*.tga') if str(x) not in before];assert after,'native screenshot missing'
 from PIL import Image
 Image.open(after[-1]).save(O/(label+'.png'))
def stop():
 global child,p
 if child and child.poll() is None:
  try:command("__import__('__main__').ccmd.quit=''")
  except Exception:pass
  try:child.wait(timeout=3)
  except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=5)
 if p:k.CloseHandle(p.h);p=None
try:
 shutil.copy2(controller,G/'Bin/loader/zz-hud-owned-controller.vtm')
 owned=G/'Unofficial_Patch/save/victim_owned.sav';assert not owned.exists();shutil.copy2(a.save,owned);dump('save-identity.json',{'sha256':sha(a.save),'copy_sha256':sha(owned)})
 # Direct save startup does not reliably run user.cfg. Define precisely the
 # three stock UP feed aliases, rather than treating an absent alias as a press.
 (G/'Unofficial_Patch/cfg/victim_owned.cfg').write_text('sv_cheats 1\nhideconsole\nalias feedStart "+feed"\nalias feedStop "-feed"\nalias vm_feed "checkFeed()"\n')
 loader=G/'Bin/loader/loader.ini';loader.write_bytes(re.sub(rb'(?m)^(Loading Wait For Enter\s*=\s*)1',rb'\g<1>0',loader.read_bytes()))
 child=subprocess.Popen([str(G/'Vampire.exe'),'-game','Unofficial_Patch','-dev','-novid','+load','victim_owned','+exec','victim_owned.cfg'],cwd=str(G),creationflags=subprocess.CREATE_NO_WINDOW);dump('process.json',{'pid':child.pid});print('OWNED',child.pid,flush=True);ready()
 import pefile
 plugin=pefile.PE(str(G/'Bin/loader/ant2684-fixes-adjustments.vtm'));status_rva=next(x.address for x in plugin.DIRECTORY_ENTRY_EXPORT.symbols if x.name==b'victim_bar_status');c=p.modules['client.dll']
 status=list(struct.unpack('<2I',p.read(p.modules['ant2684-fixes-adjustments.vtm']+status_rva,8)));result['status']=status
 original=pefile.PE(str(G/'Vampire/cl_dlls/client.dll'));original.relocate_image(c);differences={}
 for rva,n in [(0x503d0,0x22),(0x50560,0x16),(0x5057c,4),(0x507a1,0x44),(0x507ed,0x38),(0x50871,0xa9)]:
  disk=original.get_data(rva,n);live=p.read(c+rva,n);differences[hex(rva)]=[hex(rva+i) for i,(x,y) in enumerate(zip(disk,live)) if x!=y]
 dump('installation.json',{'status':status,'anchor_differences':differences,'sites':{hex(x):p.read(c+x,n).hex() for x,n in [(0x50576,6),(0x5079b,6),(0x22890c,4)]}});print('STATUS',status,differences,flush=True);assert status==[1,0],'Native installation refused; see installation.json'
 # Confirm central callback dispatch and unchanged side-HUD animation.
 hud_rva=next(x.address for x in plugin.DIRECTORY_ENTRY_EXPORT.symbols if x.name==b'hud_fix_status')
 side_status=list(struct.unpack('<3I',p.read(p.modules['ant2684-fixes-adjustments.vtm']+hud_rva,12)))
 assert side_status==[1,1,0],side_status
 rows=observe('integrated-hud',2)
 assert len({x['health']['frame'] for x in rows})>3
 assert rows[-1]['blood']['value']>=15 or len({x['blood']['frame'] for x in rows})>3
 result.update(passed=True,hud_status=side_status,victim_status=status,side_animation=True,scope='Integrated startup and existing renderer only; feeding already qualified separately')
except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc());raise
finally:
 stop();dump('result.json',result);tx.restore();assert tr.video_snapshot()==tx.video
 backup=(O/'backup').resolve();assert backup.parent==O and backup.name=='backup';shutil.rmtree(backup);dump('backup-cleanup.json',{'restoration_verified':True,'duplicate_backup_removed':True});print('RESTORED',flush=True)
print(json.dumps(result,indent=2))
