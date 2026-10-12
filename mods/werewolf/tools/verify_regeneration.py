"""Clean exact-resource gate for the local regeneration candidate, not old ZIPs."""
import argparse
import hashlib
import re
import sys
from pathlib import Path
import pefile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'resources'))
from build_regeneration import build_map, build_script

VTM = 'Bin/loader/griffith-wolf-native-damage.vtm'
INI = 'Bin/loader/griffith-wolf-native-damage.ini'
MAP = 'Unofficial_Patch/maps/sp_observatory_2.bsp'
SCRIPT = 'Unofficial_Patch/python/griffith/griffith.py'

def verify(stage, original):
    stage, original = Path(stage), Path(original)
    names = {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
    if names != {VTM, INI, MAP, SCRIPT, 'README.txt'}:
        raise ValueError('Unexpected regeneration payload files')
    if (stage / MAP).read_bytes() != build_map((original / MAP).read_bytes()):
        raise ValueError('Map is not exact scoped regeneration resource')
    if (stage / SCRIPT).read_bytes() != build_script((original / SCRIPT).read_bytes()):
        raise ValueError('Scenario is not exact scoped regeneration resource')
    mod = Path(__file__).resolve().parents[1]
    for name, source in [(INI, 'docs/griffith-wolf-native-damage.ini'), ('README.txt', 'docs/manual_regeneration_README.txt')]:
        if (stage / name).read_bytes() != (mod / source).read_bytes():
            raise ValueError('Settings/manual identity mismatch')
    raw = (stage / VTM).read_bytes()
    pe = pefile.PE(data=raw)
    if pe.FILE_HEADER.NumberOfSymbols or pe.FILE_HEADER.PointerToSymbolTable or pe.OPTIONAL_HEADER.DATA_DIRECTORY[6].Size or pe.get_overlay_data_start_offset() is not None:
        raise ValueError('PE symbols/debug/overlay')
    if {s.name for s in pe.DIRECTORY_ENTRY_EXPORT.symbols} != {b'loaded_vampire'}:
        raise ValueError('Unexpected export')
    if any(s.Name.startswith((b'.debug', b'.zdebug', b'/')) for s in pe.sections):
        raise ValueError('Debug section')
    imports = {i.name.decode() for d in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', []) for i in d.imports if i.name}
    if imports & {'WriteFile', 'fopen', 'fprintf', 'OutputDebugStringA', 'OutputDebugStringW', 'CreateThread', 'CreateProcessA', 'SendInput'}:
        raise ValueError('Unexpected writer/debug/thread/input import')
    # CreateFileA/ReadFile are required read-only INI functionality, not logging.
    if not {'CreateFileA', 'ReadFile'}.issubset(imports):
        raise ValueError('Config reader missing')
    # fwrite/__stdio_common_vfprintf are unchanged stock MinGW DLL-startup CRT
    # imports present in the preceding clean VTM, not a mod logging path.
    for marker in [b'.pdb', b'.log', b'gp_wolf_diagnostics', b'gp_wolf_damage_log']:
        if marker in raw.lower():
            raise ValueError('Diagnostic debris')
    header = (mod / 'plugin/wolf_regeneration.h').read_text()
    if 'GENERIC_WRITE' in header or 'FILE_APPEND_DATA' in header:
        raise ValueError('Configuration reader may write files')
    if re.search(r'\b(?:printf|fprintf|fwrite|fopen|WriteFile|OutputDebugStringA)\s*\(', header):
        raise ValueError('Mod source writer/diagnostic path')
    return {n: hashlib.sha256((stage / n).read_bytes()).hexdigest() for n in sorted(names)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--original-root', type=Path, required=True)
    args = parser.parse_args()
    print(verify(args.stage, args.original_root))
    print('PASS clean native/config-only reader and exact map/scenario/payload membership')
