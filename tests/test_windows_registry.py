"""Real registry API regression in a new isolated key, never game settings."""
import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from infra.core import ROOT,read_json


@unittest.skipUnless(os.name=='nt','Windows registry API')
class RegistryTests(unittest.TestCase):
    def test_original_types_absence_and_durable_restore_intents(self):
        import winreg
        base='Software\\VTMBRegressionFixture_'+uuid.uuid4().hex
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            try:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER,base+'\\Settings') as key:
                    for name,value,kind in [('dword',2**32-1,winreg.REG_DWORD),('qword',2**40,winreg.REG_QWORD),('binary',b'\x01\x00\xff',winreg.REG_BINARY),('multi',['a','b'],winreg.REG_MULTI_SZ),('expand','%SystemRoot% literal',winreg.REG_EXPAND_SZ)]:
                        winreg.SetValueEx(key,name,0,kind,value)
                user=subprocess.check_output(['whoami.exe'],text=True).strip()
                def command(action,output,source=None):
                    args=[os.environ.get('VTMB_POWERSHELL','pwsh'),'-NoProfile','-File',str(ROOT/'infra/windows.ps1'),'-Action',action,'-LaunchUser',user,'-FixtureRegistry',base,'-OutputFile',str(output)]
                    if source:args+=['-InputFile',str(source)]
                    p=subprocess.run(args,capture_output=True,text=True,timeout=30)
                    self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                snapshot=folder/'settings.json';command('Inspect',snapshot)
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,base+'\\Settings',0,winreg.KEY_WRITE) as key:
                    winreg.SetValueEx(key,'dword',0,winreg.REG_DWORD,123)
                    winreg.DeleteValue(key,'multi');winreg.SetValueEx(key,'added',0,winreg.REG_SZ,'temporary')
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER,base+'\\ResPatch') as key:winreg.SetValueEx(key,'added',0,winreg.REG_BINARY,b'tmp')
                current=folder/'current.json';command('RestoreSettings',current,snapshot);command('Inspect',current)
                self.assertEqual(read_json(snapshot)['Video'],read_json(current)['Video'])
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,base+'\\Settings') as key:
                    self.assertEqual(winreg.QueryValueEx(key,'expand'),('%SystemRoot% literal',winreg.REG_EXPAND_SZ))
                    self.assertEqual(winreg.QueryValueEx(key,'dword')[0],2**32-1)
                intents=(folder/'settings-intents.jsonl').read_text();self.assertIn('RestoreOriginalValue',intents);self.assertIn('DeleteNewKey',intents)
                # The second recovery is a no-op, including the intent stream.
                command('RestoreSettings',current,snapshot)
                self.assertEqual((folder/'settings-intents.jsonl').read_text(),intents)
            finally:
                for sub in ['Settings','ResPatch']:
                    try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,base+'\\'+sub)
                    except FileNotFoundError:pass
                try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,base)
                except FileNotFoundError:pass
