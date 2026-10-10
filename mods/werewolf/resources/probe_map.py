"""Build a diagnostic-only Griffith BSP from the accepted Frenzy map.

Only the active entity lump changes. This is not a gameplay payload.
"""

import hashlib
import re
import struct
from pathlib import Path


ACCEPTED_MAP_SHA256 = "6690798013dd82432a4c94f199111e35c5ca581bbc5ad351b0ba626ffec05cb7"
REMOVED = {"plus_check", "werewolf_melee", "werewolf_ranged", "werewolf_hit_counter"}
ENTITY = re.compile(r"\{[^{}]*\}\r?\n?", re.DOTALL)
TARGET = re.compile(r'"targetname"\s+"([^"]+)"')


def replace_once(text, before, after):
    count = text.count(before)
    if count != 1:
        raise ValueError("Expected one occurrence, found %d: %r" % (count, before))
    return text.replace(before, after, 1)


def build(data):
    if hashlib.sha256(data).hexdigest() != ACCEPTED_MAP_SHA256:
        raise ValueError("Not the pinned accepted UP/Frenzy Griffith map")
    if data[:4] != b"VBSP":
        raise ValueError("Not a BSP")
    offset, size = struct.unpack_from("<II", data, 8)
    if offset < 0x408 or size < 1 or offset + size > len(data):
        raise ValueError("Invalid entity lump")
    entities = data[offset:offset + size].decode("latin-1")
    removed = set()
    wolf_seen = False
    chunks = []
    cursor = 0
    for match in ENTITY.finditer(entities):
        chunks.append(entities[cursor:match.start()])
        block = match.group()
        name_match = TARGET.search(block)
        name = name_match.group(1) if name_match else None
        if name in REMOVED:
            if name in removed:
                raise ValueError("Duplicate removed target: " + name)
            removed.add(name)
            block = ""
        elif name == "werewolf":
            if wolf_seen or '"classname" "npc_VWerewolf"' not in block:
                raise ValueError("Unexpected werewolf entity")
            wolf_seen = True
            block = replace_once(block, '"OnDamaged" ",,,0,-1,fightWerewolf(),"\n', "")
            block = replace_once(block, '"OnDamaged" "plus_check,Test,,0,-1,,"\n', "")
            block = replace_once(
                block,
                '"OnFinishCrushAnimation" "player_stuff,AwardExp,Alliance04,0,-1,,"',
                '"OnDamaged" ",,,0,-1,gpWolfDamaged(),"\n'
                '"OnDeath" ",,,0,-1,gpWolfDeath(),"\n'
                '"OnFinishCrushAnimation" "player_stuff,AwardExp,Alliance04,0,-1,,"',
            )
        chunks.append(block)
        cursor = match.end()
    chunks.append(entities[cursor:])
    if removed != REMOVED or not wolf_seen:
        raise ValueError("Missing counter entities or werewolf")
    patched = "".join(chunks).rstrip("\0")
    if '"nofrenzyarea" "0"' not in patched or '"nofrenzyarea" "1"' in patched:
        raise ValueError("Accepted Frenzy permission was lost")
    patched += (
        '\r\n{\r\n"classname" "logic_auto"\r\n"spawnflags" "0"\r\n'
        '"OnMapSpawn" ",,,0.5,-1,gpWolfStart(),"\r\n'
        '"OnMapLoad" ",,,0.5,-1,gpWolfStart(),"\r\n'
        '"origin" "0 0 0"\r\n}\r\n\0'
    )
    new_lump = patched.encode("latin-1")
    new_offset = (len(data) + 3) & ~3
    result = bytearray(data)
    result.extend(b"\0" * (new_offset - len(result)))
    result.extend(new_lump)
    struct.pack_into("<II", result, 8, new_offset, len(new_lump))
    return bytes(result)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    out = build(args.source.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(out)
    print(hashlib.sha256(out).hexdigest())
