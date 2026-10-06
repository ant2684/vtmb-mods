"""Synthetic receipts test the audit contract, not native game UI behavior."""
import copy
import ctypes
import ctypes.wintypes
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from infra.core import Blocked,Failure,atomic_json,read_json
from infra.history_observations import (
    EXPECTED_CATEGORIES,PROFILE,PURCHASES,REJECTIONS,derive_pool,
    player_identity,record_action,snapshot_sha,validate_pool,
)


def initial_snapshot():
    groups=[]
    for kind,size in [(0,35),(1,13),(2,11)]:
        groups.append({'type':kind,'values':[0]*size,'costs':{str(i):1 for i in range(1,size)}})
    groups[0]['values'][10]=2
    groups[0]['values'][34]=100
    return {'pid':321,'wall':0.,'players':[{'address':100,'index':1,'serial':2,'groups':groups}]}


def action_receipt(before,after,spec,label,number,native=False):
    category,kind,index,coordinates=spec
    start=number*100+1
    action={'id':'action-'+str(number),'profile':PROFILE,'label':label,'category':category,
            'group':kind,'stat_index':index,'coordinates':list(coordinates),
            'window_rect':[0,0,2560,1440],'owned_process':{'Id':321,'Ticks':456},
            'started_ns':start,'finished_ns':start+50,
            'before_sha256':snapshot_sha(before),'after_sha256':snapshot_sha(after),'inputs':[],
            'native_ui_attempt':None}
    for offset,flags in [(10,2),(20,4)]:
        action['inputs'].append({'kind':0,'flags':flags,'monotonic_ns':start+offset,
            'wall_seconds':before['wall']+offset/100.,'foreground_owned_before':True,
            'foreground_owned_after':True,'cursor':list(coordinates),
            'sendinput_requested':1,'sendinput_returned':1})
    if native:
        # Explicitly synthetic future observer readback. No current collector
        # claims to obtain this event merely from SendInput and native stats.
        action['native_ui_attempt']={'source':'native-ui-command-readback',
            'action_id':action['id'],'pid':321,'player':player_identity(before),
            'event_id':'native-'+str(number),'group':kind,'stat_index':4 if index is None else index,
            'disposition':'creation-category-exhausted','wall_seconds':before['wall']+.3}
    return action


def observations():
    state=initial_snapshot();purchases=[];rejections=[]
    for number,spec in enumerate(PURCHASES):
        before=copy.deepcopy(state);before['wall']=number*2.
        after=copy.deepcopy(before);after['wall']+=1
        after['players'][0]['groups'][spec[1]]['values'][spec[2]]+=1
        after['players'][0]['groups'][0]['values'][34]-=1
        purchases.append({'before':before,'after':after,
            'action':action_receipt(before,after,spec,'fresh_pool_'+str(number),number)})
        state=after
    for index,spec in enumerate(REJECTIONS):
        number=len(PURCHASES)+index
        before=copy.deepcopy(state);before['wall']=number*2.
        after=copy.deepcopy(before);after['wall']+=1
        rejections.append({'before':before,'after':after,
            'action':action_receipt(before,after,spec,'exhausted_'+str(index),number,True)})
        state=after
    return purchases,rejections


class HistoryPoolTests(unittest.TestCase):
    def test_complete_independent_category_proof(self):
        purchases,rejections=observations()
        proof=derive_pool(purchases,rejections)
        self.assertEqual(proof['new_purchases'],[3,6,1])
        self.assertEqual(proof['category_purchases'],EXPECTED_CATEGORIES)
        self.assertEqual(set(proof['rejected_categories']),set(EXPECTED_CATEGORIES))
        self.assertEqual(proof['rejected_exhausted_categories'],7)
        self.assertEqual(validate_pool(proof),proof)

    def test_duplicate_rejection_cannot_count_as_seven_categories(self):
        purchases,rejections=observations()
        with self.assertRaises(Failure):derive_pool(purchases,[rejections[0]]*7)

    def test_duplicate_action_identity_rejected(self):
        purchases,rejections=observations()
        rejections[1]['action']['id']=rejections[0]['action']['id']
        with self.assertRaisesRegex(Failure,'action identity'):derive_pool(purchases,rejections)

    def test_duplicate_native_event_rejected(self):
        purchases,rejections=observations()
        rejections[1]['action']['native_ui_attempt']['event_id']=rejections[0]['action']['native_ui_attempt']['event_id']
        with self.assertRaisesRegex(Failure,'native UI event'):derive_pool(purchases,rejections)

    def test_wrong_attempted_category_rejected(self):
        purchases,rejections=observations()
        rejections[0]['action']['category']='social'
        with self.assertRaisesRegex(Failure,'attempted category'):derive_pool(purchases,rejections)

    def test_wrong_native_category_rejected(self):
        purchases,rejections=observations()
        rejections[0]['action']['native_ui_attempt']['stat_index']=4
        with self.assertRaisesRegex(Failure,'different category'):derive_pool(purchases,rejections)

    def test_group_totals_do_not_hide_wrong_real_purchase_distribution(self):
        purchases,rejections=observations()
        # Keep the native group total three, but move the Mental purchase to
        # Social in all subsequent snapshots and rebind their snapshot hashes.
        for row in purchases[2:]+rejections:
            for part in ['before','after']:
                values=row[part]['players'][0]['groups'][0]['values']
                if values[7]:values[4]+=values[7];values[7]=0
                row['action'][part+'_sha256']=snapshot_sha(row[part])
        with self.assertRaisesRegex(Failure,'Actual purchased stat'):derive_pool(purchases,rejections)

    def test_absent_action_is_blocked(self):
        purchases,rejections=observations();rejections[0].pop('action')
        with self.assertRaisesRegex(Blocked,'Action receipt absent'):derive_pool(purchases,rejections)

    def test_os_delivery_and_unchanged_stats_do_not_prove_rejection(self):
        purchases,rejections=observations()
        rejections[0]['action']['native_ui_attempt']=None
        with self.assertRaisesRegex(Blocked,'not actual category-exhausted rejection'):derive_pool(purchases,rejections)

    def test_failed_os_delivery_rejected(self):
        purchases,rejections=observations()
        purchases[0]['action']['inputs'][0]['sendinput_returned']=0
        with self.assertRaisesRegex(Failure,'SendInput'):derive_pool(purchases,rejections)

    def test_lost_owned_foreground_rejected(self):
        purchases,rejections=observations()
        rejections[0]['action']['inputs'][0]['foreground_owned_before']=False
        with self.assertRaisesRegex(Failure,'foreground'):derive_pool(purchases,rejections)

    def test_actual_cursor_must_match_recorded_target(self):
        purchases,rejections=observations()
        purchases[0]['action']['inputs'][0]['cursor']=[1,2]
        with self.assertRaisesRegex(Failure,'Actual cursor'):derive_pool(purchases,rejections)

    def test_snapshots_are_bound_to_actual_receipt(self):
        purchases,rejections=observations()
        purchases[0]['after']['players'][0]['groups'][0]['values'][11]=1
        with self.assertRaisesRegex(Failure,'different native snapshots'):derive_pool(purchases,rejections)

    def test_pool_cannot_splice_other_owned_process(self):
        purchases,rejections=observations()
        purchases[1]['action']['owned_process']['Ticks']+=1
        with self.assertRaisesRegex(Failure,'different native process/player'):derive_pool(purchases,rejections)

    def test_reordered_actions_rejected(self):
        purchases,rejections=observations()
        purchases[1]['action']['started_ns']=0
        with self.assertRaisesRegex(Failure,'timing overlaps'):derive_pool(purchases,rejections)

    def test_summary_must_match_independently_derived_categories(self):
        purchases,rejections=observations();proof=derive_pool(purchases,rejections)
        proof['category_purchases']['physical']=3
        with self.assertRaisesRegex(Failure,'category summary'):validate_pool(proof)


class HistoryActionCaptureTests(unittest.TestCase):
    """Fake OS APIs verify receipt plumbing without starting any process."""
    def capture(self,root,failed=False,preservation_failed=False):
        spec=PURCHASES[0];label='fresh_pool_0';calls=[]
        def rectangle(hwnd,pointer):
            rect=pointer._obj;rect.left=rect.top=0;rect.right=2560;rect.bottom=1440
            return 1
        def cursor(pointer):
            pointer._obj.x,pointer._obj.y=spec[3]
            return 1
        api=SimpleNamespace(GetWindowRect=rectangle,GetCursorPos=cursor,GetForegroundWindow=lambda:7)
        atomic_json(root/'process.json',{'Id':321,'Ticks':456})
        def original(event,check=True):
            calls.append(event.value.mi.flags)
            if failed:raise OSError('first SendInput failure')
        driver=SimpleNamespace(session=root,p=SimpleNamespace(pid=321),hwnd=7,send=original)
        def operation():
            before=initial_snapshot();before['wall']=time.time()
            atomic_json(root/(label+'_before.json'),before)
            driver.send(SimpleNamespace(kind=0,value=SimpleNamespace(mi=SimpleNamespace(flags=2))))
            driver.send(SimpleNamespace(kind=0,value=SimpleNamespace(mi=SimpleNamespace(flags=4))),False)
            after=copy.deepcopy(before);after['wall']=time.time()
            atomic_json(root/(label+'_after.json'),after)
            return 'operation-result'
        fake_drive=SimpleNamespace(C=ctypes,W=ctypes.wintypes,u=api)
        with patch.dict('sys.modules',{'drive':fake_drive}):
            if preservation_failed:
                with patch('infra.history_observations.atomic_json',side_effect=OSError('receipt storage failure')):
                    with self.assertRaisesRegex(OSError,'first SendInput failure') as captured:
                        record_action(driver,spec,label,operation)
                self.assertIn('receipt storage failure',captured.exception.__notes__[0])
            elif failed:
                with self.assertRaisesRegex(OSError,'first SendInput failure'):
                    record_action(driver,spec,label,operation)
            else:self.assertEqual(record_action(driver,spec,label,operation),'operation-result')
        self.assertIs(driver.send,original)
        return calls

    def test_capture_records_os_delivery_without_inventing_native_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.assertEqual(self.capture(root),[2,4])
            action=read_json(root/'fresh_pool_0_action.json')
            self.assertEqual([event['sendinput_returned'] for event in action['inputs']],[1,1])
            self.assertEqual(action['inputs'][0]['cursor'],[506,309])
            self.assertTrue(action['inputs'][0]['foreground_owned_before'])
            self.assertEqual(action['before_sha256'],snapshot_sha(read_json(root/'fresh_pool_0_before.json')))
            self.assertEqual(action['after_sha256'],snapshot_sha(read_json(root/'fresh_pool_0_after.json')))
            self.assertIsNone(action['native_ui_attempt'])

    def test_capture_retains_failed_delivery_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.capture(root,failed=True)
            action=read_json(root/'fresh_pool_0_action.json')
            self.assertEqual(action['inputs'][0]['sendinput_returned'],0)
            self.assertNotIn('after_sha256',action)

    def test_receipt_storage_failure_does_not_hide_first_sendinput_failure(self):
        with tempfile.TemporaryDirectory() as td:
            self.capture(Path(td),failed=True,preservation_failed=True)


if __name__=='__main__':unittest.main()
