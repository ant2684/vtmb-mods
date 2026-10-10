"""Export byte-identical test game layout and its portable source capsule."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
REPO = MOD.parents[1]
sys.path.insert(0, str(MOD / 'resources'))
from wolf_resources import build_map, build_template, build_script
from verify_payload import PINNED, verify


def archive(path, files):
    if path.exists():
        raise FileExistsError('Refusing archive overwrite: ' + str(path))
    with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, raw)
    with zipfile.ZipFile(path) as zipped:
        if zipped.testzip() or len(zipped.namelist()) != len(files):
            raise ValueError('Archive CRC/count failure')
        if {name: zipped.read(name) for name in zipped.namelist()} != files:
            raise ValueError('Archive changed member bytes')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(game, originals, output):
    if game.resolve() == originals.resolve():
        raise ValueError('Original resources must be preserved separately')
    generated = {
        'Unofficial_Patch/maps/sp_observatory_2.bsp': build_map((originals / 'Unofficial_Patch/maps/sp_observatory_2.bsp').read_bytes()),
        'Unofficial_Patch/vdata/system/npctemplate001.txt': build_template((originals / 'Unofficial_Patch/vdata/system/npctemplate001.txt').read_bytes()),
        'Unofficial_Patch/python/griffith/griffith.py': build_script((originals / 'Unofficial_Patch/python/griffith/griffith.py').read_bytes()),
        'Bin/loader/griffith-wolf-native-damage.vtm': (game / 'Bin/loader/griffith-wolf-native-damage.vtm').read_bytes(),
    }
    for name, data in generated.items():
        if data != (game / name).read_bytes():
            raise ValueError('Reconstruction differs from installed gameplay bytes: ' + name)
    generated['README.txt'] = (MOD / 'docs/manual_README.txt').read_bytes()
    generated['ENEMY_REFERENCE.md'] = (MOD / 'docs/ENEMY_REFERENCE.md').read_bytes()
    identities = verify(generated)
    output.mkdir(parents=True, exist_ok=True)
    name = 'VTMB Griffith Werewolf - Test 2026-10-10'
    payload = output / name
    if payload.exists():
        raise FileExistsError('Payload directory occupied')
    payload.mkdir()
    for relative, data in generated.items():
        path = payload / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    if {p.relative_to(payload).as_posix(): p.read_bytes() for p in payload.rglob('*') if p.is_file()} != generated:
        raise ValueError('Staged payload differs')
    gamezip = output / (name + '.zip')
    gamehash = archive(gamezip, generated)
    source = {}
    for path in MOD.rglob('*'):
        rel = path.relative_to(MOD)
        if not path.is_file() or any(part in ['build', '__pycache__'] for part in rel.parts) or path.name == 'README.md':
            continue
        if path.suffix.lower() in ['.exe', '.dll', '.vtm', '.zip', '.pyc', '.sav', '.bsp', '.pdb', '.lib']:
            raise ValueError('Forbidden source-capsule member')
        source['mods/werewolf/' + rel.as_posix()] = path.read_bytes()
    source['README.md'] = (MOD / 'README.md').read_bytes()
    for relative in ['infra/common/native_fixture.h', 'infra/common/finalize_pe.py', 'LICENSE', 'NOTICE']:
        source[relative] = (REPO / relative).read_bytes()
    if sum(Path(n).name.lower() == 'readme.md' for n in source) != 1:
        raise ValueError('Source README count')
    sourcezip = output / (name + ' Source.zip')
    sourcehash = archive(sourcezip, source)
    return {'payload': str(payload), 'game_zip': str(gamezip), 'game_sha256': gamehash,
            'source_zip': str(sourcezip), 'source_sha256': sourcehash,
            'source_members': len(source), 'game_members': len(generated),
            'member_sha256': identities, 'installed_gameplay_bytes_unchanged': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-root', type=Path, required=True)
    parser.add_argument('--original-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.game_root, args.original_root, args.output), indent=2))
