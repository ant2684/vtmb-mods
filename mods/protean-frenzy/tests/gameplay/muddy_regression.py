import sys,os,json,struct,time,shutil,subprocess,hashlib,argparse,ast
from pathlib import Path
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser(description='Owned Killer comparison; restores game files, config and saves.')
ap.add_argument('--config',type=Path,required=True)
ap.add_argument('--cases',nargs='+',choices=['stock','plugin','models','both','fixed'],default=['both','fixed'])
ap.add_argument('--repeats',type=int,default=1)
args=ap.parse_args();cfg=json.loads(args.config.read_text())
MODULE=HERE.parents[1];REPO=MODULE.parents[1]
GAME=Path(cfg['game']).resolve();OUT=Path(cfg['output']).resolve();OUT.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[cfg['native_dependencies'],str(HERE),str(MODULE/'_support')]
from process_reader import Process,k
from sequence_observer import native_sequence
from transaction import Transaction,running_games
from PIL import Image
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def packed(target):
 with (GAME/'Vampire/pack001.vpk').open('rb') as f:
  f.seek(-9,2);count,off=struct.unpack('<II',f.read(8));f.seek(off);table=f.read();q=0
  for _ in range(count):
   n=struct.unpack_from('<I',table,q)[0];q+=4;name=table[q:q+n].decode();q+=n;o,n=struct.unpack_from('<II',table,q);q+=8
   if name.lower()==target.lower():f.seek(o);return f.read(n)
 raise RuntimeError(target)
def text(p,value):p.write_text(json.dumps(value,indent=2),encoding='utf-8')
def build():
 src=(HERE/'clean_bootstrap.c').read_text()
 src+='\n'+(HERE/'loading_continue.c').read_text()
 src=src.replace('static int started;','static int started,travel;')
 src=src.replace('if(_stricmp(name,PFI_TARGET_MAP)&&_stricmp(name,PFI_TARGET_MAP ".bsp"))return;', '''if(_stricmp(name,PFI_TARGET_MAP)&&_stricmp(name,PFI_TARGET_MAP ".bsp")){
      if(!travel){HMODULE py=GetModuleHandleA("vampire_python21.dll");
        int(__cdecl *run)(const char *)=py?(void *)GetProcAddress(py,"PyRun_SimpleString"):NULL;
        if(run){travel=1;run("import __main__\\n__main__.ccmd.pfi_map='' ");}}
      return;
    }''')
 (OUT/'bootstrap.c').write_text(src)
 env=os.environ.copy();env['ZIG_GLOBAL_CACHE_DIR']=str(OUT/'zig-global');env['ZIG_LOCAL_CACHE_DIR']=str(OUT/'zig-local')
 subprocess.run([str(Path(cfg['zig'])),'cc','-target','x86-windows-gnu','-O2','-shared','-s','-DPFI_TARGET_MAP="sm_junkyard_1"',str(OUT/'bootstrap.c'),'-o',str(OUT/'bootstrap.vtm')],env=env,check=True)
build()
assert not running_games(),'User game running'
receipt=OUT/('transaction-'+str(time.time_ns()));receipt.mkdir()
tx=Transaction(GAME,receipt);proc=None;reader=None
try:
 tx.begin()
 tx.trees+=['Bin/loader','Unofficial_Patch/screenshots','Vampire/screenshots','screenshots']
 extras=[p for p in (GAME/'Bin/loader').rglob('*') if p.is_file()]
 for directory in ['Unofficial_Patch/screenshots','Vampire/screenshots','screenshots']:
  extras += [p for p in (GAME/directory).rglob('*') if p.is_file()]
 extras += [GAME/('Unofficial_Patch/models/character/shared/'+sex+'/claws.mdl') for sex in ['male','female']]
 extras += [GAME/'p5_owned_python_errors.txt']
 tx.single += ['p5_owned_python_errors.txt']
 tx.single += [str(p.relative_to(GAME)) for p in extras]
 for p in extras:
  rel=str(p.relative_to(GAME))
  if p.exists():
   dst=receipt/'backup'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
   tx.records[rel]=dict(sha256=sha(p),mtime_ns=p.stat().st_mtime_ns)
 text(receipt/'transaction.json',dict(game=str(GAME),trees=tx.trees,single=tx.single,files=tx.records,directories=tx.directories))
 original_plugin=Path(cfg['reference_plugin']).read_bytes()
 assert hashlib.sha256(original_plugin).hexdigest()==cfg['reference_plugin_sha256'].lower()
 source=Path(cfg['model_component_root'])
 seed=Path(cfg['muddy_seed'])
 assert sha(seed)==cfg['muddy_seed_sha256'].lower()
 assert b'sm_junkyard_1.HL1' not in seed.read_bytes(),'Seed must precede the first junkyard visit'
 text(OUT/'identities.json',dict(seed=str(seed),seed_sha256=sha(seed),plugin_sha256=hashlib.sha256(original_plugin).hexdigest()))
 for case in args.cases:
  for repeat in range(args.repeats):
   session=OUT/(case+'-'+str(repeat)+'-'+str(time.time_ns()));session.mkdir()
   assert not running_games(),'Another user game started'
   plugin=GAME/'Bin/loader/protean-frenzy-improved.vtm'
   if case in ['plugin','both']:plugin.write_bytes(original_plugin)
   elif case=='fixed':shutil.copy2(Path(cfg['candidate_plugin']),plugin)
   elif plugin.exists():plugin.unlink()
   for sex in ['male','female']:
    rel=Path('Unofficial_Patch/models/character/shared')/sex/'claws.mdl';dest=GAME/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes((source/rel).read_bytes() if case in ['models','both','fixed'] else packed('models/character/shared/'+sex+'/claws.mdl'))
   shutil.copy2(OUT/'bootstrap.vtm',GAME/'Bin/loader/zz-muddy-test.vtm')
   helper=(HERE/'muddy_probe.py').read_text().replace('__ROOT__',session.as_posix())
   (GAME/'Unofficial_Patch/python/p5_probe.py').write_text(helper,encoding='ascii')
   owned=GAME/'Unofficial_Patch/save/MuddyComparisonOwned.sav';assert not owned.exists();shutil.copy2(seed,owned)
   (GAME/'Unofficial_Patch/cfg/pfi_muddy.cfg').write_text('sv_cheats 1\nalias pfi_quit "quit"\nalias pfi_map "changelevel sm_junkyard_1"\nhideconsole\n',encoding='ascii')
   cmd=[str(GAME/'Vampire.exe'),'-game','Unofficial_Patch','-dev','-novid','+exec','pfi_muddy.cfg','+load','MuddyComparisonOwned']
   shot_dirs=[GAME/p for p in ['Unofficial_Patch/screenshots','Vampire/screenshots','screenshots']]
   previous_shots={p.resolve() for d in shot_dirs for p in d.glob('*.tga')}
   text(session/'launch.json',dict(command=cmd,case=case,repeat=repeat))
   proc=subprocess.Popen(cmd,cwd=GAME);print('START',case,repeat,proc.pid,flush=True)
   text(OUT/'current.json',dict(pid=proc.pid,session=str(session)))
   start=time.monotonic();reader=None;rows=[];labels={}
   while proc.poll() is None and time.monotonic()-start<110:
    try:
     if reader is None:reader=Process(proc.pid)
     base=reader.modules.get('vampire.dll')
     if not base:reader.refresh();continue
     table=reader.u(base+0x566458);entries=reader.read(table,8192*12);actors=[]
     def string(a):return reader.read(a,100).split(b'\0')[0].decode('ascii','replace') if a else ''
     for j in range(8192):
      ent,serial=struct.unpack_from('<II',entries,j*12+4)
      if not ent:continue
      try:
       cls=string(reader.u(ent+0x11c))
       if cls not in ['player','npc_VVampire']:continue
       name=string(reader.u(ent+0x26c))
       if cls!='player' and name!='Killer':continue
       seq=reader.u(ent+0x6f0);key=(ent,serial,reader.u(ent+0x2e0),seq)
       if key not in labels:
        try:labels[key]=native_sequence(reader.read,base,ent,seq)
        except Exception:pass
       a=dict(ptr=ent,cls=cls,name=name,seq=seq,label=labels.get(key,'?'),cycle=reader.f(ent+0x6f8),origin=struct.unpack('<3f',reader.read(ent+0x404,12)),activity=reader.u(ent+0xfec),state=reader.u(ent+0x168))
       if cls=='player':
        a['view']=struct.unpack('<3f',reader.read(ent+0x206c,12));(session/'view.txt').write_text(str(a['view'][1]))
       actors.append(a)
      except OSError:pass
     rows.append(dict(t=round(time.monotonic()-start,3),actors=actors))
    except (OSError,RuntimeError):pass
    log_path=session/'probe.log'
    if log_path.exists() and "('DONE',)" in log_path.read_text():break
    time.sleep(.08)
   if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
   if reader:k.CloseHandle(reader.h);reader=None
   text(session/'observations.json',rows)
   log=(session/'probe.log').read_text() if (session/'probe.log').exists() else ''
   print('END',case,'exit',proc.returncode,'rows',len(rows),'done',"('DONE',)" in log,'log_tail',log[-850:],flush=True)
   events=[ast.literal_eval(line) for line in log.splitlines()]
   quest=[e for e in events if e[0]=='QUEST_AFTER']
   assert len(quest)==1 and quest[0][2:4]==(1,1) and 'Animalism_Beastform' in quest[0][4],quest
   ticks=[e for e in events if e[0]=='TICK']
   labels={a['label'] for r in rows for a in r['actors'] if a['name']=='Killer'}
   hits=sum(b[2]<a[2] for a,b in zip(ticks,ticks[1:]))
   claw_attack=any('claws_attack_' in n for n in labels)
   if case=='fixed':
    assert claw_attack and hits>=2,'Fixed Killer must perform real claw attacks and repeated damage'
    assert not any(n.startswith(('claws_chain_','claws_diagonal_')) for n in labels),'Player combo leaked to NPC'
   if case in ['stock','models','plugin']:assert claw_attack and hits>0,'Control did not establish native claw combat'
   text(session/'result.json',dict(completed="('DONE',)" in log,case=case,repeat=repeat,labels=sorted(labels),damage_events=hits,claw_attack=claw_attack,quest_after=quest[0]))
   shots=sorted([p for d in shot_dirs for p in d.glob('*.tga') if p.resolve() not in previous_shots],key=lambda p:p.stat().st_mtime_ns)
   frames=[]
   for p in shots:
    with Image.open(p) as im:
     im.thumbnail((640,360));frames.append(im.convert('RGB').copy())
   if frames:frames[0].save(session/'combat.gif',save_all=True,append_images=frames[1:],duration=500,loop=0)
   for p in shots:
    assert any(p.resolve().parent==d.resolve() for d in shot_dirs);p.unlink()
   proc=None;owned.unlink()
   assert "('DONE',)" in log,'Scenario incomplete'
finally:
 if proc and proc.poll() is None:proc.terminate();proc.wait(timeout=10)
 if reader:k.CloseHandle(reader.h)
 tx.restore()
 print('RESTORED',receipt,flush=True)
 # Original files have been restored and verified; retain receipt, not duplicate backups.
 backup=(receipt/'backup').resolve();assert backup.is_relative_to(OUT.resolve());shutil.rmtree(backup)
