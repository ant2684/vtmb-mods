"""Manual decisions are exact, archived and cannot silently own later writes."""
import tempfile
import unittest
from pathlib import Path
from infra.core import Failure, digest
from infra.session import Transaction


class ReconciliationTests(unittest.TestCase):
    def fixture(self, folder):
        game=folder/'game';game.mkdir();file=game/'config.cfg';file.write_bytes(b'original')
        tx=Transaction(game,folder/'state');tx.start();tx.allow_runtime('config.cfg')
        file.write_bytes(b'later user bytes')
        return tx,file

    def test_retains_approved_newer_file_and_both_versions(self):
        with tempfile.TemporaryDirectory() as td:
            tx,file=self.fixture(Path(td));identity=digest(file)
            tx.reconcile_file('config.cfg',identity,'keep-current','Operator retains inspected later settings')
            result=tx.restore()
            self.assertEqual(file.read_bytes(),b'later user bytes');self.assertEqual(result['kept_current'],['config.cfg'])
            archive=tx.state/tx.data['id']/'reconciled'/identity/'config.cfg'
            self.assertEqual(archive.read_bytes(),b'later user bytes')
            self.assertEqual((tx.state/tx.data['id']/'originals/config.cfg').read_bytes(),b'original')

    def test_later_write_and_wrong_hash_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            tx,file=self.fixture(Path(td))
            with self.assertRaises(Failure):tx.reconcile_file('config.cfg','WRONG','keep-current','Reviewed')
            tx.reconcile_file('config.cfg',digest(file),'keep-current','Reviewed')
            file.write_bytes(b'newer again')
            with self.assertRaises(Failure):tx.restore()
            self.assertEqual(file.read_bytes(),b'newer again')

    def test_only_registered_mutable_paths_can_be_approved_for_restore(self):
        with tempfile.TemporaryDirectory() as td:
            tx,file=self.fixture(Path(td));identity=digest(file)
            with self.assertRaises(Failure):tx.reconcile_file('../outside',identity,'restore-recorded','Reviewed')
            tx.reconcile_file('config.cfg',identity,'restore-recorded','Explicitly authorize archived runtime output')
            tx.restore();self.assertEqual(file.read_bytes(),b'original')

    def test_partial_restore_keeps_unknown_file_and_lock(self):
        with tempfile.TemporaryDirectory() as td:
            tx,file=self.fixture(Path(td));tx.write('owned.tmp',b'temporary')
            with self.assertRaises(Failure):tx.restore(paths=['owned.tmp'])
            result=tx.restore(paths=['owned.tmp'],finalize=False)
            self.assertEqual(result['state'],'PARTIALLY_RESTORED')
            self.assertEqual(file.read_bytes(),b'later user bytes')
            self.assertTrue(tx.installation_file.exists());self.assertFalse((tx.game/'owned.tmp').exists())
            self.assertTrue(next(r for r in tx.data['operations'] if r['path']=='owned.tmp')['restore_intent'])
