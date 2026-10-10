"""Portable parser, package-refusal and private-path regressions."""
import sys
import unittest
from pathlib import Path

MOD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD / 'tools'))
from inspect_enemies import parse, children, descendants, values
from verify_payload import verify, PINNED


class Inspection(unittest.TestCase):
    def test_duplicate_rules_and_empty_parent_preserved(self):
        rows = parse('Root { Text { "ParentTemplateName" "" } Affects_Table { "x" "1" } // comment\n Affects_Table { "x" "2" } }')
        root = children(rows, 'Root')[0]
        self.assertEqual(values(children(root, 'Text')[0])['ParentTemplateName'], '')
        self.assertEqual([values(v)['x'] for v in descendants(root, 'Affects_Table')], ['1', '2'])

    def test_unbalanced_input_refused(self):
        for raw in ['Root { "x" "y"', '}', 'Root { key }', '{']:
            with self.assertRaises(ValueError):
                parse(raw)

    def test_quoted_comment_marker_preserved(self):
        self.assertEqual(values(parse('"link" "https://example.invalid/x" // ignored')),
                         {'link': 'https://example.invalid/x'})

    def test_payload_rejects_missing_extra_and_changed_bytes(self):
        with self.assertRaises(ValueError):
            verify({})
        fake = {name: b'wrong' for name in PINNED}
        fake.update({'README.txt': b'Griffith Park Werewolf', 'ENEMY_REFERENCE.md': b'# Enemy damage and discipline reference'})
        with self.assertRaises(ValueError):
            verify(fake)
        fake['debug.pdb'] = b'private'
        with self.assertRaises(ValueError):
            verify(fake)

    def test_public_source_has_no_workstation_paths(self):
        for path in MOD.rglob('*'):
            if not path.is_file() or 'build' in path.parts or '__pycache__' in path.parts:
                continue
            data = path.read_bytes().lower()
            for token in [b'c:' + b'\\' + b'users' + b'\\', b'c:' + b'/users/', b'd:' + b'\\' + b'personal projects', b'gpwolf' + b'p5.sav']:
                self.assertNotIn(token, data, path.name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
