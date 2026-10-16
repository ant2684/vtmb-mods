import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from infra.core import digest, sha, source_digest_lf
from tests import test_regressions as gates


class SourceHashTests(unittest.TestCase):
    def test_only_crlf_is_normalized(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.c';lf=b'int x = 1;\nreturn x;\n'
            p.write_bytes(lf);expected=source_digest_lf(p);raw=digest(p)
            p.write_bytes(lf.replace(b'\n',b'\r\n'))
            self.assertEqual(source_digest_lf(p),expected)
            self.assertNotEqual(digest(p),raw)
            for changed in [lf.replace(b'1',b'2'),lf.replace(b' ',b'  '),lf.replace(b'\n',b'\r')]:
                p.write_bytes(changed);self.assertNotEqual(source_digest_lf(p),expected)

    def check_fixture(self,styles,published=False,changed=False):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'mods/example/plugin/source.c';p.parent.mkdir(parents=True)
            lf=b'int value = 1;\n';crlf=lf.replace(b'\n',b'\r\n')
            record={'file':p.relative_to(root).as_posix(),'published':published,
                    'classification':'Original source','license':'MIT',
                    'original_sha256':sha(crlf),'source_sha256_lf':sha(lf)}
            if published:record['public_sha256']=sha(lf)
            (root/'docs').mkdir();(root/'docs/provenance.json').write_text(json.dumps({'files':[record]}))
            with patch.object(gates,'ROOT',root):
                for data in styles:
                    p.write_bytes(data.replace(b'1',b'2') if changed else data)
                    test=gates.GateTests('test_imported_provenance_maps_all_native_sources')
                    if changed or published and data!=lf:
                        with self.assertRaises(AssertionError):test.test_imported_provenance_maps_all_native_sources()
                    else:test.test_imported_provenance_maps_all_native_sources()

    def test_candidate_gate_accepts_lf_and_crlf(self):
        self.check_fixture([b'int value = 1;\n',b'int value = 1;\r\n'])

    def test_candidate_gate_rejects_changed_code(self):
        self.check_fixture([b'int value = 1;\n',b'int value = 1;\r\n'],changed=True)

    def test_published_gate_keeps_exact_bytes(self):
        self.check_fixture([b'int value = 1;\n',b'int value = 1;\r\n'],published=True)
