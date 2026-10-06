"""Keep environmental preparation failures separate from Console behavior."""
import tempfile
import unittest
from pathlib import Path
from infra.core import ROOT, Blocked, Failure, atomic_json, read_json
from infra.console_supported import preparation_error, preserve_first_error, supported_recipe


class ConsolePreparationTests(unittest.TestCase):
    def test_foreground_failure_before_behavior_blocks(self):
        original = RuntimeError('Owned game lost foreground; input halted')
        self.assertIsInstance(preparation_error(original, {'behavior_started': False}), Blocked)
        self.assertIs(preparation_error(original, {'behavior_started': True}), original)

    def test_failed_behavior_expectation_is_not_reclassified(self):
        original = Failure('native world did not resume')
        self.assertIs(preparation_error(original, {'behavior_started': False}), original)

    def test_first_failure_receipt_survives_diagnostic_failure(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            atomic_json(folder / 'process.json', {'Id': 1, 'Ticks': 2})
            state = {'behavior_started': False, 'driver': None}
            preserve_first_error(folder, RuntimeError('first failure'), state)
            first = (folder / 'console-first-error.json').read_bytes()
            preserve_first_error(folder, RuntimeError('later failure'), state)
            self.assertEqual((folder / 'console-first-error.json').read_bytes(), first)
            self.assertEqual(read_json(folder / 'console-first-error.json')['phase'], 'preparation')

    def test_recipe_has_explicit_preparation_boundary(self):
        path = ROOT / 'mods/console/tests/gameplay/console_clean.py'
        source = path.read_text() if path.exists() else "time.sleep(25);d=Driver(session)\n for closing in ('x','tilde'):\n  command='load rc_console'\n"
        recipe = supported_recipe(source, 'rc_fixture')
        self.assertIn('_prepare_driver(session,Driver)', recipe)
        self.assertIn('_start_behavior(d)', recipe)
        with self.assertRaises(Failure):
            supported_recipe(source.replace('time.sleep(25);d=Driver(session)', ''), 'rc_fixture')
