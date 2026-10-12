"""No game launch; timer structure and Python lifetime guards against real input."""
import argparse
import hashlib
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'resources'))
from build_regeneration import build_map, build_script
from probe_map import ENTITY, TARGET
GAME = None

class RegenResources(unittest.TestCase):
    def test_map_adds_only_one_timer_and_loader(self):
        raw = (GAME / 'Unofficial_Patch/maps/sp_observatory_2.bsp').read_bytes()
        new = build_map(raw)
        self.assertEqual(new[:8], raw[:8])
        self.assertEqual(new[16:len(raw)], raw[16:])
        def lump(data):
            off, n = struct.unpack_from('<II', data, 8)
            return data[off:off+n].rstrip(b'\0')
        old_entities = [m.group() for m in ENTITY.finditer(lump(raw).decode('latin1'))]
        new_entities = [m.group() for m in ENTITY.finditer(lump(new).decode('latin1'))]
        self.assertEqual(new_entities[:len(old_entities)], old_entities)
        self.assertEqual(len(new_entities), len(old_entities) + 2)
        self.assertEqual(lump(new).count(b'"targetname" "gp_wolf_regen_timer"'), 1)
        self.assertIn(b'"RefireTime" "0.1"', lump(new))
        self.assertIn(b'"OnMapLoad" ",,,0,-1,nativeWolfRegenSetup(),"', lump(new))
        with self.assertRaises(ValueError): build_map(new)

    def test_scenario_dead_crush_load_and_duplicates(self):
        raw = (GAME / 'Unofficial_Patch/python/griffith/griffith.py').read_bytes()
        new = build_script(raw).decode('latin1')
        namespace = {'G': SimpleNamespace(Werewolf_Dead=0), 'Find': lambda name: None}
        events = []
        class Timer:
            def Disable(self): events.append('disable')
            def Enable(self): events.append('enable')
            def FireUser1(self): events.append('start')
            def FireUser2(self): events.append('stop')
        timer = Timer()
        namespace['__main__'] = SimpleNamespace(FindEntitiesByName=lambda name: [timer])
        namespace['Find'] = lambda name: timer if name == 'gp_wolf_regen_timer' else None
        # Only execute our Python2-compatible appended functions.
        exec(new[new.index('# Native Griffith combat completion;'):], namespace)
        namespace['nativeWolfRegenSetup']()
        self.assertEqual(events, ['disable', 'start', 'enable'])
        events.clear(); namespace['nativeWolfCrushStart']()
        self.assertEqual(events, ['stop', 'disable'])
        events.clear(); namespace['nativeWolfRegenSetup']()
        self.assertEqual(events, ['disable', 'stop'])
        namespace['G'].GP_Wolf_CrushStarted = 0; namespace['G'].Werewolf_Dead = 1
        events.clear(); namespace['nativeWolfRegenSetup']()
        self.assertEqual(events, ['disable', 'stop'])
        namespace['__main__'].FindEntitiesByName = lambda name: [timer, timer]
        events.clear(); namespace['nativeWolfRegenSetup']()
        self.assertEqual(events, ['stop', 'disable', 'stop', 'disable'])
        namespace['__main__'].FindEntitiesByName = lambda name: []
        events.clear(); namespace['nativeWolfRegenSetup'](); self.assertEqual(events, [])
        with self.assertRaises(ValueError): build_script(new.encode('latin1'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-root', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    GAME = args.game_root
    unittest.main(argv=[sys.argv[0]]+remaining, verbosity=2)
