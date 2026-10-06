"""Unreadable process properties remain a blocking process observation."""
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from infra.core import ROOT, read_json


@unittest.skipUnless(os.name == 'nt', 'Windows process inspection')
class ProcessInspectionTests(unittest.TestCase):
    def test_unreadable_start_and_path_are_retained_without_null_exception(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            output = folder / 'inspection.json'
            wrapper = folder / 'probe.ps1'
            # Mock observation only. No real process is started or terminated,
            # and Inspect uses a nonexistent isolated registry fixture.
            wrapper.write_text("""param($Helper,$Output,$Registry)
function Get-Process { [pscustomobject]@{Id=12345;StartTime=$null;Path=$null} }
& $Helper -Action Inspect -LaunchUser ((whoami.exe).Trim()) -FixtureRegistry $Registry -OutputFile $Output
""", encoding='utf-8')
            command = [os.environ.get('VTMB_POWERSHELL', 'pwsh'), '-NoProfile', '-File', str(wrapper),
                       '-Helper', str(ROOT / 'infra/windows.ps1'), '-Output', str(output),
                       '-Registry', 'Software\\VTMBRegressionFixture_' + uuid.uuid4().hex]
            process = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            self.assertEqual(read_json(output)['Processes'],
                             [{'Id': 12345, 'Ticks': None, 'Path': None, 'Inspection': 'UNVERIFIED'}])
