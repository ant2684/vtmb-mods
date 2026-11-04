"""Collect bounded receipts; seal only after every required exact-byte scenario."""
import argparse,hashlib,json,datetime,re,sys
from pathlib import Path
from profiles import REQUIRED
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,default=HERE/'local.json');ap.add_argument('--seal',action='store_true')
ap.add_argument('--counterexample',type=Path,help='Receipt from run_counterexample.py for the pinned preceding release');args=ap.parse_args()
cfg=json.loads(args.config.read_text());out=Path(cfg['output']);validation=HERE/'validation'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plugin=out/'Payload/Bin/loader/protean-frenzy-improved.vtm';identity=sha(plugin)
scenarios={};failures=[]
for session in sorted((out/'live/sessions').glob('*')):
    file=session/'result.json'
    if not file.exists():continue
    r=json.loads(file.read_text());mode=r['mode'];payload=r.get('payload_sha256',{})
    if payload.get('Bin/loader/protean-frenzy-improved.vtm')!=identity:continue
    if r.get('passed') and r.get('restored'):
        if r.get('expected_payload_sha256'):assert payload==r['expected_payload_sha256']
        ini=plugin.with_suffix('.ini').read_bytes()
        if mode=='native-dependencies-off':ini=re.sub(rb'(?m)^InventoryFixes=1(\r?)$',rb'InventoryFixes=0\1',ini)
        if mode.endswith('melee-off'):ini=re.sub(rb'(?m)^MeleeFrenzy=1(\r?)$',rb'MeleeFrenzy=0\1',ini)
        assert payload['Bin/loader/protean-frenzy-improved.ini']==hashlib.sha256(ini).hexdigest()
        row=dict(mode=mode,id=session.name,passed=True,restored=True,assertions=r.get('assertions',[]),payload_sha256=payload)
        if r.get('audit_repair'):row['audit_repair']=r['audit_repair']
        if r.get('previous_setup_reproduced_map_initialization_errors'):row['baseline_limit']='The two exact unchanged UP FindPlayer startup tracebacks were also reproduced on the preceding six-module setup; other errors remain fatal.'
        row['probe_sha256']=sha(session/'probe.log')
        source=session/'generated/Unofficial_Patch/python/p5_probe.py'
        if source.exists():row['executed_script_sha256']=sha(source)
        scenarios[mode]=row
    else:
        reason=r.get('error','Missing successful completion')[:1800].replace(cfg['game'],'$GAME')
        failures.append(dict(id=session.name,mode=mode,restored=r.get('restored',False),error=reason))
missing=[m for m in REQUIRED if m not in scenarios]
print(json.dumps(dict(candidate=identity,passed_modes=list(scenarios),missing=missing),indent=2),flush=True)
if not args.seal:raise SystemExit(bool(missing))
assert not missing,'Required gameplay remains incomplete; not sealed'
# Re-evaluate retained observations with the current acceptance assertions. An
# old PASS from weaker assertions cannot qualify a changed regression contract.
sys.path.insert(0,str(HERE/'tests/gameplay'))
from audit_game import audit as audit_regular
from audit_coexist_game import audit as audit_coexist
for mode in REQUIRED:
    row=scenarios[mode];session=out/'live/sessions'/row['id']
    audit=audit_coexist if mode=='frenzy-melee' else audit_regular
    observations=json.loads((session/'observations.json').read_text())
    # JSON object keys are strings; live inventory graphs use integer handles.
    for observation in observations:
        for actor in [observation]+observation['actors']:
            if 'inventory_items' in actor:actor['inventory_items']={int(k):v for k,v in actor['inventory_items'].items()}
    row['revalidated_assertions']=audit(mode,(session/'probe.log').read_text(),observations)
    row['observations_sha256']=sha(session/'observations.json')
    row['audit_module_sha256']=sha(HERE/'tests/gameplay'/('audit_coexist_game.py' if mode=='frenzy-melee' else 'audit_game.py'))
assert args.counterexample,'Sealing requires the original-defect counterexample receipt'
counterexample=json.loads(args.counterexample.read_text())
assert counterexample['passed'] and counterexample['restored'] and counterexample['fists_samples']>0
assert counterexample['plugin_sha256']=='478bf4cb5e763e7b13553570a22bee429677837b0fd12c5d1fa36604c9673ee9'
native=[]
for file in sorted((out/'checks').glob('*/result.json')):
    r=json.loads(file.read_text())
    expected={'npc_pools','pool_isolation','fixture_priorities','configuration','lifecycle','melee_behavior','core','emitted_warform','emitted_feats','emitted_filter_sync','griffith','stealth','flow','native_support','loader_compatibility','native_runtime','claws_frenzy','claws_frenzy_models'}
    if r.get('passed') and r['plugin_sha256']==identity and {c['name'] for c in r['checks']}==expected:native.append((file,r))
assert native,'No complete exact-candidate native/resource receipt'
guards=json.loads((out/'lifecycle-guards.json').read_text())
assert guards['passed'] and guards['plugin_sha256']==identity
assert guards['hook_conflicts']==17 and guards['dependency_conflicts']==32
for name in ['resources.json','maps.json']:assert (out/name).exists()
resources={}
for component in (out/'Components').iterdir():
    if component.is_dir():
        for p in component.rglob('*'):
            if p.is_file():resources[component.name+'/'+p.relative_to(component).as_posix()]=sha(p)
assert len(resources)==6
accepted=dict(passed=True,created=datetime.datetime.now(datetime.timezone.utc).isoformat(),plugin_sha256=identity,
    ini_sha256=sha(plugin.with_suffix('.ini')),resources=resources,required_gameplay=REQUIRED,
    native_receipt=native[-1][0].parent.name,lifecycle_guards=guards,scenarios=[scenarios[m] for m in REQUIRED],original_defect_control=counterexample,
    limits=['Supported local native setup only','Owner artistic/play acceptance is separate','No full clan/armor/mod matrix or exact Frenzy cadence equivalence','Map console-trigger qualification does not certify random natural-trigger probability'])
validation.mkdir(exist_ok=True)
for name,data in [('Accepted.json',accepted),('Native.json',native[-1][1]),('LifecycleGuards.json',guards),('Counterexample.json',counterexample),('FirstFailures.json',dict(candidate=identity,failures=failures)),('Resources.json',json.loads((out/'resources.json').read_text())),('Maps.json',json.loads((out/'maps.json').read_text()))]:
    (validation/name).write_text(json.dumps(data,indent=2)+'\n')
(out/'accepted.json').write_text(json.dumps(accepted,indent=2)+'\n')
print('SEALED',identity,'native build now refuses this output directory',flush=True)
