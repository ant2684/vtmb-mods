"""Stage and run complete owned scenarios on the exact finalized candidate."""
import argparse,datetime,hashlib,json,os,re,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('modes',nargs='+')
ap.add_argument('--config',type=Path,default=HERE/'local.json')
ap.add_argument('--visual-frenzy',action='store_true',help='Audit RedVision state/render code and capture before/repeat/cleanup images')
ap.add_argument('--stock-frenzy-regression',action='store_true')
ap.add_argument('--pool-isolation-regression',action='store_true',help='All seven ordinary combo chains with InventoryFixes disabled')
args=ap.parse_args()
cfg=json.loads(args.config.read_text());out=Path(cfg['output']);live=out/'live';live.mkdir(exist_ok=True)
if cfg.get('legacy_counterexample'):
    assert args.modes==['native-hunger-human'],'Legacy counterexample is restricted to the original defect'
    assert hashlib.sha256((out/'Payload/Bin/loader/protean-frenzy-improved.vtm').read_bytes()).hexdigest()=='478bf4cb5e763e7b13553570a22bee429677837b0fd12c5d1fa36604c9673ee9','Unrecognized counterexample binary'
assert shutil.disk_usage(out).free>3*1024**3,'Insufficient task-volume space for transaction and captures'
temp=out/'temp';temp.mkdir(exist_ok=True)
env=os.environ.copy();env['TEMP']=env['TMP']=str(temp);env['PFI_CONFIG']=str(args.config.resolve())
env['ZIG_GLOBAL_CACHE_DIR']=str(out/'build/cache-global');env['ZIG_LOCAL_CACHE_DIR']=str(out/'build/cache')
env['PYTHONPATH']=os.pathsep.join([str(live),str(live/'_support'),cfg['native_dependencies']])
for source in (HERE/'tests/gameplay').glob('*.py'):shutil.copy2(source,live/source.name)
shutil.copytree(HERE/'_support',live/'_support',dirs_exist_ok=True)

if args.stock_frenzy_regression:
    assert args.modes==['native-hunger-warform'],'Run the stock-Frenzy control separately'
    p=live/'game_probe.py';s=p.read_text();old="later(.8,'native_hunger_release()')";assert s.count(old)==1
    s=s.replace(old,"later(8.,'native_hunger_release()')")
    s=s.replace("mark('NATIVE_HUNGER_BEFORE')\n","mark('NATIVE_HUNGER_BEFORE');command('snapshot')\n")
    p.write_text(s)
    p=live/'run_game.py';s=p.read_text().replace("deadline=time.monotonic()+(150 if","deadline=time.monotonic()+(90 if mode.startswith('native-hunger') else 150 if");p.write_text(s)
    p=live/'audit_game.py';p.write_text(p.read_text()+"\nfrom stock_frenzy_audit import audit_stock_frenzy\n_stock_base_audit=audit\ndef audit(mode,log,rows):\n return _stock_base_audit(mode,log,rows)+audit_stock_frenzy(log,rows)\n")
if args.visual_frenzy:
    assert all(m in ['native-hunger-human','native-hunger-human-outputs','native-hunger-warform','native-hunger-warform-outputs'] for m in args.modes),'Visual audit supports the four natural-Frenzy profiles'
    sys.path.insert(0,str(HERE/'tests/gameplay'))
    from frenzy_visual import stage
    stage(live)

syntax=out/'temp/game-probe-compile.py';syntax.write_text((live/'game_probe.py').read_text().replace('__CLAW_ROUTES__','{}'),encoding='ascii')
subprocess.run([str(out/'build/validate_python.exe'),str(Path(cfg['game'])/'Bin/vampire_python21.dll'),str(syntax)],check=True,env=env)
subprocess.run([sys.executable,'-B','-c','import run_game,native_inspect,native_health_observer,sequence_observer,audit_game,audit_coexist_game,transaction'],env=env,cwd=live,check=True)
for source,name in [('clean_bootstrap','probe-bootstrap'),('transition_bootstrap','transition-bootstrap'),
                    ('midload_bootstrap','midload-bootstrap'),('interface_bootstrap','interface-bootstrap')]:
    subprocess.run([cfg['zig'],'cc','-target','x86-windows-gnu','-shared','-O2','-g0','-s',
                    str(HERE/'tests/gameplay'/(source+'.c')),'-o',str(live/(name+'.vtm'))],check=True,env=env)
payload=live/'candidate/Payload';payload.mkdir(parents=True,exist_ok=True)
shutil.copytree(out/'Payload',payload,dirs_exist_ok=True)
if any(m.endswith('melee-off') for m in args.modes):
    assert args.modes==['native-hunger-warform-melee-off'],'Run the Melee-off control separately'
    ini=payload/'Bin/loader/protean-frenzy-improved.ini'
    changed,count=re.subn(rb'(?m)^MeleeFrenzy=1(\r?)$',rb'MeleeFrenzy=0\1',ini.read_bytes())
    assert count==1;ini.write_bytes(changed)
if args.pool_isolation_regression:
    assert args.modes==['claws-actions-male'],'One complete Inventory-off combo scenario'
    ini=payload/'Bin/loader/protean-frenzy-improved.ini'
    changed,count=re.subn(rb'(?m)^InventoryFixes=1(\r?)$',rb'InventoryFixes=0\1',ini.read_bytes())
    assert count==1;ini.write_bytes(changed)
    p=live/'run_game.py';s=p.read_text()
    s=s.replace("if mode=='native-dependencies-off':\n                                from native_inspect import mem","if mode=='native-dependencies-off' or mode=='claws-actions-male':\n                                from native_inspect import mem")
    s=s.replace("if mode=='native-dependencies-off' or mode=='claws-actions-male':\n                                from native_inspect import mem","if mode=='native-dependencies-off' or mode=='claws-actions-male':\n                                assert reader.read(base+0x8dac0,1)==b'\\xe9','Model isolation hook missing'\n                                from native_inspect import mem")
    p.write_text(s)
if 'native-dependencies-off' in args.modes:
    assert args.modes==['native-dependencies-off'],'Run the configuration control separately'
    ini=payload/'Bin/loader/protean-frenzy-improved.ini'
    changed,count=re.subn(rb'(?m)^InventoryFixes=1(\r?)$',rb'InventoryFixes=0\1',ini.read_bytes())
    assert count==1;ini.write_bytes(changed)
    assert b'\nInventoryFixes=0' in ini.read_bytes()
for component in ['ClawsModels','StealthSound','StealthBlood']:
    shutil.copytree(out/'Components'/component,payload,dirs_exist_ok=True)
map_modes={'frenzy-maps-library':'la_library_1','frenzy-maps-griffith':'sp_observatory_2'}
if any(mode in map_modes for mode in args.modes):
    assert all(mode in map_modes for mode in args.modes),'Run fresh-map transactions separately'
    for mode in args.modes:
        subprocess.run([cfg['zig'],'cc','-target','x86-windows-gnu','-shared','-O2','-g0','-s',
            '-DPFI_TARGET_MAP="'+map_modes[mode]+'"',str(HERE/'tests/gameplay/clean_bootstrap.c'),'-o',str(live/(mode+'-bootstrap.vtm'))],check=True,env=env)
    for component in ['FrenzyLibrary','FrenzyGriffith']:
        shutil.copytree(out/'Components'/component,payload,dirs_exist_ok=True)
else:
    shutil.rmtree(payload/'Unofficial_Patch/maps',ignore_errors=True)
expected={p.relative_to(payload).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in payload.rglob('*') if p.is_file()}
for mode in args.modes:
    before=set((live/'sessions').glob('*'))
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    result=subprocess.run([sys.executable,'-B',str(live/'run_game.py'),mode],env=env,cwd=live,capture_output=True,text=True)
    created=set((live/'sessions').glob('*'))-before
    assert len(created)==1,('Scenario did not create one receipt',mode,result.stdout,result.stderr)
    session=created.pop();(session/'stdout.txt').write_text(result.stdout,encoding='utf8');(session/'stderr.txt').write_text(result.stderr,encoding='utf8')
    receipt=session/'result.json'
    if not receipt.exists():
        print(mode,'BLOCKED; no receipt',session,result.stderr[-3000:],flush=True);raise SystemExit(1)
    data=json.loads(receipt.read_text());data['started']=started
    data['expected_payload_sha256']=expected
    receipt.write_text(json.dumps(data,indent=2)+'\n')
    print(mode,'PASS' if data.get('passed') and data.get('restored') else 'FAIL',session,flush=True)
    if result.returncode or not data.get('passed') or not data.get('restored'):
        print(result.stdout[-2500:]+result.stderr[-2500:],flush=True);raise SystemExit(1)
    assert data.get('payload_sha256')==expected,'Scenario qualified another payload'
    if mode=='save-active':
        seed=session/'generated/Unofficial_Patch/save/ProteanLifecycleActiveOwned.sav';assert seed.exists()
        cfg['active_seed']=str(seed);cfg['active_seed_sha256']=hashlib.sha256(seed.read_bytes()).hexdigest()
        args.config.write_text(json.dumps(cfg,indent=2)+'\n')
    if mode=='filter-save':
        name,key='ProteanFilterOwned','filter_seed'
        seed=next((session/'generated').rglob(name+'.sav'))
        target=out/'inputs/saves'/(key+'.sav');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(seed,target)
        cfg[key]=str(target);cfg[key+'_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
        args.config.write_text(json.dumps(cfg,indent=2)+'\n')
print('All requested scenarios passed and restored. Installed game unchanged.',flush=True)
