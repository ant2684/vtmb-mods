"""Regression against Advanced EXE silently skipping a valid new plugin."""
import json,os,sys,hashlib
from pathlib import Path
here=Path(__file__).resolve().parents[1]
cfg=json.loads(Path(os.environ['PFI_CONFIG']).read_text());out=Path(cfg['output'])
sys.path[:0]=[str(here/'_support'),cfg['native_dependencies']]
import pefile
from finalize_pe import LEGACY_BLOCKED_SIZES,extend_last_section,ensure_loader_compatible_size
from clean_payload import verify_clean
plugin=out/'Payload/Bin/loader/protean-frenzy-improved.vtm'
identity=hashlib.sha256(plugin.read_bytes()).hexdigest()
assert plugin.stat().st_size not in LEGACY_BLOCKED_SIZES
exe=pefile.PE(str(Path(cfg['game'])/'Vampire.exe')).get_memory_mapped_image()
for index,(offset,size) in enumerate(zip([0xe98f,0xe997,0xe99f,0xe9a7,0xe9af,0xe9b7],
                       [0x17c00,0x1ae00,0x1f200,0x13400,0x15000,0x1ea00])):
    assert exe[offset:offset+4]==b'\xc7\x44\x24'+bytes([0x18+index*4])
    assert int.from_bytes(exe[offset+4:offset+8],'little')==size
fixture=out/'build/loader-size-regression.vtm';fixture.write_bytes(plugin.read_bytes())
target=min(size for size in LEGACY_BLOCKED_SIZES if size>fixture.stat().st_size)
extend_last_section(fixture,target-fixture.stat().st_size)
try:verify_clean(fixture,['loaded_vampire','loaded_client'])
except AssertionError as error:assert 'historical plugin size' in str(error)
else:raise AssertionError('Blacklist counterexample was not rejected')
ensure_loader_compatible_size(fixture)
verify_clean(fixture,['loaded_vampire','loaded_client'])
assert hashlib.sha256(plugin.read_bytes()).hexdigest()==identity
print('PASS actual loader-size table, rejected counterexample, valid section-only padding, no overlay/code/RVA changes, original candidate unchanged')
