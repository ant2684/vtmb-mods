"""Regression checks for pointer relocation, graph termination and preservation."""
import unittest
import os
from pathlib import Path
from combo_models import (ACCEPTED, CHAINS, DONORS, build_model, combat_string,
                          integer, payloads, put, sequences, verify_model)

RELEASES = Path(os.environ.get('VTMB_RELEASES', str(Path(__file__).resolve().parents[2] / 'VTMB Final Releases')))

class ComboTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = []
        for edition, digest in ACCEPTED.items():
            data = payloads(RELEASES / f'VTMB Protean Claws Hit Fix 1.2.0 - {edition}.zip', digest)
            cls.inputs.extend((edition + '/' + path, value) for path, value in data.items()
                              if path.endswith('/claws.mdl'))

    def test_all_editions_both_sexes(self):
        for name, data in self.inputs:
            with self.subTest(name=name):
                result = build_model(data)
                verify_model(data, result)
                self.assertEqual(result, build_model(data))
                nodes = sequences(result)
                for chain in CHAINS.values():
                    self.assertIsNone(combat_string(result, nodes[chain[-1]], 744))

    def test_reject_already_patched_model(self):
        with self.assertRaises(ValueError):
            build_model(build_model(self.inputs[0][1]))

    def test_corruptions_are_detected(self):
        original = self.inputs[0][1]
        result = build_model(original)
        nodes = sequences(result)
        cases = []
        broken = bytearray(result)
        put(broken, nodes['claws_pi_left4'] + 744, -2)
        cases.append(broken)
        broken = bytearray(result)
        pos = nodes['claws_pi_left3']
        put(broken, pos + 744, -integer(broken, pos + 744))
        cases.append(broken)
        broken = bytearray(result)
        put(broken, nodes['claws_pi_right3'] + 12, 1)
        cases.append(broken)
        broken = bytearray(result)
        broken[nodes['claws_pi_left3'] + 56] ^= 1
        cases.append(broken)
        broken = bytearray(result)
        broken[0x300] ^= 1
        cases.append(broken)
        broken = bytearray(result)
        put(broken, nodes['claws_pi_left3'] + 24, integer(broken, nodes['claws_pi_left3'] + 24) + 4)
        cases.append(broken)
        for index, broken in enumerate(cases):
            with self.subTest(corruption=index):
                with self.assertRaises((AssertionError, ValueError)):
                    verify_model(original, broken)

if __name__ == '__main__':
    unittest.main()
