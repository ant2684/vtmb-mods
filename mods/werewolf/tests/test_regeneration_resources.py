"""No game launch; timer structure and Python lifetime guards against real input."""
import argparse
import hashlib
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'resources'))
from build_regeneration import build_map, build_script, PREVIOUS_MAP_PIN
from probe_map import ENTITY, TARGET
GAME = None
CANDIDATE = None

class RegenResources(unittest.TestCase):
    def candidate(self, name, builder):
        raw = (GAME / name).read_bytes()
        expected = builder(raw)
        actual = (CANDIDATE / name).read_bytes() if CANDIDATE else expected
        self.assertEqual(actual, expected, 'Actual candidate differs from qualified builder output')
        return raw, actual

    def test_map_changes_only_scoped_timer_outputs_and_adds_relays(self):
        raw, new = self.candidate('Unofficial_Patch/maps/sp_observatory_2.bsp', build_map)
        self.assertEqual(new[:8], raw[:8])
        self.assertEqual(new[16:len(raw)], raw[16:])
        def lump(data):
            off, n = struct.unpack_from('<II', data, 8)
            return data[off:off+n].rstrip(b'\0')
        old_entities = [m.group() for m in ENTITY.finditer(lump(raw).decode('latin1'))]
        new_entities = [m.group() for m in ENTITY.finditer(lump(new).decode('latin1'))]
        previous = hashlib.sha256(raw).hexdigest() == PREVIOUS_MAP_PIN
        if previous:
            old_entities = [e.replace('"OnUser1" "werewolf,WolfRegenStart,,0,-1,,"\n', '')
                             .replace('"OnUser2" "werewolf,WolfRegenStop,,0,-1,,"\n', '')
                            for e in old_entities]
        self.assertEqual(new_entities[:len(old_entities)], old_entities)
        self.assertEqual(len(new_entities), len(old_entities) + (2 if previous else 4))
        self.assertEqual(lump(new).count(b'"targetname" "gp_wolf_regen_timer"'), 1)
        self.assertIn(b'"RefireTime" "0.1"', lump(new))
        self.assertIn(b'"OnMapLoad" ",,,0,-1,nativeWolfRegenSetup(),"', lump(new))
        self.assertNotIn(b'OnUser', lump(new))
        for name, action in [('start', 'Start'), ('stop', 'Stop')]:
            self.assertEqual(lump(new).count(('"targetname" "gp_wolf_regen_%s"' % name).encode()), 1)
            self.assertIn(('"OnTrigger" "werewolf,WolfRegen%s,,0,-1,,"' % action).encode(), lump(new))
        with self.assertRaises(ValueError): build_map(new)

    def test_scenario_dead_crush_load_and_duplicates(self):
        raw, new = self.candidate('Unofficial_Patch/python/griffith/griffith.py', build_script)
        new = new.decode('latin1')
        namespace = {'G': SimpleNamespace(Werewolf_Dead=0), 'Find': lambda name: None}
        events = []
        class Timer:
            def Disable(self): events.append('disable')
            def Enable(self): events.append('enable')
            # Deliberately NO FireUser methods: stock VTMB lacks this API.
        class Relay:
            def __init__(self, action): self.action = action
            def Trigger(self): events.append(self.action)
        timer = Timer()
        actors = {'gp_wolf_regen_timer': [timer], 'gp_wolf_regen_start': [Relay('start')],
                  'gp_wolf_regen_stop': [Relay('stop')]}
        namespace['__main__'] = SimpleNamespace(FindEntitiesByName=lambda name: actors.get(name, []))
        namespace['Find'] = lambda name: actors.get(name, [None])[0] if actors.get(name) else None
        # Only execute our Python2-compatible appended functions.
        exec(new[new.index('# Native Griffith combat completion;'):], namespace)
        namespace['nativeWolfRegenSetup']()
        self.assertEqual(events, ['disable', 'start', 'enable'])
        events.clear(); namespace['nativeWolfCrushStart']()
        self.assertEqual(events, ['disable', 'stop'])
        events.clear(); namespace['nativeWolfRegenSetup']()
        self.assertEqual(events, ['disable', 'stop'])
        namespace['G'].GP_Wolf_CrushStarted = 0; namespace['G'].Werewolf_Dead = 1
        events.clear(); namespace['nativeWolfRegenSetup']()
        self.assertEqual(events, ['disable', 'stop'])
        actors['gp_wolf_regen_timer'] = [timer, timer]
        events.clear(); namespace['nativeWolfRegenSetup']()
        self.assertEqual(events, ['disable', 'disable', 'stop'])
        actors.clear()
        events.clear(); namespace['nativeWolfRegenSetup'](); self.assertEqual(events, [])
        with self.assertRaises(ValueError): build_script(new.encode('latin1'))

    def test_combat_reward_still_runs_without_relays_in_serialized_map(self):
        self.completion(relays=False)

    def test_combat_reward_and_tram_once_with_valid_timer_api(self):
        self.completion(relays=True)

    def completion(self, relays):
        raw, new = self.candidate('Unofficial_Patch/python/griffith/griffith.py', build_script)
        new = new.decode('latin1')
        events = []
        class Timer:
            def Disable(self): events.append('disable')
            def Enable(self): events.append('enable')
        class Trigger:
            def __init__(self, name): self.name = name
            def Trigger(self): events.append(self.name)
        actors = {'gp_wolf_regen_timer': Timer(),
                  'player_stuff': SimpleNamespace(AwardExp=lambda key: events.append(key)),
                  'tram_timer': SimpleNamespace(Hide=lambda: events.append('hide')),
                  'tram_to_station': Trigger('tram')}
        if relays:
            actors.update(gp_wolf_regen_start=Trigger('start'), gp_wolf_regen_stop=Trigger('stop'))
        g = SimpleNamespace(Werewolf_Dead=0)
        namespace = {'G': g, 'Find': actors.get,
                     '__main__': SimpleNamespace(FindEntitiesByName=lambda name: [actors[name]] if name in actors else [])}
        exec(new[new.index('# Native Griffith combat completion;'):], namespace)
        # OnDeath, not TakeDamage/Kill/killWerewolf; the actor/API are mocks.
        namespace['nativeWolfDeath']()
        self.assertEqual(events.count('Alliance04'), 1)
        self.assertEqual(events.count('tram'), 1)
        self.assertEqual((g.GP_Wolf_Rewarded, g.Werewolf_Dead), (1, 1))
        # Re-loaded serialized G and duplicate OnDeath must not award again.
        namespace['G'] = SimpleNamespace(**vars(g))
        namespace['nativeWolfDeath']()
        self.assertEqual(events.count('Alliance04'), 1)
        self.assertEqual(events.count('tram'), 1)
        # Crush defers reward to animation finish and owns its tram outputs.
        namespace['G'] = SimpleNamespace(Werewolf_Dead=0)
        events.clear()
        namespace['nativeWolfCrushStart']()
        namespace['nativeWolfDeath']()
        self.assertNotIn('Alliance04', events)
        namespace['nativeWolfReward']()
        namespace['nativeWolfReward']()
        self.assertEqual(events.count('Alliance04'), 1)
        self.assertNotIn('tram', events)
        # Old serialized maps have no relays: disable/fail closed, no exception.
        if not relays:
            namespace['G'] = SimpleNamespace(Werewolf_Dead=0)
            events.clear(); namespace['nativeWolfRegenSetup']()
            self.assertEqual(events, ['disable'])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-root', type=Path, required=True)
    parser.add_argument('--candidate-root', type=Path, help='Exercise exact staged/installed resource bytes')
    args, remaining = parser.parse_known_args()
    GAME = args.game_root
    CANDIDATE = args.candidate_root
    unittest.main(argv=[sys.argv[0]]+remaining, verbosity=2)
