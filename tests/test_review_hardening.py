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
    def test_each_session_retains_its_final_journal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);game=root/'game';game.mkdir()
            tx=Transaction(game,root/'state');first=tx.start();tx.write('probe',b'owned');tx.restore()
            original=(first/'journal.json').read_bytes();second=tx.start()
            self.assertNotEqual(first,second);self.assertEqual((first/'journal.json').read_bytes(),original)
            self.assertEqual(read_json(first/'journal.json')['state'],'RESTORED');tx.restore()

    def test_changed_process_record_cannot_control_other_pid(self):
        from infra.gameplay import verify_process_record
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);game=root/'game';game.mkdir();tx=Transaction(game,root/'state');folder=tx.start()
            tx.launch_intent(game/'Vampire.exe',[]);tx.owned_process(123,456)
            atomic_json(folder/'process.json',{'Id':456,'Ticks':789})
            with self.assertRaises(Failure):verify_process_record(tx,folder)
            atomic_json(folder/'process.json',{'Id':123,'Ticks':456});verify_process_record(tx,folder)
            tx.restore(process_stopped=True)

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
    def test_actual_griffith_and_library_paths_can_pass(self):
        from infra.core import catalog
        for name in ['frenzy.library','frenzy.griffith']:
            scenario=next(s for s in SCENARIOS if s['id']==name)
            resource=catalog()['scenario_resources'][name]
            identity={'session':'fixture','artifacts':{},'modules':{},'save_sha256':None,'resources':{resource:'HASH'}}
            observations=[{'check':key,'expected':True,'observed':True,'before':{'frenzy_active':True,'owned_shadow_count':1},'after':{'frenzy_active':False,'owned_shadow_count':0},'elapsed_seconds':1,'source':'native-process-read'} for key in scenario['checks']]
            by={r['check']:r for r in observations}
            by['resolved_resource']['after']={'resources':identity['resources']}
            metrics={}
            if name=='frenzy.library':
                by['permission']['after']={'nofrenzyarea':0}
                by['native_frenzy']['after']={'command':'frenzyplayer','owned_shadow_count':1,'shadow_handle':2,'player_handle':1}
            else:
                metrics={'closest_active_xy':100,'native_damage':5,'ground_handle':0,'original_player_handle':1}
                for key,protean in [('normal_contact',False),('warform_contact',True)]:by[key]['after']={'protean_active':protean,'closest_active_xy':100,'native_damage':5}
                by['scope_forwarding']['after']={'unrelated_calls_forwarded':True}
            evidence={**identity,'scenario':name,'scenario_version':1,'resolved_resources':identity['resources'],'first_result_preserved':True,'observations':observations,'metrics':metrics}
            self.assertEqual(audit(scenario,evidence,identity)['result'],'PASS')

    def test_historical_identity_cannot_be_assigned_to_other_bytes(self):
        from infra.historical import require_historical_identity
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            with self.assertRaises(Failure):require_historical_identity('background',folder,{'plugin_sha256':'OTHER'},'EXPECTED')
            with self.assertRaises(Blocked):require_historical_identity('subtitle',folder,{'binary_sha256':'EXPECTED'},'EXPECTED')
            atomic_json(folder/'launch.json',{'PluginHash':'OTHER'})
            with self.assertRaises(Failure):require_historical_identity('subtitle',folder,{'binary_sha256':'EXPECTED'},'EXPECTED')
            atomic_json(folder/'launch.json',{'PluginHash':'EXPECTED'})
            require_historical_identity('subtitle',folder,{'binary_sha256':'EXPECTED'},'EXPECTED')

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
