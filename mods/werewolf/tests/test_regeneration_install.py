"""Installation/rollback against isolated copies, never the live game."""
import argparse
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import install_regeneration as impl
GAME = PLUGIN = None

class Installation(unittest.TestCase):
    def fixture(self, root):
        game = root / 'game'
        for name in [impl.VTM, impl.MAP, impl.SCRIPT]:
            p = game / name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes((GAME / name).read_bytes())
        for name, raw in [(impl.INI, b'[Regeneration]\nHPPerTick=3\n'),
                          (impl.CACHE, b'original-cache'), (impl.GRAPH, b'original-graph'),
                          ('Unofficial_Patch/vdata/system/npctemplate001.txt', b'custom-user-balance')]:
            p=game/name; p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        return game

    def test_complete_install_and_existing_ini_rollback(self):
        with tempfile.TemporaryDirectory(prefix='wolf_regen_install_') as d:
            root=Path(d);game=self.fixture(root)
            names=[impl.VTM,impl.INI,impl.MAP,impl.SCRIPT,impl.CACHE,impl.GRAPH]
            before={n:impl.snapshot(game/n) for n in names}
            with patch.object(impl,'idle'), contextlib.redirect_stdout(io.StringIO()):
                impl.install(game,PLUGIN,root/'stage')
                self.assertEqual((game/impl.INI).read_bytes(), b'[Regeneration]\nHPPerTick=3\n')
                self.assertFalse((game/impl.CACHE).exists())
                self.assertEqual((game/'Unofficial_Patch/vdata/system/npctemplate001.txt').read_bytes(),b'custom-user-balance')
                backup=next((game/'Mod_Backups').iterdir())
                impl.rollback(backup)
            for name,state in before.items():self.assertTrue(impl.matches(game/name,state),name)

    def test_failure_after_first_replacement_restores_owned_only(self):
        with tempfile.TemporaryDirectory(prefix='wolf_regen_failure_') as d:
            root=Path(d);game=self.fixture(root)
            before={n:impl.snapshot(game/n) for n in [impl.VTM,impl.INI,impl.MAP,impl.SCRIPT,impl.CACHE,impl.GRAPH]}
            original_replace=impl.os.replace; calls=[]
            def fail_second(src,dst):
                calls.append(dst)
                if len(calls)==2:raise OSError('synthetic interruption')
                original_replace(src,dst)
            with patch.object(impl,'idle'), patch.object(impl.os,'replace',fail_second),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(OSError):impl.install(game,PLUGIN,root/'stage')
            for name,state in before.items():self.assertTrue(impl.matches(game/name,state),name)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--game-root',type=Path,required=True)
    parser.add_argument('--plugin',type=Path,required=True)
    args,remaining=parser.parse_known_args();GAME,PLUGIN=args.game_root,args.plugin
    unittest.main(argv=[sys.argv[0]]+remaining,verbosity=2)
