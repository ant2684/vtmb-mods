"""One exact-candidate runner. A failure retains its first receipt and stops."""
import argparse,datetime,hashlib,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,default=HERE/'local.json')
ap.add_argument('--suite',choices=['native','resources','all'],default='all');ap.add_argument('--only',nargs='+');args=ap.parse_args()
cfg=json.loads(args.config.read_text());out=Path(cfg['output']);game=Path(cfg['game'])
plugin=out/'Payload/Bin/loader/protean-frenzy-improved.vtm';before=hashlib.sha256(plugin.read_bytes()).hexdigest()
receipt=out/'checks'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');receipt.mkdir(parents=True)
env=os.environ.copy();env['PFI_CONFIG']=str(args.config.resolve());env['PYTHONPATH']=os.pathsep.join([cfg['native_dependencies'],str(HERE/'_support')])
checks=[]
if args.only:
    known={'npc_pools','pool_isolation','fixture_priorities','configuration','lifecycle','native_support','claws_frenzy','melee_behavior','core','emitted_warform','emitted_feats','emitted_filter_sync','griffith','stealth','flow','claws_frenzy_models','loader_compatibility','native_runtime'}
    assert set(args.only)<=known,'Unknown check name'
def run(label,*cmd):
    if args.only and label not in args.only:return
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    result=subprocess.run([str(p) for p in cmd],env=env,capture_output=True,text=True)
    (receipt/(label+'.stdout.txt')).write_text(result.stdout,encoding='utf8')
    (receipt/(label+'.stderr.txt')).write_text(result.stderr,encoding='utf8')
    checks.append(dict(name=label,started=started,passed=result.returncode==0,exit_code=result.returncode))
    (receipt/'result.json').write_text(json.dumps(dict(plugin_sha256=before,checks=checks,passed=all(c['passed'] for c in checks)),indent=2)+'\n')
    print(label,'PASS' if not result.returncode else 'FAIL',flush=True)
    if result.returncode:
        print(result.stdout+result.stderr);raise SystemExit(result.returncode)
    if label=='lifecycle' and '17 hook conflicts, 32 dependency conflicts' in result.stdout:
        (out/'lifecycle-guards.json').write_text(json.dumps(dict(passed=True,plugin_sha256=before,
            created=started,hook_conflicts=17,dependency_conflicts=32,stdout=result.stdout,stderr=result.stderr),indent=2)+'\n')
if args.suite in ['native','all']:
    run('configuration',out/'build/exact_configuration.exe',plugin,game/'Vampire/dlls/vampire.dll',game/'Vampire/cl_dlls/client.dll',game/'Bin/engine.dll')
    run('lifecycle',out/'build/exact_lifecycle.exe',plugin,game/'Vampire/dlls/vampire.dll')
    run('native_support',out/'build/native_support.exe')
    run('claws_frenzy',out/'build/native_claws_frenzy.exe')
    models=out/'Components/ClawsModels/Unofficial_Patch/models/character/shared'
    run('pool_isolation',out/'build/exact_claws_pools.exe',plugin,game/'Vampire/dlls/vampire.dll',models/'male/claws.mdl',models/'female/claws.mdl')
    run('npc_pools',sys.executable,'-B',HERE/'tests/verify_npc_pools.py')
    run('melee_behavior',out/'build/native_melee.exe')
    core=receipt/'emitted';core.mkdir()
    run('core',out/'build/exact_core.exe',plugin,game/'Vampire/dlls/vampire.dll',game/'Vampire/cl_dlls/client.dll',core)
    for name in ['emitted_warform','emitted_feats','emitted_filter_sync']:
        run(name,sys.executable,'-B',HERE/'tests'/(name+'.py'),core)
    run('griffith',out/'build/exact_griffith.exe',plugin,game/'Vampire/dlls/vampire.dll',game/'Bin/engine.dll')
    run('stealth',sys.executable,'-B',HERE/'tests/verify_stealth.py')
    run('flow',sys.executable,'-B',HERE/'tests/verify_flow.py')
if args.suite in ['resources','all']:
    run('claws_frenzy_models',sys.executable,'-B',HERE/'tests/verify_claws_frenzy.py')
    run('loader_compatibility',sys.executable,'-B',HERE/'tests/verify_loader_compatibility.py')
    run('native_runtime',sys.executable,'-B',HERE/'tests/verify_native_runtime.py')
    run('fixture_priorities',sys.executable,'-B',HERE/'tests/verify_fixture_priorities.py')
assert hashlib.sha256(plugin.read_bytes()).hexdigest()==before,'Candidate changed during tests'
print('Exact candidate unchanged:',before,receipt,flush=True)
