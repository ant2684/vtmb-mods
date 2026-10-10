"""Offline resource regressions; proprietary fixture paths are explicit inputs."""
import argparse
import re
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'resources'))
from wolf_resources import build_map, build_template, build_script
from probe_map import ENTITY, TARGET, REMOVED

ORIGINALS = None


def blocks(data):
    off, size = struct.unpack_from('<II', data, 8)
    found = {}
    for match in ENTITY.finditer(data[off:off + size].decode('latin1')):
        name = TARGET.search(match.group())
        if name:
            found.setdefault(name.group(1), []).append(match.group())
    return found


class Resources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ORIGINALS is None:
            raise RuntimeError('Explicit preserved original-root required; not a synthetic gameplay PASS')
        cls.map = (ORIGINALS / 'Unofficial_Patch/maps/sp_observatory_2.bsp').read_bytes()
        cls.template = (ORIGINALS / 'Unofficial_Patch/vdata/system/npctemplate001.txt').read_bytes()
        cls.script = (ORIGINALS / 'Unofficial_Patch/python/griffith/griffith.py').read_bytes()

    def test_wolf_only_profile_and_legacy_preserved(self):
        data = self.template
        result = build_template(data)
        begin = data.index(b'"TemplateName"\t\t\t"Werewolf"')
        end = data.index(b'ClanData', begin)
        self.assertEqual(result[:begin], data[:begin])
        self.assertTrue(result.endswith(data[end:]))
        text = result[begin:result.index(b'ClanData', begin)]
        for name, value in [('Max_Health', '900'), ('Stamina', '5'), ('Wits', '6'),
                            ('Dodge', '5'), ('Dexterity', '1'), ('DisciplineStrata', '6'),
                            ('HasTrueSight', '1'), ('TrueSightVisionDistance', '150'),
                            ('DamageFilterBashing', '0.20'), ('DamageFilterLethal', '0.40'),
                            ('DamageFilterAggravated', '1.00'), ('DamageFilterFlame', '1.00')]:
            self.assertEqual(re.findall(rb'"' + name.encode() + rb'"\s+"([0-9.]+)"', text), [value.encode()])
        self.assertNotIn(b'"Soak_Pool"', text)
        def section(raw, key):
            return re.search(rb'\b' + key + rb'\s*\{([^{}]*)\}', raw).group(1)
        self.assertEqual(section(text, b'Resistances'), section(data[begin:end], b'Resistances'))
        self.assertNotIn(b'HasTrueSight', section(text, b'Attributes'))
        self.assertIn(b'HasTrueSight', section(text, b'General'))

    def test_map_scope_crush_and_no_synthetic_damage(self):
        result = build_map(self.map)
        self.assertEqual(result[:8], self.map[:8])
        self.assertEqual(result[16:len(self.map)], self.map[16:])
        old, new = blocks(self.map), blocks(result)
        self.assertEqual(set(old) - set(new), REMOVED)
        for name in set(new) - {'werewolf'}:
            self.assertEqual(new[name], old[name], name)
        excluded = ('"OnDamaged"', '"OnDeath"', 'nativeWolf', 'AwardExp,Alliance04', 'G.Werewolf_Dead')
        self.assertEqual([s for s in old['werewolf'][0].splitlines() if not any(t in s for t in excluded)],
                         [s for s in new['werewolf'][0].splitlines() if not any(t in s for t in excluded)])
        off, size = struct.unpack_from('<II', result, 8)
        for marker in [b'TakeDamage', b'fightWerewolf()', b'werewolf_hit_counter', b'gpWolfStart']:
            self.assertNotIn(marker, result[off:off + size])

    def completion(self):
        source = build_script(self.script)[len(self.script):].decode()
        self.assertNotIn('killWerewolf', source)
        self.assertNotIn('.Kill(', source)
        events = []
        class Entity:
            def __init__(self, name): self.name = name
            def AwardExp(self, key): events.append((self.name, key))
            def PlaySound(self): events.append((self.name, 'sound'))
            def Hide(self): events.append((self.name, 'hide'))
            def Trigger(self): events.append((self.name, 'trigger'))
        state = SimpleNamespace(Werewolf_Dead=0)
        context = {'G': state, 'Find': lambda name: Entity(name),
                   '__main__': SimpleNamespace(FindEntitiesByName=lambda name: [Entity(name)])}
        exec(source, context)
        return context, state, events

    def test_death_reward_guard_and_restored_globals(self):
        context, state, events = self.completion()
        context['nativeWolfDeath']()
        context['nativeWolfDeath']()
        context['nativeWolfReward']()
        self.assertEqual(events, [('player_stuff', 'Alliance04'), ('werewolf_death', 'sound'),
                                  ('tram_timer', 'hide'), ('tram_to_station', 'trigger')])
        restored = SimpleNamespace(**vars(state))
        context['G'] = restored
        context['nativeWolfDeath']()
        self.assertEqual(len(events), 4)

    def test_crush_only_common_reward_not_duplicate_tram(self):
        context, state, events = self.completion()
        context['nativeWolfCrushStart']()
        context['nativeWolfDeath']()
        self.assertEqual(events, [])
        context['nativeWolfReward']()
        context['nativeWolfDeath']()
        context['nativeWolfReward']()
        self.assertEqual(events, [('player_stuff', 'Alliance04')])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--original-root', required=True, type=Path)
    ORIGINALS = parser.parse_args().original_root
    unittest.main(argv=[sys.argv[0]], verbosity=2)
