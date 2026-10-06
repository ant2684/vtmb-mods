"""Reject plausible native observations that do not satisfy console controls."""
import copy
import unittest
from infra.core import Failure
from infra.console_minimize import audit_controls
from infra.gameplay import SCENARIOS, audit


def fixture(menu=True):
    state = {'console': {'address': 100, 'visible': 1}, 'minimize': {'visible': 0, 'bounds': [20,20,38,38]},
        'title_menu': {'address': 200, 'items': [{'name': 'Minimize', 'enabled': 0}, {'name': 'Close', 'enabled': 1}]} if menu else None,
        'server_paused': 1, 'menu_pause_depth': 1}
    labels = ['opened','former_button_click','title_menu_action','cached_reopen','after_reload']
    samples = [{'label': name, 'state': copy.deepcopy(state)} for name in labels]
    identity = {'session': 'test', 'scenario': 'console.minimize', 'scenario_version': 1, 'artifacts': {}, 'modules': {}, 'save_sha256': 'test', 'resources': {}}
    scenario = next(s for s in SCENARIOS if s['id']=='console.minimize')
    observations = [{'check': name, 'before': {'native': 1}, 'after': {'native': 1}, 'expected': True, 'observed': True,
                     'source': 'native-process-read', 'elapsed_seconds': 1} for name in scenario['checks']]
    next(r for r in observations if r['check']=='minimize_controls').update(before=samples[0]['state'], after=samples[-1]['state'])
    next(r for r in observations if r['check']=='first_input')['after'] = {'mouse_active': 1, 'paused': 0, 'server_paused': 0, 'menu_pause_depth': 0}
    evidence = {**identity, 'resolved_resources': {}, 'first_result_preserved': True, 'observations': observations,
        'control_samples': samples, 'former_button_click': {'client_x': 29, 'client_y': 29},
        'metrics': {'native_back_held': True, 'native_forward_held': True, 'signed_back': -3, 'signed_forward': 3,
                    'camera_left': -1, 'camera_right': 1, 'world_time_delta': 1, 'external_wait_seconds': 5}}
    return scenario,evidence,identity


class MinimizeAuditTests(unittest.TestCase):
    def remaining_fixture(self):
        _,e,i=fixture();s=next(s for s in SCENARIOS if s['id']=='console.minimize_remaining')
        e['scenario']=i['scenario']=s['id']
        e['control_samples']=[e['control_samples'][0],e['control_samples'][-1]]
        e['control_samples'][0]['label']='delayed_menu_open'
        e['delayed_menu_action']={'prior_menu':{'menu':{'visible':1}},
            'closed':{'menu':{'visible':0},'console':{'visible':0},'wall':10,'client_time':1},
            'waited':{'wall':15,'client_time':6},'opening_key_count':1,'key_down_wall':15.01}
        e['observations']=[r for r in e['observations'] if r['check'] in s['checks']]
        e['observations'].append({'check':'menu_first_delayed_open','before':{'native':1},'after':{'native':1},
            'expected':True,'observed':True,'source':'native-process-read','elapsed_seconds':5})
        return s,e,i

    def test_bounded_remaining_workflows_can_pass(self):
        self.assertEqual(audit(*self.remaining_fixture())['result'],'PASS')

    def test_remaining_cannot_hide_repeat_or_short_wait(self):
        for change in ['repeat','wait']:
            s,e,i=self.remaining_fixture()
            if change=='repeat':e['delayed_menu_action']['opening_key_count']=2
            else:e['delayed_menu_action']['waited']['wall']=12
            with self.subTest(change=change),self.assertRaises(Failure):audit(s,e,i)

    def test_native_hidden_button_cached_disabled_menu(self):
        self.assertEqual(audit(*fixture())['result'], 'PASS')

    def test_absent_menu_need_not_be_created(self):
        self.assertEqual(audit(*fixture(False))['result'], 'PASS')

    def test_visible_button_rejected_at_each_transition(self):
        for index in range(5):
            _,e,_ = fixture(); e['control_samples'][index]['state']['minimize']['visible'] = 1
            with self.subTest(index=index), self.assertRaises(Failure): audit_controls(e)

    def test_enabled_cached_menu_rejected(self):
        _,e,_ = fixture(); e['control_samples'][3]['state']['title_menu']['items'][0]['enabled'] = 1
        with self.assertRaises(Failure): audit_controls(e)

    def test_missing_menu_item_is_not_gameplay_proof(self):
        _,e,_ = fixture(); e['control_samples'][2]['state']['title_menu']['items'] = []
        with self.assertRaises(Failure): audit_controls(e)

    def test_wrong_click_or_disappeared_console_rejected(self):
        for change in ['click','console']:
            _,e,_ = fixture()
            if change=='click': e['former_button_click']['client_x'] = 50
            else: e['control_samples'][1]['state']['console']['visible'] = 0
            with self.subTest(change=change), self.assertRaises(Failure): audit_controls(e)

    def test_frozen_world_and_missing_input_rejected(self):
        for change in ['time','input','receipt']:
            s,e,i = fixture()
            if change=='time': e['metrics']['world_time_delta'] = 0
            elif change=='input': next(r for r in e['observations'] if r['check']=='first_input')['after']['mouse_active'] = 0
            else: e['metrics']['native_back_held'] = False
            with self.subTest(change=change), self.assertRaises(Failure): audit(s,e,i)
