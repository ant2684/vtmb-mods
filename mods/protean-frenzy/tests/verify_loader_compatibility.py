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
loader=Path(cfg['game'])/'Vampire.exe'
loader_sha=hashlib.sha256(loader.read_bytes()).hexdigest()
# The same six-entry size table moved when Advanced EXE gained new code.
# Pin both inspected layouts; an unknown loader remains a blocked input.
layouts={
 '6b15fae4e5514f88e023a2f17ee84e2a3cdee35ce663d5af39b8178a58e3765a':(0xe98f,0x18),
 '0625c6b5986d76a8b8f4f2b0447a08c1d1faba7655d417b07d8fa1fdcc076a76':(0xfee4,0x1c)}
assert loader_sha in layouts,('Unsupported loader identity',loader_sha)
start,stack_slot=layouts[loader_sha]
exe=pefile.PE(str(loader)).get_memory_mapped_image()
for index,size in enumerate([0x17c00,0x1ae00,0x1f200,0x13400,0x15000,0x1ea00]):
    offset=start+index*8
    assert exe[offset:offset+4]==bytes([0xc7,0x44,0x24,stack_slot+index*4])
    assert int.from_bytes(exe[offset+4:offset+8],'little')==size
print('Pinned loader',loader_sha,'table RVA',hex(start))
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
