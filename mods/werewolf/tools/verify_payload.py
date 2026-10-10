"""Exact experimental payload allowlist and clean-binary/resource gate."""
import argparse
import hashlib
import struct
from pathlib import Path

PINNED = {
    'Bin/loader/griffith-wolf-native-damage.vtm': '4f1dc7b0244049593adeb19cada3e7367d4a80ed9d9450d0f544ee9ac241b64c',
    'Unofficial_Patch/maps/sp_observatory_2.bsp': '3e5fdfa9cb054ba1c17380ff5128aac8ddd8b72dc5f2d5059e14121cf67d2fad',
    'Unofficial_Patch/python/griffith/griffith.py': 'd3b9df97d63f8fe8558e584ab9e5a058728317845366b81c85423e6d5a41b15f',
    'Unofficial_Patch/vdata/system/npctemplate001.txt': 'e82a5769694109619917d00a5c2c4a393d86b91cfd41ec1753f42cb4e651ea49',
}


def verify(files):
    if set(files) != set(PINNED) | {'README.txt', 'ENEMY_REFERENCE.md'}:
        raise ValueError('Unexpected or missing payload member')
    for name, wanted in PINNED.items():
        if hashlib.sha256(files[name]).hexdigest() != wanted:
            raise ValueError('Candidate byte mismatch: ' + name)
    if not files['README.txt'].startswith(b'Griffith Park Werewolf'):
        raise ValueError('Manual English README missing')
    if not files['ENEMY_REFERENCE.md'].startswith(b'# Enemy damage and discipline reference'):
        raise ValueError('English enemy reference missing')
    raw = files['Bin/loader/griffith-wolf-native-damage.vtm']
    for marker in [b'.pdb', b'gp_wolf_diagnostics', b'GP_WOLF_DAMAGE_LOG', b'OutputDebugString', b'CreateFile']:
        if marker.lower() in raw.lower():
            raise ValueError('Diagnostic binary debris')
    # Direct PE debug/export directory checks without optional dependencies.
    pe = struct.unpack_from('<I', raw, 0x3c)[0]
    optional = pe + 24
    if raw[:2] != b'MZ' or raw[pe:pe + 4] != b'PE\0\0' or struct.unpack_from('<H', raw, optional)[0] != 0x10b:
        raise ValueError('Not a PE32 VTM')
    if struct.unpack_from('<II', raw, optional + 96 + 6 * 8) != (0, 0):
        raise ValueError('Debug directory present')
    mapdata = files['Unofficial_Patch/maps/sp_observatory_2.bsp']
    off, length = struct.unpack_from('<II', mapdata, 8)
    active = mapdata[off:off + length]
    for marker in [b'werewolf_hit_counter', b'TakeDamage', b'fightWerewolf()', b'gpWolfStart', b'gpWolfDamaged', b'gpWolfDeath']:
        if marker in active:
            raise ValueError('Old damage path/diagnostic map output')
    script = files['Unofficial_Patch/python/griffith/griffith.py']
    if any(marker in script for marker in [b'gp_wolf_probe', b'game-probe.log', b'NATIVE_FINISH_BEFORE']):
        raise ValueError('Diagnostic Python debris')
    return {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('payload', type=Path)
    root = parser.parse_args().payload
    files = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    verify(files)
    print('PASS exact candidate, payload allowlist, documentation and clean PE/resources')
