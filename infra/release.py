"""Read-only frozen-release, PE and resource checks."""
import re
import struct
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from infra.core import ROOT, require, sha, catalog, need, run


def members(path):
    with zipfile.ZipFile(path) as z:
        require(z.testzip() is None, 'ZIP CRC failure')
        entries = z.infolist()
        require(all(e.orig_filename == e.filename for e in entries), 'ZIP filename normalization hides unsafe path')
        require(not any(e.is_dir() for e in entries), 'Unexpected directory members')
        names = [e.filename for e in entries]
        require(len(names) == len({n.casefold() for n in names}), 'Duplicate Windows ZIP paths')
        for name in names:
            p = PurePosixPath(name)
            require(not p.is_absolute() and '..' not in p.parts and ':' not in name and '\\' not in name, 'Unsafe ZIP path: ' + name)
        return {e.filename: z.read(e) for e in entries}


def clean_pe(data, exports, mod):
    import pefile
    p = pefile.PE(data=data)
    require(p.FILE_HEADER.Machine == 0x14c and p.OPTIONAL_HEADER.Magic == 0x10b, 'Not PE32 x86')
    require(bool(p.FILE_HEADER.Characteristics & 0x2000), 'Not DLL')
    require(not p.FILE_HEADER.PointerToSymbolTable and not p.FILE_HEADER.NumberOfSymbols, 'COFF symbols')
    d = p.OPTIONAL_HEADER.DATA_DIRECTORY[6]
    require(not d.Size and not d.VirtualAddress, 'Debug directory')
    require(p.get_overlay_data_start_offset() is None, 'Overlay')
    sections = {s.Name.rstrip(b'\0').decode() for s in p.sections}
    require(sections <= {'.text', '.rdata', '.data', '.tls', '.reloc'}, 'Unexpected PE sections')
    require({e.name.decode() for e in p.DIRECTORY_ENTRY_EXPORT.symbols} == set(exports), 'Unexpected exports')
    imports = {i.name.decode() for dll in getattr(p, 'DIRECTORY_ENTRY_IMPORT', []) for i in dll.imports if i.name}
    forbidden = {'CreateFileA','CreateFileW','WriteFile','fopen','fprintf','OutputDebugStringA','OutputDebugStringW','CreateThread','SendInput','CreateProcessA','CreateProcessW','RegSetValueExA','RegSetValueExW'}
    require(not imports & forbidden, 'Diagnostic/service imports: ' + str(imports & forbidden))
    # fwrite and formatting in ordinary CRT support are not independently a log writer.
    strings = re.findall(rb'[\x20-\x7e]{5,}', data)
    strings += [x.decode('utf-16le').encode() for x in re.findall(rb'(?:[\x20-\x7e]\x00){5,}', data)]
    marks = [b'.pdb', b'.log', b'test_hook', b'.debug', b'.buildid', b'console-task-command', b'console-input-command']
    require(not any(mark in s.lower() for s in strings for mark in marks), 'Debug/log/test string')
    if mod == 'history':
        require(imports == {'FlushInstructionCache','GetCurrentProcess','GetModuleHandleA','VirtualAlloc','VirtualFree','VirtualProtect'}, 'History import boundary')
    return {'sha256': sha(data), 'sections': sorted(sections), 'exports': exports, 'imports': sorted(imports)}


def verify_archives(config, mod='all'):
    c = catalog()
    base = Path(need(config, 'releases'))
    selected = set(c['mods']) if mod == 'all' else {mod}
    archives = {a for m in selected for a in (c['mods'][m]['archive'], c['mods'][m]['capsule'])}
    if 'protean' in selected:
        archives.update(a for a in c['archives'] if 'Block.zip' in a)
    findings = []
    for name in sorted(archives):
        path = base / name
        if not path.is_file():
            from infra.core import Blocked
            raise Blocked('Missing frozen archive: ' + name)
        pin = c['archives'][name]
        require(sha(path.read_bytes()) == pin['sha256'], 'Archive changed: ' + name)
        files = members(path)
        require({n: sha(d) for n, d in files.items()} == pin['members'], 'Member inventory/bytes changed')
        source = name.startswith('_Source Capsules/')
        readmes = [n for n in files if re.search(r'(^|/)README\.(txt|md)$', n, re.I)]
        require(len(readmes) == 1 and readmes[0] == ('README.md' if source else 'README.txt'), 'One root README required')
        if not source:
            text = files['README.txt'].decode('utf-8-sig')
            require(not re.search(r'(?im)^\s*(?:#+\s*)?(?:Verify|Testing|Test checklist|Logs)\b', text), 'Prohibited gameplay README section')
            require(('rollback' in text.lower() or 'restore' in text.lower()) and ('copy' in text.lower() or 'install' in text.lower()), 'Manual copy/rollback missing')
        for n, data in files.items():
            if n.endswith('.vtm'):
                info = next(x for x in c['mods'].values() if x['filename'] == Path(n).name)
                clean_pe(data, info['exports'], next(k for k,v in c['mods'].items() if v == info))
            if n.endswith('.bsp'):
                require(data[:4] == b'VBSP', 'BSP header')
                offset, size = struct.unpack_from('<ii', data, 8)
                entity = data[offset:offset+size]
                require(len(entity) == size and len(re.findall(rb'"nofrenzyarea"\s*"0"', entity)) == 1 and not re.search(rb'"nofrenzyarea"\s*"1"', entity), 'Frenzy permission entity lump')
        findings.append({'archive': name, 'sha256': pin['sha256'], 'files': len(files)})
    return findings


def models(config):
    base = Path(need(config, 'releases'))
    module = ROOT / 'mods/protean/models'
    import sys, os
    env = {'VTMB_RELEASES': str(base), 'PYTHONPATH': os.pathsep.join([str(module), str(module/'reference'), os.environ.get('PYTHONPATH','')])}
    return run([sys.executable, '-B', module/'test_release_models.py'], timeout=120, env=env) + run([sys.executable, '-B', module/'rebuild_models.py', '--releases', base], timeout=120, env=env)
