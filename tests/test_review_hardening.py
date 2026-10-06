import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from infra.core import Blocked,Failure,atomic_json,read_json
from infra.gameplay import SCENARIOS,audit
from infra.recover import settings_restore_allowed
from infra.session import Transaction


class LateRecoveryTests(unittest.TestCase):
    def test_historical_pid_does_not_own_newer_config(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);game=root/'game';game.mkdir();file=game/'config.cfg';file.write_bytes(b'original')
            tx=Transaction(game,root/'state');tx.start();tx.allow_runtime('config.cfg')
            tx.launch_intent(game/'Vampire.exe',[]);tx.owned_process(123,456)
            file.write_bytes(b'newer personal configuration')
            with self.assertRaises(Blocked):tx.restore(process_stopped=True,runtime_safe=True)
            self.assertEqual(file.read_bytes(),b'newer personal configuration')
            tx.release_installation()

    def test_frozen_runtime_cannot_authorize_later_change(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);game=root/'game';game.mkdir();file=game/'config.cfg';file.write_bytes(b'original')
            tx=Transaction(game,root/'state');tx.start();tx.allow_runtime('config.cfg')
            file.write_bytes(b'owned runtime');tx.seal_runtime()
            file.write_bytes(b'newer personal configuration')
            with self.assertRaises(Blocked):tx.restore(process_stopped=True)
            self.assertEqual(file.read_bytes(),b'newer personal configuration')
            tx.release_installation()

    def test_sealed_runtime_restores_exact_original(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);game=root/'game';game.mkdir();file=game/'config.cfg';file.write_bytes(b'original')
            tx=Transaction(game,root/'state');tx.start();tx.allow_runtime('config.cfg')
            file.write_bytes(b'owned runtime');tx.seal_runtime();tx.restore()
            self.assertEqual(file.read_bytes(),b'original')

    def test_later_user_video_values_remain_unowned(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);original={'Video':{'width':2560},'Shortcuts':[]}
            atomic_json(folder/'settings.json',original)
            settings_restore_allowed(folder,original)
            newer={'Video':{'width':1920},'Shortcuts':[]}
            with self.assertRaises(Blocked):settings_restore_allowed(folder,newer)
            atomic_json(folder/'settings-after-stop.json',newer)
            settings_restore_allowed(folder,newer)
            with self.assertRaises(Blocked):settings_restore_allowed(folder,{'Video':{'width':1280},'Shortcuts':[]})


class AuditHardeningTests(unittest.TestCase):
    def test_generic_griffith_labels_cannot_prove_transitions(self):
        scenario=next(s for s in SCENARIOS if s['id']=='frenzy.griffith')
        identity={'session':'fixture','artifacts':{},'modules':{},'save_sha256':None,'resources':{}}
        evidence={**identity,'scenario':scenario['id'],'scenario_version':1,'resolved_resources':{},'first_result_preserved':True,
            'observations':[{'check':name,'expected':True,'observed':True,'before':{'placeholder':1},'after':{'placeholder':1},'elapsed_seconds':1,'source':'native-process-read'} for name in scenario['checks']],
            'metrics':{'closest_active_xy':100,'native_damage':5,'original_player_handle':123}}
        with self.assertRaises(Failure):audit(scenario,evidence,identity)
        evidence['metrics']['ground_handle']=0
        with self.assertRaises(Failure):audit(scenario,evidence,identity)

    def test_collector_summary_cannot_prove_history_pool(self):
        from infra.history_observations import validate_pool
        with self.assertRaises(Failure):validate_pool({'new_purchases':[3,6,1],'rejected_exhausted_categories':7})

    def test_scenario_failure_survives_blocked_preservation(self):
        from infra.runner import main
        error=Failure('native first event failed')
        error.scenario_result={'status':'FAIL','reason':'native first event failed'}
        error.preservation_result={'status':'BLOCKED','reason':'user game started'}
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);output=folder/'report.json'
            from infra.core import catalog
            scenario=next(s['id'] for s in SCENARIOS if s['mod'] in catalog()['mods'])
            with patch('infra.gameplay.execute',side_effect=error):
                code=main(['--suite','gameplay','--scenario',scenario,'--output',str(output)])
            report=read_json(output)
            self.assertEqual(code,1);self.assertEqual(report['status'],'FAIL')
            self.assertEqual(report['results'][0]['preservation_result']['status'],'BLOCKED')
            self.assertEqual(report['results'][0]['scenario_result']['reason'],'native first event failed')
