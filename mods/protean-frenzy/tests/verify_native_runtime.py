"""Reject regression to a modified production Python file or interpreter calls."""
import hashlib,json,os,re,sys
from pathlib import Path
cfg=json.loads(Path(os.environ['PFI_CONFIG']).read_text())
out=Path(cfg['output']);here=Path(__file__).resolve().parents[1]
sys.path[:0]=[cfg['native_dependencies'],str(here/'_support')]
import pefile
plugin=out/'Payload/Bin/loader/protean-frenzy-improved.vtm'
raw=plugin.read_bytes();pe=pefile.PE(data=raw)
imports={s.name for d in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]) for s in d.imports if s.name}
assert not any(n.startswith((b'PyRun_',b'PyImport_',b'PyObject_',b'PyInt_',b'PyErr_',b'PyModule_')) for n in imports)
for forbidden in [b'PyRun_String',b'PyRun_SimpleString',b'PyImport_AddModule',b'vampire_python21.dll',b'_proteanSupportABI',b'_proteanNativeReady']:
    assert forbidden not in raw,('Interpreter dependency in native binary',forbidden)
for folder in ['Payload','Components']:
    assert not any(p.is_file() and (p.suffix.lower() in ['.py','.pyc','.pyo'] or 'TransformSupport' in p.parts) for p in (out/folder).rglob('*'))
runtime=(here/'native/runtime.c').read_text()
assert 'pfi_publish_python' not in runtime
assert 'pfi_inventory_ready' in runtime and 'pfi_transform_active' in runtime
for file in (here/'native').iterdir():
    if file.suffix not in ['.c','.h','.inc']:continue
    assert not re.search(r'\bPy(?:Run|Import|Object|Module|Int|Err)_\w+\s*\(',file.read_text()),file
stock=Path(cfg['original_resource_root'])/'Unofficial_Patch/python/vamputil.py'
assert hashlib.sha256(stock.read_bytes()).hexdigest()=='6a98c7da7b2e3aba816091f363763109fb6420ae9d2ef3fd82767162439dbd3a'
print('PASS native-only artifact: no interpreter calls/handshake/module dependency or production Python payload; pinned stock UP input available')
