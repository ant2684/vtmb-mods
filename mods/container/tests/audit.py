"""Independent quantitative audit; never accepts a generic observed=True."""
from collections import Counter
import re
from infra.core import require

KNIFE = 'item_w_knife'
FRIDGE = 'haven_refrigerator'
ORIGINAL = '8b4424348a888101000084c90f8401070000'
TRADE_STEPS = {
    True: [('reference-bought-one', 'buy'), ('reference-sold-one', 'sell'),
           ('reference-bought-two', 'buy'), ('reference-sold-two', 'sell')],
    False: [('shop-sold-one', 'sell'), ('shop-bought-one', 'buy'),
            ('shop-sold-two', 'sell'), ('shop-sold-three', 'sell'),
            ('shop-bought-two', 'buy'), ('shop-bought-three', 'buy')],
}


def count(s, owner, cls):
    return sum(i['count'] for i in s['owners'][owner]['inventory'] if i['class'] == cls)


def visible(s, owner, cls, side='donor'):
    slots = {i['slot'] for i in s['owners'][owner]['inventory'] if i['class'] == cls}
    return [r for r in s['ui']['rows'] if r['side'] == side and
            r['slot'] in slots and r['panel']['visible'] == 1]


def inventory_counts(s, owner):
    counts = Counter()
    for item in s['owners'][owner]['inventory']:
        counts[item['class']] += item['count']
    return dict(counts)


def same_owners(before, after, label):
    for owner in ['player', 'Trip']:
        require(inventory_counts(before, owner) == inventory_counts(after, owner),
                'trade inventory discontinuity: ' + label + '/' + owner)
        require(before['owners'][owner].get('money') == after['owners'][owner].get('money'),
                'trade wallet discontinuity: ' + label + '/' + owner)


def selected_knife(s, side, label):
    owner = 'Trip' if side == 'donor' else 'player'
    rows = [r for r in visible(s, owner, KNIFE, side) if r['selected'] == 1]
    require(len(rows) == 1 and isinstance(rows[0].get('entity'), int) and rows[0]['entity'] > 0,
            'missing/ambiguous selected native knife row: ' + label)
    return rows[0]


def stock_policy(s):
    policy = s.get('vendor_policy', {})
    require(policy.get('vendor') == 'Trip' and policy.get('class') == KNIFE,
            'missing native vendor policy')
    records = policy.get('records')
    require(isinstance(records, list) and records and
            all(isinstance(r, dict) and isinstance(r.get('name'), str) and
                isinstance(r.get('classes'), list) for r in records),
            'missing native vendor records')
    authored = any(r['name'] == 'Trip' and KNIFE in r['classes'] for r in records)
    require(policy.get('authored') is authored, 'authored stock disagrees with native records')
    expected = 0 if authored else -1
    require(type(policy.get('expected_buy_delta')) is int and
            policy['expected_buy_delta'] == expected,
            'stock decrement disagrees with native records')
    return expected


def reload_audit(e):
    s = e['states']
    receipt = e.get('reload_receipt', {})
    require(receipt.get('save_stem') == 'rc_container_state' and receipt.get('ready') is True,
            'missing completed nominated reload receipt')
    require(isinstance(receipt.get('save_sha256'), str) and
            re.fullmatch(r'[0-9a-fA-F]{64}', receipt['save_sha256']) is not None and
            type(receipt.get('size')) is int and receipt['size'] > 0,
            'missing saved-file identity')
    for key, label in [('saved', 'returned-first'), ('dirty', 'reload-dirty'), ('loaded', 'reloaded')]:
        require(receipt.get(key) == s.get(label) and isinstance(receipt.get(key), dict),
                'reload receipt snapshot differs: ' + key)
    require(count(receipt['dirty'], 'player', KNIFE) == 0 and
            count(receipt['dirty'], FRIDGE, KNIFE) == 2,
            'reload did not start from deliberately changed ownership')
    require(receipt['dirty'] != receipt['loaded'], 'reload did not change native state')
    for owner in ['player', FRIDGE]:
        require(inventory_counts(receipt['saved'], owner) == inventory_counts(receipt['loaded'], owner),
                'saved inventory was not restored: ' + owner)


def audit_transfer(e):
    s=e['states']
    require(all(v.get('price_filter_bytes','').startswith('e9') and v['price_filter_bytes'][10:]=='90' for v in s.values()),'server payment hook missing')
    expected=[('opened',0,2,True),('taken-one',1,1,True),('reopened',1,1,True),
              ('taken-two',2,0,False),('returned-first',1,1,True),('returned-two',0,2,True),
              ('cap-ready',10,2,True),('cap-selected',10,2,True),('cap-rejected',10,2,True),
              ('cap-freed',9,3,True),('capacity-available',9,3,True),('cap-refilled',10,2,True)]
    require(set(s)=={r[0] for r in expected},'missing narrow transfer states')
    for label,player,donor,shown in expected:
        v=s[label];require(count(v,'player',KNIFE)==player and count(v,FRIDGE,KNIFE)==donor,'native knife count/owner differs: '+label)
        rows=visible(v,FRIDGE,KNIFE)
        require(bool(rows)==shown and (not shown or len(rows)==1 and rows[0]['count']==donor),'native row/count differs: '+label)
        require(v['filter_bytes'].startswith('e9') and v['filter_bytes'][10:]=='90'*13,'candidate hook missing')
    for label in ['cap-selected','cap-rejected']:require(s[label]['ui']['action']['enabled'] is False,'full stack Take enabled')
    require(s['capacity-available']['ui']['action']['enabled'] is True,'capacity did not recover')
    labels=['taken-one','taken-two','returned-first','returned-two','cap-freed','cap-refilled']
    require([a['label'] for a in e['actions']]==labels,'missing/replayed narrow native actions')
    for a in e['actions']:
        require(a['kind']=='native-ui-click' and a['before']['ui']['action']['enabled'] is True,'native transfer action unavailable')
    return {'status':'PASS','scope':'narrow knife transfer, visibility and capacity only'}


def audit(e):
    if e['scenario']=='container.transfer':return audit_transfer(e)
    s = e['states']
    baseline = e['scenario'] == 'container.baseline'
    if not baseline:
        require(all(v.get('price_filter_bytes','').startswith('e9') and v['price_filter_bytes'][10:]=='90' for v in s.values()),'server payment hook missing')
    require(e['scenario'] in ['container.baseline', 'container.stacks'], 'unknown container scenario')
    def knives(label, player, fridge, shown=None):
        v = s[label]
        require(count(v, 'player', KNIFE) == player and count(v, FRIDGE, KNIFE) == fridge,
                'wrong native knife owners/count: ' + label)
        if shown is not None:
            rows = visible(v, FRIDGE, KNIFE)
            require(bool(rows) == shown, 'wrong donor visibility: ' + label)
            if shown:
                require(len(rows) == 1 and type(rows[0].get('count')) is int and
                        rows[0]['count'] == fridge,
                        'displayed knife count differs from native inventory: ' + label)
    require(all(v['filter_bytes'] == ORIGINAL if baseline else
                v['filter_bytes'].startswith('e9') and v['filter_bytes'][10:] == '90' * 13
                for v in s.values()), 'wrong baseline/candidate hook state')
    require(all(0 <= i['count'] <= 0x7fffffff for v in s.values() for i in v['items']),
            'invalid native count')
    knives('opened', 0, 2, True)
    knives('taken-one', 1, 1, not baseline)
    knives('reopened', 1, 1, not baseline)
    if baseline:
        knives('returned-one', 0, 2, True)
    else:
        for label, player, fridge, shown in [
            ('taken-two', 2, 0, False), ('returned-first', 1, 1, True),
            ('reloaded', 1, 1, True), ('returned-two', 0, 2, True),
            ('cap-ready', 10, 2, True), ('cap-selected', 10, 2, True),
            ('cap-rejected', 10, 2, True), ('cap-freed', 9, 3, True),
            ('capacity-available', 9, 3, True), ('cap-refilled', 10, 2, True)]:
            knives(label, player, fridge, shown)
        reload_audit(e)
        require(s['cap-selected']['ui']['action']['enabled'] is False and
                s['cap-rejected']['ui']['action']['enabled'] is False, 'full stack Take enabled')
        require(s['capacity-available']['ui']['action']['enabled'] is True,
                'Take did not recover after freeing capacity')
        for label, player, fridge in [
            ('blood-one', 1, 2), ('blood-reopened', 1, 2), ('blood-two', 2, 1),
            ('blood-returned-one', 1, 2), ('blood-returned-two', 0, 3)]:
            v = s[label]
            require(count(v, 'player', 'item_g_bloodpack') == player and
                    count(v, FRIDGE, 'item_g_bloodpack') == fridge, 'bloodpack conservation: ' + label)
            rows = visible(v, FRIDGE, 'item_g_bloodpack')
            require(len(rows) == 1 and type(rows[0].get('count')) is int and
                    rows[0]['count'] == fridge,
                    'displayed bloodpack count differs from native inventory: ' + label)
    controls = s['controls']
    require(count(controls, 'player', 'item_w_sledgehammer') ==
            count(controls, FRIDGE, 'item_w_sledgehammer') == 1, 'nonstack fixture missing')
    require(not visible(controls, FRIDGE, 'item_w_sledgehammer'), 'nonstack filter changed')
    require(count(controls, 'player', 'item_w_thirtyeight') ==
            count(controls, FRIDGE, 'item_w_thirtyeight') == 1, 'ammo fixture missing')
    ammo_rows = visible(controls, FRIDGE, 'item_w_thirtyeight')
    require(len(ammo_rows) == 1 and type(ammo_rows[0].get('ammo_count')) is int and
            ammo_rows[0]['ammo_count'] == 1,
            'duplicate firearm did not exercise the native ammo exception')
    # A fixed sequence and owner continuity prevent replaying one successful
    # action as evidence for a missing buy/sell transition.
    trades = [a for a in e.get('actions', []) if 'quote' in a]
    require([(a.get('label'), a['quote'].get('direction')) for a in trades] == TRADE_STEPS[baseline],
            'missing/duplicated/out-of-order trade operations')
    prices = {'buy': set(), 'sell': set()}
    if baseline:
        previous = s['shop-opened']
    else:
        for label in ['shop-cap-selected', 'shop-cap-rejected']:
            same_owners(s['shop-opened'], s[label], label)
            selected_knife(s[label], 'donor', label)
            require(s[label]['ui']['action_kind'] == 3 and
                    s[label]['ui']['action']['enabled'] is False, 'full-stack Buy enabled/unselected')
        require(count(s['shop-cap-selected'], 'player', KNIFE) == 10, 'shop cap fixture differs')
        previous = s['shop-cap-rejected']
    stock_changes = []
    for a in trades:
        before, after, q = a['before'], s[a['label']], a['quote']
        direction, price = q['direction'], q['price']
        side = 'donor' if direction == 'buy' else 'player'
        kind = 3 if direction == 'buy' else 4
        same_owners(previous, before, a['label'])
        require(a.get('class') == KNIFE and a.get('side') == side and
                a['kind'] == 'native-ui-click' and before['ui']['action']['enabled'] is True,
                'trade did not use an available native knife action')
        row = selected_knife(before, side, a['label'])
        require(q.get('selected') == row and q.get('selected_global') == row['entity'] and
                q.get('ammo_flag') == 0 and q.get('action_kind') == kind and
                before['ui']['action_kind'] == kind,
                'quote differs from selected item/side/action')
        if 'before' in q:
            require(q['before'] == before, 'quote belongs to a different preclick state')
        matches = re.findall(rb'Value:\s*\$([0-9]+)', bytes.fromhex(q['text_hex']))
        require(len(matches) == 1 and int(matches[0]) == price and type(price) is int and price > 0,
                'displayed quote differs')
        delta = 1 if direction == 'buy' else -1
        require(count(after, 'player', KNIFE) - count(before, 'player', KNIFE) == delta,
                'trade item gain/loss differs')
        require(after['owners']['player']['money'] - before['owners']['player']['money'] == -delta * price,
                'wallet differs from preclick quote')
        expected = stock_policy(before)
        require(stock_policy(after) == expected, 'native stock policy changed during trade')
        donor_delta = count(after, 'Trip', KNIFE) - count(before, 'Trip', KNIFE)
        require(donor_delta == (expected if direction == 'buy' else 1),
                'vendor stock differs from native policy')
        for owner in ['player', 'Trip']:
            left, right = inventory_counts(before, owner), inventory_counts(after, owner)
            left.pop(KNIFE, None)
            right.pop(KNIFE, None)
            require(left == right, 'trade changed another item class: ' + owner)
        if direction == 'buy':
            stock_changes.append(donor_delta)
        prices[direction].add(price)
        previous = after
    if not baseline:
        proof = e.get('baseline_controls', {}).get('evidence')
        require(proof and proof['scenario'] == 'container.baseline' and proof['artifacts'] == {},
                'missing unpatched control proof')
        require(proof['save_sha256'] == e['save_sha256'] and proof['modules'] == e['modules'] and
                proof['background_mods'] == e['background_mods'], 'baseline uses different inputs')
        audit(proof)
        require(bool(visible(controls, FRIDGE, 'item_w_thirtyeight')) ==
                bool(visible(proof['states']['controls'], FRIDGE, 'item_w_thirtyeight')),
                'ammo visibility differs from baseline')
        reference = [a for a in proof['actions'] if 'quote' in a]
        reference_buy = [count(proof['states'][a['label']], 'Trip', KNIFE) -
                         count(a['before'], 'Trip', KNIFE) for a in reference
                         if a['quote']['direction'] == 'buy']
        require(len(set(reference_buy)) == 1 and all(delta == reference_buy[0] for delta in stock_changes),
                'native vendor stock policy differs from baseline')
        for direction in ['buy', 'sell']:
            require(prices[direction] == {a['quote']['price'] for a in reference
                                         if a['quote']['direction'] == direction},
                    'native price changed: ' + direction)
    require(len(e.get('actions', [])) >= 2, 'native UI actions not recorded')
    return {'status': 'PASS', 'scope': 'native ownership/count plus load transition, live UI rows, '
            'action availability, native vendor policy, quoted prices and wallet'}
