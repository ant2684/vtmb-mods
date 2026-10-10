"""Pinned, minimal native-combat resources. No diagnostic outputs in build_map."""
import hashlib
import struct
from pathlib import Path

from probe_map import ACCEPTED_MAP_SHA256, ENTITY, TARGET, REMOVED, replace_once

TEMPLATE_SHA256 = 'f988669f14c7da03043f8e97ce8ff1ab74ee70fa2221a742ae7899690a992b0a'
SCRIPT_SHA256 = 'cf2a2b1d5bdb556423dd18cb36a88757be51ba8201d11a4c54c81299b45ba096'


def pinned(data, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Resource does not match pinned UP 11.5 Plus original')


def build_map(data):
    pinned(data, ACCEPTED_MAP_SHA256)
    offset, size = struct.unpack_from('<II', data, 8)
    entities = data[offset:offset + size].decode('latin1')
    removed, wolf_seen = set(), False
    chunks, cursor = [], 0
    for match in ENTITY.finditer(entities):
        chunks.append(entities[cursor:match.start()])
        block = match.group()
        target = TARGET.search(block)
        name = target.group(1) if target else None
        if name in REMOVED:
            if name in removed:
                raise ValueError('Duplicate synthetic entity')
            removed.add(name)
            block = ''
        elif name == 'werewolf':
            if wolf_seen or '"classname" "npc_VWerewolf"' not in block:
                raise ValueError('Unexpected Werewolf')
            wolf_seen = True
            for line in ('"OnDamaged" ",,,0,-1,fightWerewolf(),"\n',
                         '"OnDamaged" "plus_check,Test,,0,-1,,"\n',
                         '"OnFinishCrushAnimation" ",,,0,-1,G.Werewolf_Dead = 1,"\n'):
                block = replace_once(block, line, '')
            block = replace_once(block,
                '"OnFinishCrushAnimation" "player_stuff,AwardExp,Alliance04,0,-1,,"',
                '"OnDeath" ",,,0,-1,nativeWolfDeath(),"\n'
                '"OnBeginCrushAnimation" ",,,0,-1,nativeWolfCrushStart(),"\n'
                '"OnFinishCrushAnimation" ",,,0,-1,nativeWolfReward(),"')
        chunks.append(block)
        cursor = match.end()
    chunks.append(entities[cursor:])
    if removed != REMOVED or not wolf_seen:
        raise ValueError('Incomplete map replacement')
    lump = ''.join(chunks).encode('latin1')
    new_offset = (len(data) + 3) & ~3
    result = bytearray(data)
    result.extend(bytes(new_offset - len(data)))
    result.extend(lump)
    struct.pack_into('<II', result, 8, new_offset, len(lump))
    return bytes(result)


def build_template(data, low=False):
    pinned(data, TEMPLATE_SHA256)
    begin = data.index(b'"TemplateName"\t\t\t"Werewolf"')
    end = data.index(b'ClanData', begin)
    text = data[begin:end].decode('ascii')
    if low:
        # Retained historical diagnostic profile; never a gameplay payload.
        text = replace_once(text, '"Stamina"\t\t\t"5"', '"Stamina"\t\t\t"1"')
        text = replace_once(text, '"Wits"\t\t\t\t"6"', '"Wits"\t\t\t\t"1"')
        text = replace_once(text, '"Dodge"\t\t\t\t"5"', '"Dodge"\t\t\t\t"0"')
        text = replace_once(text, '"Max_Health"\t\t\t"80"',
                            '"Max_Health"\t\t\t"80"\r\n\t\t\t"Soak_Pool"\t\t\t"0"')
    else:
        text = replace_once(text, '"Max_Health"\t\t\t"80"', '"Max_Health"\t\t\t"900"')
        text = replace_once(text, '\t\t\t"HasTrueSight"\t\t\t"1"\r\n', '')
        text = replace_once(text, '"DisciplineStrata"\t\t"7"', '"DisciplineStrata"\t\t"6"')
        text = replace_once(text, '\t\t\t"Kindred"\t\t\t\t"0"',
            '\t\t\t"HasTrueSight"\t\t\t"1"\r\n'
            '\t\t\t"TrueSightVisionDistance"\t"150"\r\n'
            '\t\t\t"DamageFilterBashing"\t\t"0.20"\r\n'
            '\t\t\t"DamageFilterLethal"\t\t"0.40"\r\n'
            '\t\t\t"DamageFilterAggravated"\t\t"1.00"\r\n'
            '\t\t\t"DamageFilterFlame"\t\t"1.00"\r\n'
            '\t\t\t"Kindred"\t\t\t\t"0"')
    return data[:begin] + text.encode('ascii') + data[end:]


def build_script(data):
    pinned(data, SCRIPT_SHA256)
    source = Path(__file__).with_name('wolf_scenario.py.template').read_bytes()
    return data + b'\r\n' + source.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')


def diagnostic_map(data):
    """Scenario resources plus observers, never a release candidate."""
    result = bytearray(build_map(data))
    offset, size = struct.unpack_from('<II', result, 8)
    text = result[offset:offset + size].decode('latin1')
    text = replace_once(text, '"OnDeath" ",,,0,-1,nativeWolfDeath(),"',
                        '"OnDamaged" ",,,0,-1,gpWolfDamaged(),"\n'
                        '"OnDeath" ",,,0,-1,gpWolfDeath(),"\n'
                        '"OnDeath" ",,,0,-1,nativeWolfDeath(),"')
    text = text.rstrip('\0') + (
        '\n{\n"classname" "logic_auto"\n"spawnflags" "0"\n'
        '"OnMapSpawn" ",,,0.5,-1,gpWolfStart(),"\n'
        '"OnMapLoad" ",,,0.5,-1,gpWolfStart(),"\n"origin" "0 0 0"\n}\n\0')
    result[offset:] = text.encode('latin1')
    struct.pack_into('<I', result, 12, len(result) - offset)
    return bytes(result)
