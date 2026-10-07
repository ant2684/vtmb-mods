"""Frozen release tests must come from its pinned matching source capsule."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from infra.core import Failure, digest, sha
from infra.native import CONSOLE_FROZEN_TEST_FILES, frozen_console_tests


class FrozenConsoleSourceTests(unittest.TestCase):
    def test_repository_layout_selected_and_mixed_layout_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);archive=root/'source.zip';archive.write_bytes(b'pinned archive')
            files={'mods/console/'+n:('release '+n).encode() for n in CONSOLE_FROZEN_TEST_FILES}
            files['infra/common/clean_pe.py']=b'shared clean checker'
            files['infra/common/load_clean.c']=b'shared native loader'
            pins={'mods':{'console':{'capsule':'source.zip'}},'archives':{'source.zip':{'sha256':digest(archive),'members':{n:sha(v) for n,v in files.items()}}}}
            with patch('infra.native.catalog',return_value=pins),patch('infra.native.members',return_value=files):
                code=frozen_console_tests({'releases':td},root/'work')
                expected={n:files['mods/console/'+n] for n in CONSOLE_FROZEN_TEST_FILES}
                self.assertEqual({p.relative_to(code).as_posix():p.read_bytes() for p in code.rglob('*') if p.is_file()},expected)
                for key in ('infra/common/clean_pe.py','infra/common/load_clean.c'):
                    self.assertEqual((root/'work/frozen-console'/key).read_bytes(),files[key])
                files['infra/common/clean_pe.py']=b'changed helper'
                with self.assertRaises(Failure):frozen_console_tests({'releases':td},root/'bad-helper')
                files['infra/common/clean_pe.py']=b'shared clean checker'
                files['plugin/console_pause.c']=b'ambiguous'
                with self.assertRaises(Failure):frozen_console_tests({'releases':td},root/'other')

    def test_pinned_sources_selected_without_current_candidate_tests(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);archive=root/'source.zip';archive.write_bytes(b'pinned archive')
            files={n:('frozen '+n).encode() for n in CONSOLE_FROZEN_TEST_FILES}
            pins={'mods':{'console':{'capsule':'source.zip'}},'archives':{'source.zip':{'sha256':digest(archive),'members':{n:sha(v) for n,v in files.items()}}}}
            with patch('infra.native.catalog',return_value=pins),patch('infra.native.members',return_value=files):
                code=frozen_console_tests({'releases':td},root/'work')
                self.assertEqual({p.relative_to(code).as_posix():p.read_bytes() for p in code.rglob('*') if p.is_file()},files)
                archive.write_bytes(b'changed archive')
                with self.assertRaises(Failure):frozen_console_tests({'releases':td},root/'other')

    def test_changed_or_missing_harness_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);archive=root/'source.zip';archive.write_bytes(b'pinned archive')
            files={n:b'frozen' for n in CONSOLE_FROZEN_TEST_FILES}
            pins={'mods':{'console':{'capsule':'source.zip'}},'archives':{'source.zip':{'sha256':digest(archive),'members':{n:sha(v) for n,v in files.items()}}}}
            for changed in [b'changed',None]:
                bad=dict(files)
                if changed is None:bad.pop('tests/exact_harness.c')
                else:bad['tests/exact_harness.c']=changed
                with patch('infra.native.catalog',return_value=pins),patch('infra.native.members',return_value=bad):
                    with self.assertRaises(Failure):frozen_console_tests({'releases':td},root/'work')
