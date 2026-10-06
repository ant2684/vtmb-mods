import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from infra.core import ROOT, Blocked, Failure, atomic_json, require
from infra.release import members
from infra.session import Transaction
from infra.gameplay import SCENARIOS, audit


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.game=self.base/'game';self.game.mkdir();self.state=self.base/'state'
        (self.game/'config.cfg').write_bytes(b'personal original')
        os.utime(self.game/'config.cfg',ns=(1234567890000000000,1234567890000000000))
        self.tx=Transaction(self.game,self.state);self.tx.start()
    def tearDown(self):self.tmp.cleanup()
    def test_replacement_and_new_file_restored_and_archived(self):
        self.tx.write('config.cfg',b'temporary');self.tx.write('probe.py',b'task')
        self.tx.restore()
        self.assertEqual((self.game/'config.cfg').read_bytes(),b'personal original')
        self.assertEqual((self.game/'config.cfg').stat().st_mtime_ns,1234567890000000000)
        self.assertFalse((self.game/'probe.py').exists())
        self.assertEqual((self.state/self.tx.data['id']/'after-tests/config.cfg').read_bytes(),b'temporary')
        self.assertTrue(self.tx.restore()['idempotent'])
    def test_crash_at_each_write_checkpoint(self):
        for checkpoint in ['intent','write']:
            with self.subTest(checkpoint=checkpoint):
                if self.tx.data['state']=='RESTORED':self.tx.start()
                def crash(stage):
                    if stage==checkpoint:raise RuntimeError('simulated interruption')
                with self.assertRaises(RuntimeError):self.tx.write('config.cfg',b'changed',crash)
                Transaction(self.game,self.state).restore()
                self.tx=Transaction(self.game,self.state)
                self.assertEqual((self.game/'config.cfg').read_bytes(),b'personal original')
    def test_live_lock_blocks_new_run(self):
        with self.assertRaises(Blocked):Transaction(self.game,self.state).start()
    def test_unknown_change_kept(self):
        self.tx.write('config.cfg',b'temporary');(self.game/'config.cfg').write_bytes(b'user newer')
        with self.assertRaises(Blocked):self.tx.restore()
        self.assertEqual((self.game/'config.cfg').read_bytes(),b'user newer')
    def test_corrupt_backup_keeps_candidate(self):
        self.tx.write('config.cfg',b'temporary');(self.state/self.tx.data['id']/'originals/config.cfg').write_bytes(b'corrupt')
        with self.assertRaises(Failure):self.tx.restore()
        self.assertEqual((self.game/'config.cfg').read_bytes(),b'temporary')
    def test_same_bytes_still_restore_timestamp(self):
        self.tx.preserve('config.cfg');os.utime(self.game/'config.cfg',None);self.tx.restore()
        self.assertEqual((self.game/'config.cfg').stat().st_mtime_ns,1234567890000000000)
    def test_uncertain_launch_blocks_restore(self):
        self.tx.write('config.cfg',b'temporary');self.tx.launch_intent(self.game/'Vampire.exe',[])
        with self.assertRaises(Blocked):self.tx.restore()
    def test_recorded_process_requires_stop(self):
        self.tx.launch_intent(self.game/'Vampire.exe',[]);self.tx.owned_process(123,999)
        with self.assertRaises(Blocked):self.tx.restore()
        self.tx.restore(process_stopped=True)
    def test_unknown_extra_file_not_deleted(self):
        (self.game/'user_new.sav').write_bytes(b'user')
        self.tx.restore();self.assertEqual((self.game/'user_new.sav').read_bytes(),b'user')
    def test_escape_and_state_overlap_rejected(self):
        for path in ['../outside','/absolute','C:/outside']:
            with self.assertRaises(Failure):self.tx.path(path)
        with self.assertRaises(Failure):Transaction(self.game,self.game/'state')

    def test_process_death_at_write_checkpoints(self):
        for checkpoint in ['intent','write']:
            with self.subTest(checkpoint=checkpoint):
                if self.tx.data['state']=='RESTORED':self.tx.start()
                script='from infra.session import Transaction; import os,sys; t=Transaction(sys.argv[1],sys.argv[2]); t.write("config.cfg",b"changed",lambda stage: os._exit(73) if stage==sys.argv[3] else None)'
                p=subprocess.run([sys.executable,'-B','-c',script,str(self.game),str(self.state),checkpoint],cwd=ROOT)
                self.assertEqual(p.returncode,73)
                Transaction(self.game,self.state).restore()
                self.tx=Transaction(self.game,self.state)
                self.assertEqual((self.game/'config.cfg').read_bytes(),b'personal original')

    def test_inventory_blocks_unregistered_file(self):
        self.tx.watch_inventory();(self.game/'user_new.sav').write_bytes(b'user')
        with self.assertRaises(Blocked):self.tx.restore()
        self.assertTrue(self.tx.lock.exists())
        self.assertEqual((self.game/'user_new.sav').read_bytes(),b'user')

    def test_file_restore_does_not_unlock_before_settings(self):
        self.tx.write('config.cfg',b'temporary');self.tx.restore(finalize=False)
        self.assertTrue(self.tx.lock.exists())
        with self.assertRaises(Blocked):Transaction(self.game,self.state).start()
        self.tx.finish();self.assertFalse(self.tx.lock.exists())

    def test_recovery_after_final_state_before_lock_removal(self):
        self.tx.restore(finalize=False);self.tx.data['state']='RESTORED';self.tx.save()
        self.assertTrue(self.tx.installation_file.exists())
        self.assertTrue(Transaction(self.game,self.state).restore()['idempotent'])
        self.assertFalse(self.tx.installation_file.exists())

    def test_persistent_installation_lock_survives_controller_death(self):
        self.tx.release_installation()
        with self.assertRaises(Blocked):Transaction(self.game,self.base/'other-state').start()

    @unittest.skipUnless(os.name=='nt','Windows installation-wide mutex')
    def test_different_state_root_cannot_bypass_installation_lock(self):
        script='from infra.session import Transaction; import sys; Transaction(sys.argv[1],sys.argv[2]).start()'
        p=subprocess.run([sys.executable,'-B','-c',script,str(self.game),str(self.base/'other-state')],cwd=ROOT,capture_output=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn(b'owned by another test controller',p.stderr)


class GateTests(unittest.TestCase):
    def test_explicit_gate_survives_python_optimization(self):
        p=subprocess.run([sys.executable,'-O','-c','from infra.core import require; require(False,"reject")'],cwd=ROOT,capture_output=True)
        self.assertNotEqual(p.returncode,0)
    def test_archive_path_duplicates_and_traversal(self):
        for names in [['README.txt','readme.txt'],['../escape'],['C:/escape'],['folder\\escape']]:
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)/'bad.zip'
                with zipfile.ZipFile(path,'w') as z:
                    for n in names:z.writestr(n,b'wrong')
                if names==['folder\\escape']:
                    path.write_bytes(path.read_bytes().replace(b'folder/escape',b'folder\\escape'))
                with self.assertRaises(Failure):members(path)
    def test_atomic_report_preserves_unicode(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'report.json';atomic_json(p,{'result':'BLOCKED','reason':'Нет сохранения'})
            self.assertEqual(json.loads(p.read_text(encoding='utf-8'))['reason'],'Нет сохранения')
    def test_public_tree_and_python_sources(self):
        from infra.public_tree import inspect
        inspect()
        for path in ROOT.rglob('*.py'):
            if not any(x in {'.git','.local','__pycache__'} for x in path.relative_to(ROOT).parts):compile(path.read_bytes(),str(path),'exec')

    def test_public_scan_uses_staged_blob_and_casefold(self):
        from infra.public_tree import inspect
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            subprocess.run(['git','init','-q',str(root)],check=True,capture_output=True)
            source=root/'note.txt';source.write_text('ghp_'+'x'*35,encoding='utf-8')
            subprocess.run(['git','add','note.txt'],cwd=root,check=True,capture_output=True)
            source.write_text('sanitized worktree',encoding='utf-8')
            with self.assertRaises(Failure):inspect(root,tracked=True)
            subprocess.run(['git','add','note.txt'],cwd=root,check=True,capture_output=True)
            self.assertEqual(inspect(root,tracked=True)['result'],'PASS')
            (root/'PRIVATE.DLL').write_bytes(b'not a PE')
            with self.assertRaises(Failure):inspect(root)
    def test_imported_provenance_maps_all_native_sources(self):
        from infra.core import read_json, digest
        if (ROOT/'docs/provenance.json').exists():records=read_json(ROOT/'docs/provenance.json')['files']
        else:
            from infra.provenance_data import DATA
            records=DATA['files']
        published={r['file'] for r in records if r['published']}
        for source in (ROOT/'mods').glob('*/plugin/*'):
            self.assertIn(source.relative_to(ROOT).as_posix(),published)
        self.assertTrue(all(r.get('original_sha256') for r in records))
        for r in records:
            if r['published']:self.assertEqual(digest(ROOT/r['file']),r['public_sha256'],r['file'])


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.scenario=next(s for s in SCENARIOS if s['id']=='console.immediate')
        self.identity={'session':'fresh','artifacts':{'plugin':'HASH'},'modules':{'engine':'PIN'},'save_sha256':'SAVE','resources':{}}
        self.evidence={'session':'fresh','scenario':'console.immediate','scenario_version':1,'artifacts':{'plugin':'HASH'},'modules':{'engine':'PIN'},'save_sha256':'SAVE','resolved_resources':{},'first_result_preserved':True,'observations':[{'check':n,'expected':True,'observed':True,'before':{'console':{'visible':1}},'after':{'console':{'visible':0},'mouse_active':1,'paused':0,'server_paused':0,'menu_pause_depth':0},'elapsed_seconds':.1,'source':'native-process-read'} for n in self.scenario['checks']], 'metrics':{'native_back_held':True,'native_forward_held':True,'signed_back':-3,'signed_forward':3,'camera_left':-2,'camera_right':2,'world_time_delta':1,'first_input_after_close_seconds':.1}}
    def test_bound_fresh_synthetic_evidence(self):self.assertEqual(audit(self.scenario,self.evidence,self.identity)['result'],'PASS')
    def test_stale_session_and_artifacts_rejected(self):
        for key in ['session','artifacts','modules','save_sha256','scenario_version','resolved_resources']:
            e=copy.deepcopy(self.evidence);e[key]='stale'
            with self.assertRaises(Failure):audit(self.scenario,e,self.identity)
    def test_missing_and_duplicate_observations(self):
        for observations in [[],self.evidence['observations']*2]:
            e=copy.deepcopy(self.evidence);e['observations']=observations
            with self.assertRaises(Failure):audit(self.scenario,e,self.identity)
    def test_first_failed_input_cannot_be_replaced_by_later_success(self):
        e=copy.deepcopy(self.evidence);e['metrics']['native_back_held']=False
        with self.assertRaises(Failure):audit(self.scenario,e,self.identity)
        e=copy.deepcopy(self.evidence);e['first_result_preserved']=False
        with self.assertRaises(Failure):audit(self.scenario,e,self.identity)
    def test_delayed_input_not_immediate_certificate(self):
        e=copy.deepcopy(self.evidence);e['metrics']['first_input_after_close_seconds']=5
        with self.assertRaises(Failure):audit(self.scenario,e,self.identity)
    def test_os_key_state_not_native_receipt(self):
        e=copy.deepcopy(self.evidence);e['metrics'].pop('native_forward_held')
        with self.assertRaises(Failure):audit(self.scenario,e,self.identity)
    def test_wrong_expectation_and_unproven_source_rejected(self):
        e=copy.deepcopy(self.evidence);e['observations'][0]['observed']=False
        with self.assertRaises(Failure):audit(self.scenario,e,self.identity)
        e=copy.deepcopy(self.evidence);e['observations'][0].update(expected=False,observed=False)
        with self.assertRaises(Failure):audit(self.scenario,e,self.identity)
        e=copy.deepcopy(self.evidence);e['observations'][0]['source']='SendInput returned success'
        with self.assertRaises(Failure):audit(self.scenario,e,self.identity)
