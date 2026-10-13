"""Add one game-owned timer to pinned damage-only resources. Never touch template."""
import argparse
import hashlib
import struct
from pathlib import Path

MAP_PIN = '3e5fdfa9cb054ba1c17380ff5128aac8ddd8b72dc5f2d5059e14121cf67d2fad'
SCRIPT_PIN = 'd3b9df97d63f8fe8558e584ab9e5a058728317845366b81c85423e6d5a41b15f'
PREVIOUS_MAP_PIN = '34b23dd725c9ae23d013b6cdbe21d917f42546f43d40ae6387650f5b54e70801'
PREVIOUS_SCRIPT_PIN = 'ec85633c1bb9dbb3be4b4cda5d38c1fcf60e5a20d9dafc591debd589d3214dd2'
CURRENT_MAP_PIN = 'c0c10a6e796d2581f5b679edbe7b50466de4cdd91070352577dba6566280753a'
CURRENT_SCRIPT_PIN = 'f49092402132cd4b890369f2fec2054215cba2656b99afbb85f7e7369bc48dd1'
LIFE_MAP_PIN = '1d7fc983b163e19f554bd741e11cbee65abaff8b0c315acbed9c98db68b31983'
LIFE_SCRIPT_PIN = 'd2f6fcac14819627a882823b60f545d67d1e9a3ecd38afde4383a4929bf20e63'

RELAYS = b'''
{
"classname" "logic_relay"
"targetname" "gp_wolf_regen_start"
"StartDisabled" "0"
"spawnflags" "0"
"OnTrigger" "werewolf,WolfRegenStart,,0,-1,,"
"origin" "0 0 0"
}
{
"classname" "logic_relay"
"targetname" "gp_wolf_regen_stop"
"StartDisabled" "0"
"spawnflags" "0"
"OnTrigger" "werewolf,WolfRegenStop,,0,-1,,"
"origin" "0 0 0"
}
'''


def build_map(raw):
    digest = hashlib.sha256(raw).hexdigest()
    if digest == LIFE_MAP_PIN:
        return raw
    if digest not in (MAP_PIN, PREVIOUS_MAP_PIN, CURRENT_MAP_PIN):
        raise ValueError('Unrecognized current map: preserve user changes, no generic replacement')
    offset, length = struct.unpack_from('<II', raw, 8)
    active = raw[offset:offset + length]
    if digest == CURRENT_MAP_PIN:
        pass
    elif digest == PREVIOUS_MAP_PIN:
        # Repair only the exact preceding candidate; never touch geometry or
        # unrelated entities. These Source-generic events do not exist in VTMB.
        for line in (b'"OnUser1" "werewolf,WolfRegenStart,,0,-1,,"\n',
                     b'"OnUser2" "werewolf,WolfRegenStop,,0,-1,,"\n'):
            if active.count(line) != 1:
                raise ValueError('Unexpected previous timer output')
            active = active.replace(line, b'', 1)
        active = active.rstrip(b'\0') + RELAYS + b'\0'
    elif b'gp_wolf_regen_' in active:
        raise ValueError('Existing timer must not be duplicated')
    else:
        active = active.rstrip(b'\0') + b'''
{
"classname" "logic_timer"
"targetname" "gp_wolf_regen_timer"
"StartDisabled" "1"
"UseRandomTime" "0"
"RefireTime" "0.1"
"spawnflags" "0"
"OnTimer" "werewolf,WolfRegenTick,,0,-1,,"
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
''' + RELAYS + b'\0'
    # These callbacks run after the real battle reveal / after world readiness.
    active = active.replace(b'"OnMapSpawn" ",,,0,-1,nativeWolfRegenSetup(),"\n', b'')
    active = active.replace(b'"OnMapLoad" ",,,0,-1,nativeWolfRegenSetup(),"',
                            b'"OnMapLoad" ",,,0,-1,nativeWolfRegenLoad(),"')
    from probe_map import ENTITY, TARGET
    text = active.rstrip(b'\0').decode('latin1')
    seen = False
    def battle(match):
        nonlocal seen
        block = match.group(); target = TARGET.search(block)
        if target and target.group(1) == 'cutscene_end':
            if seen: raise ValueError('Duplicate battle reveal')
            seen = True
            block = block.replace('}', '"OnTrigger" ",,,0.1,-1,nativeWolfBattleStart(),"\n}', 1)
        return block
    text = ENTITY.sub(battle, text)
    if not seen: raise ValueError('Battle reveal missing')
    active = text.encode('latin1') + b'''
{
"classname" "logic_relay"
"targetname" "gp_wolf_regen_reset"
"StartDisabled" "0"
"spawnflags" "0"
"OnTrigger" "werewolf,WolfRegenReset,,0,-1,,"
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
    digest = hashlib.sha256(raw).hexdigest()
    if digest not in (SCRIPT_PIN, PREVIOUS_SCRIPT_PIN, CURRENT_SCRIPT_PIN, LIFE_SCRIPT_PIN):
        raise ValueError('Unrecognized current scenario script; no user changes overwritten')
    extension = Path(__file__).with_name('wolf_regeneration.py.template').read_bytes()
    extension = extension.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    if digest in (PREVIOUS_SCRIPT_PIN, CURRENT_SCRIPT_PIN, LIFE_SCRIPT_PIN):
        marker = b'# The native input wrapper performs HP access and keeps queued ticks disarmed.'
        if raw.count(marker) != 1:
            raise ValueError('Unexpected previous regeneration functions')
        return raw[:raw.index(marker)] + extension
    text = raw.decode('latin1')
    def once(before, after):
        nonlocal text
        if text.count(before) != 1:
            raise ValueError('Unexpected scenario function')
        text = text.replace(before, after)
    once("def nativeWolfCrushStart():\r\n    G.GP_Wolf_CrushStarted = 1",
         "def nativeWolfCrushStart():\r\n    G.GP_Wolf_CrushStarted = 1\r\n    nativeWolfRegenStop()")
    once("def nativeWolfDeath():\r\n", "def nativeWolfDeath():\r\n    nativeWolfRegenStop()\r\n")
    return text.encode('latin1') + b'\r\n' + extension


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
