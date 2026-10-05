"""Recovered gangster_gate readiness, unchanged; native snapshot adapter."""
import math
MELEE_CLASSES=()
def readiness(snapshot, mode, baseline, preserve_layout=False):
    actors = snapshot['entities']
    players = [e for e in actors if e['class'] == 'player']
    targets = [e for e in actors if e.get('name') in ('fk_target_0', 'fk_target_1')]
    if len(players) != 1 or len(targets) != 2 or len({e['name'] for e in targets}) != 2:
        return 'player/target identity count', None
    if len({e['address'] for e in players+targets}) != 3:
        return 'aliased actor identities', None
    if any(e['class'] == 'npc_VFrenzyShadow' for e in actors):
        return 'unexpected existing Shadow', None
    distractors = [e for e in actors if e.get('name') == 'bum_male']
    if not preserve_layout and any(not int(e['body_effects'],16) & 0x20 for e in distractors):
        return 'known competing pedestrian still visible', None
    p = players[0]
    for e in targets:
        if e['class'] != 'npc_VHumanCombatant' or e['address'] == p['address']:
            return 'wrong target class/identity', None
        if '/gangmember_male_2/' not in e.get('model','').lower():
            return 'target is not the native gangster model', None
        if e['bcc_targetable_1480'] != '01' or e['bcc_alive_1481'] != '01' or e['life_state_200'] != '00' or e['health_field_210'] <= 0:
            return 'target not a living damageable combatant', None
        lo, hi = e['collision_mins'], e['collision_maxs']
        if not all(math.isfinite(x) for x in lo + hi) or not all(hi[i] > lo[i] for i in range(3)):
            return 'invalid collision bounds', None
        if not 1 <= e['solid'] <= 6 or int(e['body_effects'],16) & 0x20:
            return 'non-solid or hidden target', None
        if int(e['spawn_flags_434'],16) & 0x8000:
            return 'native Frenzy spawnflag exclusion', None
        if e.get('npc_think_early_exit_6080')!='00':
            return 'native NPC think disabled or unconfirmed', None
        if e['enemy_handle_5ce0'] != p['handle']:
            return 'gangster has not acquired the player as enemy', None
    expected = {'katana':'item_w_katana','fists':'item_w_fists','protean':'item_w_claws','protean1':'item_w_fists','firearm':'item_w_thirtyeight'}.get(mode)
    if mode in MELEE_CLASSES: expected=mode
    if mode=='protean' and p.get('active_protean_1380')==1: expected='item_w_fists'
    if p.get('weapon_class') != expected:
        return 'starting weapon not equipped', None
    if snapshot['ai_global_flags'] != '0x0' or snapshot['server_paused'] or snapshot['engine_paused']:
        return 'AI disabled or game paused', None
    if baseline and snapshot['hooks']['0x161fc0']['bytes'].startswith('e9'):
        return 'Katana prototype is still active in baseline', None
    if not baseline:
        for rva in ('0x161fc0','0x33f6d0','0x329a70'):
            if not snapshot['hooks'].get(rva,{}).get('bytes','').startswith('e9'):
                return 'Frenzy exit hook not installed: '+rva,None
    if (mode == 'katana' or mode in MELEE_CLASSES) and not baseline:
        for rva in ('0x161fc0','0x162038','0x375c80','0x8dc40','0x375f50','0x1618e0','0x376f20','0xf03d','0xc036','0x8dd30','0x32b0','0xd4e0','0x2725d0','0xd0b2','0x2a7c','0x272400','0x32ef60','0x3e9e00','0x343020','0x3daf'):
            if not snapshot['hooks'][rva]['bytes'].startswith('e9'):
                return 'Katana hook not installed: ' + rva, None
        # This site is already an E9 in the stock DLL. Its original destination
        # must not be mistaken for the newly installed inventory wrapper.
        stock_inventory = int(snapshot['modules']['vampire.dll'], 16) + 0x334e70
        if int(snapshot['hooks']['0x3daf'].get('target', '0x0'), 16) == stock_inventory:
            return 'Katana inventory hook still has its stock destination', None
    if not snapshot['hooks']['0x33ed75']['bytes'].startswith('eb27'):
        return 'existing Protean short-branch patch not installed', None
    for rva in ('0x16c558', '0x33e9be', '0x1f9177', '0x3510d7', '0x1e56e0', '0x1e5b30', '0x16c5be'):
        if not snapshot['hooks'][rva]['bytes'].startswith('e9'):
            return 'existing mod hook not installed: ' + rva, None
    return None, targets

def check(row):
    entities=[]
    for a in row['actors']:
        e=dict(a, address=hex(a['ptr']), handle=hex(a['handle']),
            body_effects=hex(a['effects']),bcc_targetable_1480='%02x'%a['targetable'],
            bcc_alive_1481='%02x'%a['alive'],life_state_200='%02x'%a['life'],
            health_field_210=a['health'],collision_mins=a['mins'],collision_maxs=a['maxs'],
            spawn_flags_434=hex(a['spawn_flags']),npc_think_early_exit_6080='%02x'%a.get('think_disabled',255),
            enemy_handle_5ce0=hex(a['enemy']),active_protean_1380=a.get('protean'))
        entities.append(e)
    snapshot=dict(entities=entities,ai_global_flags=hex(row['ai_global_flags']),
        server_paused=row['paused'],engine_paused=row['engine_paused'],
        hooks={rva:{'bytes':data} for rva,data in row['hooks'].items()})
    # Original baseline gate refuses the unrelated Katana prototype.
    return readiness(snapshot,'protean',True)[0]
