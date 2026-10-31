"""Build/finalize once before acceptance. Never writes to a game installation."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser()
ap.add_argument('--config',type=Path,default=HERE/'local.json')
ap.add_argument('--tests-only',action='store_true')
ap.add_argument('--fixtures',nargs='+',help='Compile only these named test fixtures; default is every fixture')
args=ap.parse_args()
cfg=json.loads(args.config.read_text())
repo=Path(cfg['repo']);out=Path(cfg['output']);build=out/'build'
common=HERE/'_support' if (HERE/'_support').exists() else repo/'infra/common'
sys.path[:0]=[cfg['native_dependencies'],str(common)]
from finalize_pe import finalize,ensure_loader_compatible_size
from clean_payload import verify_clean
build.mkdir(parents=True,exist_ok=True)
(out/'temp').mkdir(exist_ok=True)
os.environ['TEMP']=os.environ['TMP']=str(out/'temp')
os.environ['ZIG_GLOBAL_CACHE_DIR']=str(build/'cache-global')
os.environ['ZIG_LOCAL_CACHE_DIR']=str(build/'cache')
base=[cfg['zig'],'cc','-target','x86-windows-gnu','-O2','-g0','-s','-Wall','-Wextra','-Werror',
      '-Wno-unused-function','-Wno-unused-variable','-Wno-unused-but-set-variable',
      '-I',str(HERE/'native'),'-I',str(common)]
def run(*parts):subprocess.run([str(p) for p in parts],check=True)
plugin=out/'Payload/Bin/loader/protean-frenzy-improved.vtm'
if not args.tests_only:
    assert not (out/'accepted.json').exists(),'Accepted delivery bytes are sealed; choose a fresh output directory'
    native=Path(cfg['game'])/'Vampire/dlls/vampire.dll'
    assert hashlib.sha256(native.read_bytes()).hexdigest()=='c546f4de2003624d72f54d03805e0dbe1d8157231adcc62368ff53fe6e48a76f'
    target=build/plugin.name
    run(*base,'-shared','-Wl,--build-id=none',*[str(p) for p in sorted((HERE/'native').glob('*.c'))],'-o',target)
    finalize(target)
    ensure_loader_compatible_size(target)
    receipt=verify_clean(target,['loaded_vampire','loaded_client'])
    plugin.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,plugin)
    shutil.copy2(HERE/'protean-frenzy-improved.ini',plugin.with_suffix('.ini'))
    (out/'clean.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('CLEAN',receipt['sha256'],receipt['size'])
fixtures=sorted((HERE/'tests').glob('*.c'))
if args.fixtures:
    assert set(args.fixtures)<={p.stem for p in fixtures},'Unknown fixture'
    fixtures=[p for p in fixtures if p.stem in args.fixtures]
for source in fixtures:
    run(*base,source,'-o',build/(source.stem+'.exe'))
print('Build finished. No game files changed.')
