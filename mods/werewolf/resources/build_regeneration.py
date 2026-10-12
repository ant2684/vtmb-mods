"""Add one game-owned timer to pinned damage-only resources. Never touch template."""
import argparse
import hashlib
import struct
from pathlib import Path

MAP_PIN = '3e5fdfa9cb054ba1c17380ff5128aac8ddd8b72dc5f2d5059e14121cf67d2fad'
SCRIPT_PIN = 'd3b9df97d63f8fe8558e584ab9e5a058728317845366b81c85423e6d5a41b15f'


def build_map(raw):
    if hashlib.sha256(raw).hexdigest() != MAP_PIN:
        raise ValueError('Unrecognized current map: preserve user changes, no generic replacement')
    offset, length = struct.unpack_from('<II', raw, 8)
    active = raw[offset:offset + length]
    if b'gp_wolf_regen_' in active:
        raise ValueError('Existing timer must not be duplicated')
    active = active.rstrip(b'\0') + b'''
{
"classname" "logic_timer"
"targetname" "gp_wolf_regen_timer"
"StartDisabled" "1"
"UseRandomTime" "0"
"RefireTime" "0.1"
"spawnflags" "0"
"OnTimer" "werewolf,WolfRegenTick,,0,-1,,"
"OnUser1" "werewolf,WolfRegenStart,,0,-1,,"
"OnUser2" "werewolf,WolfRegenStop,,0,-1,,"
"origin" "0 0 0"
}
{
"classname" "logic_auto"
"targetname" "gp_wolf_regen_init"
"spawnflags" "0"
"OnMapSpawn" ",,,0,-1,nativeWolfRegenSetup(),"
"OnMapLoad" ",,,0,-1,nativeWolfRegenSetup(),"
"origin" "0 0 0"
}
\0'''
    result = bytearray(raw)
    new_offset = (len(result) + 3) & ~3
    result.extend(bytes(new_offset - len(result)))
    result.extend(active)
    struct.pack_into('<II', result, 8, new_offset, len(active))
    return bytes(result)


def build_script(raw):
    if hashlib.sha256(raw).hexdigest() != SCRIPT_PIN:
        raise ValueError('Unrecognized current scenario script; no user changes overwritten')
    text = raw.decode('latin1')
    def once(before, after):
        nonlocal text
        if text.count(before) != 1:
            raise ValueError('Unexpected scenario function')
        text = text.replace(before, after)
    once("def nativeWolfCrushStart():\r\n    G.GP_Wolf_CrushStarted = 1",
         "def nativeWolfCrushStart():\r\n    G.GP_Wolf_CrushStarted = 1\r\n    nativeWolfRegenStop()")
    once("def nativeWolfDeath():\r\n", "def nativeWolfDeath():\r\n    nativeWolfRegenStop()\r\n")
    extension = Path(__file__).with_name('wolf_regeneration.py.template').read_bytes()
    return text.encode('latin1') + b'\r\n' + extension.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Refusing occupied stage')
    for name, builder in [('Unofficial_Patch/maps/sp_observatory_2.bsp', build_map),
                          ('Unofficial_Patch/python/griffith/griffith.py', build_script)]:
        path = args.output / name
        data = builder((args.game_root / name).read_bytes())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(name, hashlib.sha256(data).hexdigest())
