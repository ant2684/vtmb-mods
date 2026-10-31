import ast,math

def audit(mode,log,rows):
    marks={}
    for line in log.splitlines():
        t=ast.literal_eval(line)
        if t[0]=='NATIVE':marks[t[1]]=t[2]
    required=['COEXIST_MORPH_ON_BODY','COEXIST_MORPH_ON_DONE','COEXIST_MORPH_OFF_BODY','COEXIST_BEFORE_0','COEXIST_ACTIVE_0','COEXIST_END','COEXIST_LOADED','COEXIST_ACTIVE_1','COEXIST_BEFORE_MAP_ACTIVE','COEXIST_MAPPED']
    assert all(k in marks for k in required),(list(marks),required)
    assert marks['COEXIST_MORPH_ON_BODY']['state']==30
    assert marks['COEXIST_MORPH_ON_DONE']['wolf']==1
    assert marks['COEXIST_MORPH_OFF_BODY']['state']==30
    for label in ['COEXIST_END','COEXIST_LOADED','COEXIST_MAPPED']:
        assert not marks[label]['frenzy'] and marks[label]['controller']=='0xffffffff',marks[label]
    ended=marks['COEXIST_END']
    assert ended['item_classes'].get(ended['inventory'][0])=='item_w_fists','Native fists slot0 not restored'
    assert "('COEXIST_BLOOD', 15)" in log
    attacks=[];health={};losses=[];seen_controllers=set()
    allowed={'katana_attack_med','katana_attack_Left_Right','katana_attack_Left_Right2','katana_attack_heavy','katana_combo_A1','katana_combo_A2','katana_combo_B1','katana_combo_B2','katana_combo_C1','katana_combo_C2','katana_combo_D1','katana_combo_D2','katana_attack_far_spin','katana_attack_Run','katana_attack_SweepKickCombo','katana_attack_medcombo','katana_running_attack'}
    windows=[(marks['COEXIST_ACTIVE_0']['observer_time'],marks['COEXIST_END']['observer_time']),(marks['COEXIST_ACTIVE_1']['observer_time'],marks['COEXIST_BEFORE_MAP_ACTIVE']['observer_time'])]
    previous_player_graph=previous_player_inventory=None;previous_shadow_graphs={}
    stable_shadow_graphs=0
    for r in rows:
        # Guard contract begins with a live, owned Frenzy controller; loader
        # snapshots legitimately precede native inventory reconstruction.
        if not r.get('frenzy',0):continue
        valid=[h for h in r['inventory'] if h!=0xffffffff]
        assert len(valid)==len(set(valid)),('duplicate player inventory',r)
        entities=r.get('inventory_items',{})
        if previous_player_graph==entities and previous_player_inventory==r['inventory']:
            for i,h in enumerate(r['inventory']):
                if h in entities:assert entities[h]['slot']==i and entities[h]['owner']==next(a['handle'] for a in r['actors'] if a['cls']=='player'),('stable player slot/owner',r['game_time'])
        previous_player_graph=entities;previous_player_inventory=r['inventory']
        for shadow in [a for a in r['actors'] if a['cls']=='npc_VFrenzyShadow' and hex(a['handle'])==r['controller']]:
            seen_controllers.add(shadow['handle'])
            inv=[h for h in shadow['inventory'] if h!=0xffffffff];assert len(inv)==len(set(inv))
            shadow_items=shadow.get('inventory_items',{})
            state=(shadow['inventory'],shadow_items)
            if previous_shadow_graphs.get(shadow['handle'])==state:
                stable_shadow_graphs+=1
                for i,h in enumerate(shadow['inventory']):
                    if h in shadow_items:assert shadow_items[h]['slot']==i and shadow_items[h]['owner']==shadow['handle']
            previous_shadow_graphs[shadow['handle']]=state
            assert 'feed' not in shadow['sequence_name'].lower(),shadow
            weapon=shadow_items.get(shadow['weapon'],{})
            assert weapon.get('cls')=='item_w_katana',('melee binding missing',shadow,weapon)
            if shadow['activity']==2463:
                assert shadow['sequence_name'] in allowed,shadow
                attacks.append((r,shadow))
            enemy=shadow['enemy']
            target=next((a for a in r['actors'] if a['handle']==enemy and 'native_health' in a),None)
            if target:
                previous=health.get(enemy)
                if previous is not None and target['native_health']<previous:losses.append((enemy,previous,target['native_health']))
                health[enemy]=target['native_health']
    assert stable_shadow_graphs>=3,'No stable owned inventory graph coverage'
    assert len(attacks)>=3 and losses,('no selected-target melee damage',len(attacks),losses)
    assert not marks['COEXIST_MAPPED']['shadow_actors'],'Shadow survived native map transition'
    assert len(seen_controllers)>=2,'No reload/reentry controller'
    before=next(r for r in rows if r['frenzy'] and r['controller']!='0xffffffff')
    assert any(a['activity']==19 for r in rows for a in r['actors'] if a['cls']=='npc_VFrenzyShadow'),'No native approach'
    assert all(r['state']!=30 for r,a in attacks),'Melee incorrectly starts Protean scene'
    assert "'sm_hub_1'" in log or 'sm_hub_1' in log,'Native warehouse transition not completed'
    return ['Core/Lifecycle/Melee all installed; original Protean entry/return retained; correct owned sword/positive selected health loss/no feeding; player+Shadow unique slots/owners; natural Frenzy end, same-save reload/reentry and native warehouse transition clear controllers']
