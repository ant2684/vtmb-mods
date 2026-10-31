"""Unified verification of existing finalized artifacts. Never rebuilds payloads."""
import argparse,hashlib,json,os,subprocess,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
from profiles import DEFAULT
ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,default=HERE/'local.json');ap.add_argument('--phase',choices=['static','native','game','archives','all'],default='all');args=ap.parse_args()
cfg=json.loads(args.config.read_text());out=Path(cfg['output'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plugin=out/'Payload/Bin/loader/protean-frenzy-improved.vtm';before=sha(plugin)
def run(script,*values):subprocess.run([sys.executable,'-B',str(HERE/script),'--config',str(args.config),*values],check=True)
if args.phase in ['static','all']:
    run('check_config.py')
    run('tests/verify_backup_scope.py')
    assert {p.relative_to(out/'Payload').as_posix() for p in (out/'Payload').rglob('*') if p.is_file()}=={'Bin/loader/protean-frenzy-improved.vtm','Bin/loader/protean-frenzy-improved.ini'}
    sys.path[:0]=[cfg['native_dependencies'],str(HERE/'_support')]
    from clean_payload import verify_clean
    verify_clean(plugin,['loaded_vampire','loaded_client'])
    for report_name in ['resources.json','maps.json']:
        report=json.loads((out/report_name).read_text())
        for relative,row in report.items():
            if report_name=='maps.json':relative='Unofficial_Patch/maps/'+relative
            assert sha(out/'Components'/row['component']/relative)==row['sha256'],relative
    print('Static payload/resource identities PASS',flush=True)
if args.phase in ['native','all']:run('run_tests.py','--suite','all')
if args.phase in ['game','all']:
    run('run_gameplay.py',*DEFAULT)
    run('run_gameplay.py','frenzy-maps-library','frenzy-maps-griffith')
    run('run_gameplay.py','native-hunger-warform-melee-off')
    run('run_gameplay.py','native-dependencies-off')
if args.phase in ['archives','all']:
    manifest=json.loads((out/'archives.json').read_text())
    for row in manifest['archives']:
        p=Path(row['path']);assert sha(p)==row['sha256']
        with zipfile.ZipFile(p) as z:
            assert z.testzip() is None
            assert set(z.namelist())==set(row['files'])
            for name,digest in row['files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    print('Archive CRC, membership and extracted SHA-256 PASS',flush=True)
assert sha(plugin)==before,'Finalized candidate changed during verification'
print('Requested phase PASS; candidate unchanged',before,flush=True)
