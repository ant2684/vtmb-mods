import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from infra.core import Failure, atomic_json
from mods.container.tests.audit import audit

ORIGINAL = '8b4424348a888101000084c90f8401070000'
CANDIDATE = 'e9' + '00' * 4 + '90' * 13
KNIFE = 'item_w_knife'


def state(player, fridge, shown, stock=1, money=5000, authored=True):
    def item(cls, quantity, slot):
        return {'class': cls, 'count': quantity, 'slot': slot}
    owners = {
        'player': {'money': money, 'inventory': [item('item_w_sledgehammer', 1, 21),
            item('item_w_thirtyeight', 1, 28)] + ([item(KNIFE, player, 1)] if player else [])},
        'haven_refrigerator': {'inventory': [item(KNIFE, fridge, 0),
            item('item_w_sledgehammer', 1, 21), item('item_w_thirtyeight', 1, 28)]},
        'Trip': {'money': 1000, 'inventory': [item(KNIFE, stock, 0)] if stock else []}}
    rows = [{'side': 'donor', 'slot': 28, 'count': 1, 'entity': 400,
             'selected': 0, 'ammo_count': 1, 'panel': {'visible': 1}}]
    if shown:
        rows.append({'side': 'donor', 'slot': 0, 'count': fridge, 'entity': 200,
                     'selected': 1, 'panel': {'visible': 1}})
    if player:
        rows.append({'side': 'player', 'slot': 1, 'count': player, 'entity': 300,
                     'selected': 0, 'panel': {'visible': 1}})
    return {'owners': owners, 'items': [i for o in owners.values() for i in o['inventory']],
        'ui': {'rows': rows, 'action': {'enabled': True}, 'action_kind': 3},
        'filter_bytes': ORIGINAL, 'price_filter_bytes':'0f8486000000',
        'vendor_policy': {'vendor': 'Trip', 'class': KNIFE, 'authored': authored,
            'expected_buy_delta': 0 if authored else -1,
            'records': [{'name': 'Trip', 'classes': [KNIFE] if authored else []}]}}


def add_trade(e, previous, label, direction, authored):
    before = copy.deepcopy(previous)
    side = 'donor' if direction == 'buy' else 'player'
    kind = 3 if direction == 'buy' else 4
    for row in before['ui']['rows']:
        row['selected'] = int(row['side'] == side and row['slot'] == (0 if side == 'donor' else 1))
    selected = next(r for r in before['ui']['rows'] if r['selected'])
    before['ui']['action_kind'] = kind
    before['ui']['action']['enabled'] = True
    price, delta = (90, 1) if direction == 'buy' else (5, -1)
    def total(owner):
        return sum(i['count'] for i in before['owners'][owner]['inventory'] if i['class'] == KNIFE)
    stock = total('Trip') + ((0 if authored else -1) if direction == 'buy' else 1)
    after = state(total('player') + delta, 2, True, stock,
                  before['owners']['player']['money'] - delta * price, authored)
    after['filter_bytes'] = previous['filter_bytes']
    after['price_filter_bytes'] = previous['price_filter_bytes']
    e['states'][label] = after
    e['actions'].append({'label': label, 'kind': 'native-ui-click', 'class': KNIFE,
        'side': side, 'before': before, 'quote': {'direction': direction, 'price': price,
        'text_hex': ('Value: $' + str(price)).encode().hex(), 'selected': copy.deepcopy(selected),
        'selected_global': selected['entity'], 'ammo_flag': 0, 'action_kind': kind,
        'before': before}})
    return after


def baseline(authored=True):
    e = {'scenario': 'container.baseline', 'artifacts': {}, 'save_sha256': 'a' * 64,
         'modules': {'client': 'pin'}, 'background_mods': {}, 'actions': [{'label': 'take'}, {'label': 'return'}],
         'states': {'opened': state(0, 2, True), 'taken-one': state(1, 1, False),
                    'reopened': state(1, 1, False), 'returned-one': state(0, 2, True),
                    'controls': state(0, 2, True), 'shop-opened': state(0, 2, True, authored=authored)}}
    previous = e['states']['shop-opened']
    for label, direction in [('reference-bought-one', 'buy'), ('reference-sold-one', 'sell'),
                             ('reference-bought-two', 'buy'), ('reference-sold-two', 'sell')]:
        previous = add_trade(e, previous, label, direction, authored)
    return e


def fixed(authored=True):
    e = {'scenario': 'container.stacks', 'save_sha256': 'a' * 64, 'modules': {'client': 'pin'},
         'background_mods': {}, 'actions': [], 'states': {}}
    for label, player, fridge, shown in [
        ('opened', 0, 2, True), ('taken-one', 1, 1, True), ('reopened', 1, 1, True),
        ('taken-two', 2, 0, False), ('returned-first', 1, 1, True), ('reload-dirty', 0, 2, True),
        ('reloaded', 1, 1, True), ('returned-two', 0, 2, True), ('cap-ready', 10, 2, True),
        ('cap-selected', 10, 2, True), ('cap-rejected', 10, 2, True), ('cap-freed', 9, 3, True),
        ('capacity-available', 9, 3, True), ('cap-refilled', 10, 2, True), ('controls', 10, 2, True)]:
        e['states'][label] = state(player, fridge, shown, authored=authored)
    for label in ['returned-first', 'reloaded']:
        v = e['states'][label]
        item = {'class': 'item_g_bloodpack', 'count': 3, 'slot': 4}
        v['owners']['haven_refrigerator']['inventory'].append(item)
        v['items'].append(item)
    for label, player, fridge in [('blood-one', 1, 2), ('blood-reopened', 1, 2), ('blood-two', 2, 1),
                                  ('blood-returned-one', 1, 2), ('blood-returned-two', 0, 3)]:
        v = state(10, 2, True, authored=authored)
        for owner, quantity in [('player', player), ('haven_refrigerator', fridge)]:
            if quantity:
                item = {'class': 'item_g_bloodpack', 'count': quantity, 'slot': 4}
                v['owners'][owner]['inventory'].append(item)
                v['items'].append(item)
                if owner == 'haven_refrigerator':
                    v['ui']['rows'].append({'side': 'donor', 'slot': 4, 'count': quantity, 'selected': 0,
                                           'entity': 500, 'panel': {'visible': 1}})
        e['states'][label] = v
    for label in ['cap-selected', 'cap-rejected']:
        e['states'][label]['ui']['action']['enabled'] = False
    e['states']['shop-opened'] = state(10, 2, True, authored=authored)
    for label in ['shop-cap-selected', 'shop-cap-rejected']:
        e['states'][label] = copy.deepcopy(e['states']['shop-opened'])
        e['states'][label]['ui']['action']['enabled'] = False
    for v in e['states'].values():
        v['filter_bytes'] = CANDIDATE
        v['price_filter_bytes'] = 'e9'+'00'*4+'90'
    previous = e['states']['shop-cap-rejected']
    for label, direction in [('shop-sold-one', 'sell'), ('shop-bought-one', 'buy'),
                             ('shop-sold-two', 'sell'), ('shop-sold-three', 'sell'),
                             ('shop-bought-two', 'buy'), ('shop-bought-three', 'buy')]:
        previous = add_trade(e, previous, label, direction, authored)
    e['reload_receipt'] = {'save_stem': 'rc_container_state', 'save_sha256': 'b' * 64,
        'size': 100, 'ready': True, 'saved': copy.deepcopy(e['states']['returned-first']),
        'dirty': copy.deepcopy(e['states']['reload-dirty']), 'loaded': copy.deepcopy(e['states']['reloaded'])}
    e['baseline_controls'] = {'evidence': baseline(authored)}
    return e


class ContainerAuditTests(unittest.TestCase):
    def test_quantitative_unpatched_fixture(self):
        audit(baseline())

    def test_fixed_fixture_infinite_and_finite_stock(self):
        for authored in [True, False]:
            with self.subTest(authored=authored):
                audit(fixed(authored))

    def test_missing_server_payment_hook_rejected(self):
        e=fixed();e['states']['opened']['price_filter_bytes']='0f8486000000'
        with self.assertRaises(Failure):audit(e)

    def test_generic_pass_does_not_hide_lost_item(self):
        e = baseline(); e['observed'] = True
        e['states']['taken-one']['owners']['haven_refrigerator']['inventory'][0]['count'] = 0
        with self.assertRaises(Failure): audit(e)

    def test_wrong_ui_visibility_rejected(self):
        e = baseline()
        e['states']['taken-one']['ui']['rows'].append({'side': 'donor', 'slot': 0, 'panel': {'visible': 1}})
        with self.assertRaises(Failure): audit(e)

    def test_duplicate_firearm_must_exercise_ammo_exception(self):
        for fixed_run in [False, True]:
            for hidden in [False, True]:
                e = fixed() if fixed_run else baseline()
                rows = e['states']['controls']['ui']['rows']
                firearm = next(r for r in rows if r['slot'] == 28)
                if hidden: firearm['panel']['visible'] = 0
                else: firearm['ammo_count'] = 0
                with self.subTest(fixed=fixed_run, hidden=hidden), self.assertRaises(Failure):
                    audit(e)

    def test_displayed_knife_count_must_match_native(self):
        for fixed_run in [False, True]:
            for bad in [0, 1, 999, None]:
                e = fixed() if fixed_run else baseline()
                row = next(r for r in e['states']['opened']['ui']['rows'] if r['slot'] == 0)
                if bad is None: row.pop('count')
                else: row['count'] = bad
                with self.subTest(fixed=fixed_run, bad=bad), self.assertRaises(Failure):
                    audit(e)

    def test_visible_stack_requires_exactly_one_row(self):
        for cls in ['knife', 'bloodpack']:
            e = fixed(); label = 'opened' if cls == 'knife' else 'blood-two'
            rows = e['states'][label]['ui']['rows']; slot = 0 if cls == 'knife' else 4
            rows.append(copy.deepcopy(next(r for r in rows if r['slot'] == slot)))
            with self.subTest(cls=cls), self.assertRaises(Failure): audit(e)

    def test_displayed_bloodpack_count_must_match_native(self):
        for bad in [0, 2, 999, None]:
            e = fixed()
            row = next(r for r in e['states']['blood-two']['ui']['rows'] if r['slot'] == 4)
            if bad is None: row.pop('count')
            else: row['count'] = bad
            with self.subTest(bad=bad), self.assertRaises(Failure): audit(e)

    def test_ammo_mode_rejects_garbage_or_duplicate_rows(self):
        for bad in [2, 0x19200001, None, 'duplicate']:
            e = baseline(); rows = e['states']['controls']['ui']['rows']
            row = next(r for r in rows if r['slot'] == 28)
            if bad == 'duplicate': rows.append(copy.deepcopy(row))
            elif bad is None: row.pop('ammo_count')
            else: row['ammo_count'] = bad
            with self.subTest(bad=bad), self.assertRaises(Failure): audit(e)

    def test_wrong_wallet_rejected(self):
        e = baseline(); e['states']['reference-bought-one']['owners']['player']['money'] += 1
        with self.assertRaises(Failure): audit(e)

    def test_quoted_price_is_not_an_unverified_number(self):
        e = baseline(); e['actions'][2]['quote']['price'] = 89
        with self.assertRaises(Failure): audit(e)

    def test_missing_native_trade_rejected(self):
        e = baseline(); e['actions'].pop()
        with self.assertRaises(Failure): audit(e)

    def test_candidate_cannot_be_unpatched_reference(self):
        e = baseline(); e['states']['opened']['filter_bytes'] = CANDIDATE
        with self.assertRaises(Failure): audit(e)

    def test_replayed_or_reordered_trade_rejected(self):
        for duplicate in [True, False]:
            e = baseline()
            if duplicate: e['actions'][-1] = copy.deepcopy(e['actions'][3])
            else: e['actions'][2], e['actions'][3] = e['actions'][3], e['actions'][2]
            with self.subTest(duplicate=duplicate), self.assertRaises(Failure): audit(e)

    def test_trade_state_continuity_rejected(self):
        for owner in ['player', 'Trip']:
            e = baseline(); e['actions'][3]['before']['owners'][owner]['money'] += 17
            with self.subTest(owner=owner), self.assertRaises(Failure): audit(e)

    def test_trade_inventory_continuity_rejected(self):
        e = baseline(); e['actions'][3]['before']['owners']['player']['inventory'][0]['count'] += 1
        with self.assertRaises(Failure): audit(e)

    def test_quote_native_selection_receipts_rejected(self):
        for key, bad in [('selected_global', 999), ('ammo_flag', 1), ('action_kind', 4)]:
            e = baseline(); e['actions'][2]['quote'][key] = bad
            with self.subTest(key=key), self.assertRaises(Failure): audit(e)

    def test_quote_row_must_be_in_before(self):
        e = baseline(); e['actions'][2]['quote']['selected']['entity'] = 999
        with self.assertRaises(Failure): audit(e)

    def test_quote_direction_must_match_actual_side(self):
        e = baseline(); e['actions'][2]['side'] = 'player'
        with self.assertRaises(Failure): audit(e)

    def test_native_stock_records_are_required(self):
        e = baseline(); e['actions'][2]['before']['vendor_policy']['records'] = []
        with self.assertRaises(Failure): audit(e)

    def test_native_stock_policy_cannot_be_asserted(self):
        for key, bad in [('authored', False), ('expected_buy_delta', -1)]:
            e = baseline(); e['actions'][2]['before']['vendor_policy'][key] = bad
            with self.subTest(key=key), self.assertRaises(Failure): audit(e)

    def test_buy_must_follow_derived_stock_decrement(self):
        e = baseline(); e['states']['reference-bought-one']['owners']['Trip']['inventory'][0]['count'] = 0
        with self.assertRaises(Failure): audit(e)

    def test_dirty_reload_is_required(self):
        e = fixed(); e['states']['reload-dirty'] = copy.deepcopy(e['states']['reloaded'])
        e['reload_receipt']['dirty'] = copy.deepcopy(e['states']['reload-dirty'])
        with self.assertRaises(Failure): audit(e)

    def test_reload_receipt_binds_all_snapshots(self):
        for key in ['saved', 'dirty', 'loaded']:
            e = fixed(); e['reload_receipt'][key]['ui']['action_kind'] += 1
            with self.subTest(key=key), self.assertRaises(Failure): audit(e)

    def test_reload_requires_file_identity_and_readiness(self):
        for key, bad in [('save_sha256', 'not-a-hash'), ('size', 0), ('ready', False),
                         ('save_stem', 'another_save')]:
            e = fixed(); e['reload_receipt'][key] = bad
            with self.subTest(key=key), self.assertRaises(Failure): audit(e)

    def test_reload_restores_other_inventory(self):
        e = fixed(); v = e['states']['reloaded']
        v['owners']['haven_refrigerator']['inventory'][-1]['count'] = 2
        e['reload_receipt']['loaded'] = copy.deepcopy(v)
        with self.assertRaises(Failure): audit(e)

    def test_shop_cap_rejection_preserves_vendor_and_money(self):
        for owner in ['player', 'Trip']:
            e = fixed(); e['states']['shop-cap-rejected']['owners'][owner]['money'] += 1
            with self.subTest(owner=owner), self.assertRaises(Failure): audit(e)

    def test_shop_cap_requires_selected_buy(self):
        e = fixed()
        for row in e['states']['shop-cap-selected']['ui']['rows']: row['selected'] = 0
        with self.assertRaises(Failure): audit(e)


class AtomicJournalTests(unittest.TestCase):
    def test_transient_windows_reader_lock_is_retried(self):
        import os
        with tempfile.TemporaryDirectory() as t:
            target = Path(t) / 'journal.json'; real = os.replace; calls = []
            def replace(a, b):
                calls.append(1)
                if len(calls) == 1: raise PermissionError('sharing violation')
                return real(a, b)
            with patch('infra.core.os.replace', side_effect=replace), patch('time.sleep'):
                atomic_json(target, {'state': 'saved'})
            self.assertIn('saved', target.read_text()); self.assertEqual(len(calls), 2)

    def test_persistent_refusal_keeps_original_and_pending(self):
        with tempfile.TemporaryDirectory() as t:
            target = Path(t) / 'journal.json'; target.write_text('original')
            with patch('infra.core.os.replace', side_effect=PermissionError('persistent')), patch('time.sleep'):
                with self.assertRaises(PermissionError): atomic_json(target, {'state': 'new'})
            self.assertEqual(target.read_text(), 'original')
            self.assertTrue(target.with_name('journal.json.pending').exists())
