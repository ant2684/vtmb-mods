"""Package already qualified bytes; no rebuild and no game mutation."""
import argparse,hashlib,json,zipfile,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
VERSION=(HERE/'VERSION').read_text(encoding='ascii').strip()
assert re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?',VERSION), 'Invalid release version'
ap=argparse.ArgumentParser();ap.add_argument('--plugin',type=Path,required=True);ap.add_argument('--guard',type=Path,required=True);ap.add_argument('--native-report',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
def sha(data):return hashlib.sha256(data).hexdigest()
plugin=a.plugin.read_bytes();checks=json.loads(a.native_report.read_text())
assert checks['passed'] and checks['plugin_unchanged'] and checks['plugin_sha256']==sha(plugin)
guard=a.guard.read_bytes()
assert checks['guard_unchanged'] and checks['guard_sha256']==sha(guard)
assert checks['hud_integration_passed'],'Current HUD integration certificate required'
out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
game=out/f'ant2684-fixes-adjustments {VERSION}.zip'
source=out/f'ant2684-fixes-adjustments {VERSION} - Source.zip'
def archive(path,files):
 assert not path.exists(),'Do not overwrite a delivery archive'
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name,data in sorted(files.items()):
   info=zipfile.ZipInfo(name,(2026,11,2,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
   z.writestr(info,data)
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None
  assert set(z.namelist())==set(files)
  for name,data in files.items():assert z.read(name)==data
manual=(HERE/'game-manual.txt').read_bytes()
assert manual.splitlines()[0]==f'Fixes & Adjustments {VERSION}'.encode('ascii'), 'Manual version mismatch'
payload={
 'README.txt':manual,
 'Bin/loader/ant2684-fixes-adjustments.vtm':plugin,
 'Bin/loader/ant2684-fixes-adjustments.ini':(HERE/'ant2684-fixes-adjustments.ini').read_bytes(),
 'Bin/loader/vtmb-loading-input-guard.vtm':guard,
 'Bin/loader/vtmb-loading-input-guard.ini':(HERE/'vtmb-loading-input-guard.ini').read_bytes(),
}
archive(game,payload)
files={}
for p in HERE.rglob('*'):
 if not p.is_file() or any(x.startswith('.') or x=='__pycache__' for x in p.relative_to(HERE).parts):continue
 if p.suffix in ['.pyc','.exe','.vtm','.dll','.zip','.o','.lib']:continue
 rel=p.relative_to(HERE).as_posix()
 if rel.startswith(('validation/','tests/nexus_media/','tests/hud_media/')):continue
 files[rel]=p.read_bytes()
assert [x for x in files if Path(x).name.lower().startswith('readme')]==['README.md']
archive(source,files)
receipt={
 'version':VERSION,
 'game':{'file':game.name,'sha256':sha(game.read_bytes()),'bytes':game.stat().st_size},
 'source':{'file':source.name,'sha256':sha(source.read_bytes()),'bytes':source.stat().st_size},
 'plugin_sha256':sha(plugin),
 'guard_sha256':sha(guard),
 'payload':{name:sha(data) for name,data in payload.items()},
}
(out/'Package.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode())
print(json.dumps(receipt,indent=2))
