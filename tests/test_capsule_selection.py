"""Single-mod exports retain shared tests without unrelated source imports."""
import copy
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from infra import export_capsule

class CapsuleSelectionTests(unittest.TestCase):
    def test_mod_owned_tests_follow_their_sources(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'repo';root.mkdir()
            files=['RunTests.ps1','Setup.ps1','requirements.txt','local.example.json','LICENSE','NOTICE','docs/gameplay.md','docs/lessons.md','infra/common/helper.py','tests/test_shared.py','tests/test_container_audit.py','tests/test_container_receiver.py','mods/subtitle/plugin/fix.c','mods/container/plugin/fix.c']
            for name in files:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture\n')
            (root/'docs/provenance.json').write_text('{"files":[]}')
            info={m:{'title':m,'version':'1.0.0','capsule':m+'.zip','filename':'fix.vtm','exports':[]} for m in ['subtitle','container']}
            for mod in info:
                archive=Path(td)/(mod+'.zip')
                with patch.object(export_capsule,'ROOT',root),patch.object(export_capsule,'families',return_value=info),patch.object(export_capsule,'mod_info',side_effect=lambda name:copy.deepcopy(info[name])),patch.object(export_capsule,'catalog',return_value={'mods':copy.deepcopy(info),'archives':{}}):
                    export_capsule.export(mod,archive)
                with zipfile.ZipFile(archive) as z:names=set(z.namelist())
                self.assertIn('tests/test_shared.py',names)
                self.assertEqual('tests/test_container_audit.py' in names,mod=='container')
                self.assertEqual('tests/test_container_receiver.py' in names,mod=='container')
                self.assertIn('mods/'+mod+'/plugin/fix.c',names)
                self.assertEqual(sum(Path(n).name.lower() in ['readme.md','readme.txt'] for n in names),1)

if __name__=='__main__':unittest.main()
