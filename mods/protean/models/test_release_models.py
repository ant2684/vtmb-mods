"""Run the preserved original regressions using current-release resources."""
import os
import unittest
from pathlib import Path
import rebuild_models as release
import test_combo_models as regression

class ReleaseComboTests(regression.ComboTests):
    @classmethod
    def setUpClass(cls):
        releases = Path(os.environ['VTMB_RELEASES'])
        cls.inputs = []
        for edition in release.EDITIONS:
            files = release.read_inputs(releases, edition)
            cls.inputs.extend((edition + '/' + path,
                               release.baseline(data, edition, path.split('/')[-2]))
                              for path, data in files.items() if path.endswith('/claws.mdl'))

    def test_unknown_current_resource_rejected(self):
        data = bytearray(release.build_model(self.inputs[0][1]))
        data[0x300] ^= 1
        with self.assertRaises(ValueError):
            release.baseline(data, 'Default Block', 'female')

if __name__ == '__main__':
    unittest.main()
