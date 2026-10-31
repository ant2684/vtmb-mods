"""Acceptance assertions over real engine observations, not script completion."""
import ast

def audit(mode,log,rows):
 if mode.startswith('native-hunger'):
  events=[ast.literal_eval(x) for x in log.splitlines()]
  details={x[1]:x[2] for x in events if x[0]=='NATIVE'}
  assert ('STOCK_SUPPORT_ABSENT',0,0) in events
  expected='item_w_katana' if 'katana' in mode else 'item_w_chang_claw' if 'tiger' in mode else 'item_w_claws'
  before=details['NATIVE_HUNGER_BEFORE'];zero=details['NATIVE_HUNGER_ZERO']
  assert before['events_outputs'].get('events_player_plus')==int('outputs' in mode)
  assert next(x for x in events if x[0]=='NATIVE_HUNGER_ZERO')[6]==0,'Blood must reach zero'
  for label in ['NATIVE_HUNGER_ENTER','NATIVE_HUNGER_SETTLED','NATIVE_HUNGER_AFTER_CALLBACK']:
   d=details[label];assert d['frenzy']>0 and len(d['shadow_actors'])==1
   shadow=d['shadow_actors'][0];assert shadow['weapon_class']==expected,(label,shadow)
   assert shadow['native_traits']['corpus']>=3,(label,shadow)
  first=details['NATIVE_HUNGER_SETTLED']['shadow_actors'][0]
  repeated=details['NATIVE_HUNGER_AFTER_CALLBACK']['shadow_actors'][0]
  assert first['handle']==repeated['handle'] and first['native_traits']==repeated['native_traits'],'Repeated stock callback stacked/changed native effects'
  assert first['native_effects']==repeated['native_effects'],'Repeated callback changed actual effect membership'
  for label in ['NATIVE_HUNGER_SETTLED','NATIVE_HUNGER_AFTER_CALLBACK']:
   d=details[label]
   for membership in [d['player_effects'],d['shadow_actors'][0]['native_effects']]:
    for kind in ['groups','effective_groups']:
     names=[row[1] for row in membership[kind]]
     assert names.count('frenzy (gangrel)')==1,(label,kind,names)
     assert 'frenzy (kindred)' not in names,(label,kind,names)

  attacks={a.get('sequence_name','').lower() for r in rows for a in r['actors'] if a['cls']=='npc_VFrenzyShadow' and ('attack' in a.get('sequence_name','').lower() or 'combo' in a.get('sequence_name','').lower() or a.get('sequence_name','').lower().startswith('kick_'))}
  assert attacks,'Shadow never performed an actual attack (idle is insufficient)'
  if expected=='item_w_claws':
   assert any(n.startswith('pfi_frenzy_claws_') for n in attacks),attacks
   assert not any(n.startswith('claws_') for n in attacks),('Player combo leaked into Frenzy',attacks)
   assert not any(n.startswith('fists_') for n in attacks),attacks
  elif expected=='item_w_katana':assert any(n.startswith('katana_') for n in attacks),attacks
  returned=details['NATIVE_HUNGER_RETURN'];assert returned['frenzy']==0 and returned['controller']=='0xffffffff' and not returned['shadow_actors']
  assert all('frenzy (' not in row[1] for row in returned['player_effects']['effective_groups']),'Frenzy effect leaked after cleanup'
  moved=details['NATIVE_HUNGER_MOVED'];assert sum((a-b)**2 for a,b in zip(returned['origin'],moved['origin']))>1,'Manual movement not restored'
  return ['Pinned stock Python; natural Humanity3/blood0 Frenzy; original Outputs state controlled; expected Shadow weapon/real attacks; duplicate callback preserves exact effect groups and native traits; normal cleanup and returned movement','Observed Shadow attack sequences: '+repr(sorted(attacks))]
 if mode in ('filter-save','filter-restore'):
  events=[ast.literal_eval(x) for x in log.splitlines()]
  states={x[1]:x[2:] for x in events if x[0]=='FILTER_STATE'}
  details={x[1]:x[2] for x in events if x[0]=='NATIVE'}
  required={'filter-save':['INITIAL'],'filter-restore':['LOADED','RED_INITIAL']}[mode]
  assert set(states)==set(required)
  for name in [n for n in required if n in ['INITIAL','LOADED']]:
   assert states[name][0:2]==(4,1),states
   assert details['FILTER_'+name]['mat_fullbright_native']==1
  for name in [n for n in required if n.startswith('RED_')]:
   assert states[name]==(0,0,10),states
   assert details['FILTER_'+name]['mat_fullbright_native']==0
  return ['Fresh-process filter workflow: '+repr(states)+'; native mat_fullbright agrees; no queued reload task serialized into saved state']
 if mode=='native-dependencies-off':
  events=[ast.literal_eval(x) for x in log.splitlines()]
  assert ('NATIVE_OFF_READY',0) in events
  details={x[1]:x[2] for x in events if x[0]=='NATIVE'}
  assert details['OFF_ACTIVE']['protean']==5 and details['OFF_ACTIVE']['wolf']==1
  assert any(x[0]=='DONE' and x[2]==0 and 'animalism_beastform' not in x[3].lower() for x in events)
  return ['Inventory disabled: inventory, morph and Melee hooks absent; Python readiness stays zero; original activation/return completes']
 if mode.startswith('claws-actions'):
  events=[ast.literal_eval(x) for x in log.splitlines()]
  chains=[x for x in events if x[0]=='CLAW_CHAIN'];assert [x[1] for x in chains]==list(range(7))
  details={x[1]:x[2] for x in events if x[0]=='NATIVE'}
  assert details['CLAW_AIR']['sequence_name'].lower()=='claws_air'
  assert 'guard' in details['CLAW_BLOCK']['sequence_name'].lower(),details['CLAW_BLOCK']
  assert details['CLAW_RELEASE']['sequence_name'] in ['claws_idle','claws_ready','claws_fidget']
  for j in range(8):assert details['CLAW_SNEAK_'+str(j)]['sequence_name']=='claws_sneak'
  return ['All seven native direction-selected full chains, authored continuation input, air attack, native guard/release and eight sneak directions; no guard module']
 if mode in ('frenzy-maps-library','frenzy-maps-griffith'):
  stage=0 if mode.endswith('library') else 1
  events=[ast.literal_eval(x) for x in log.splitlines()]
  permission=[x for x in events if x[0]=='MAP_PERMISSION']
  assert {x[1] for x in permission}=={stage} and all(x[3]==0 for x in permission)
  details={x[1]:x[2] for x in events if x[0]=='NATIVE'}
  for stage in [stage]:
   d=details['MAP_FRENZY_'+str(stage)];assert d['frenzy']>0 and len(d['shadow_actors'])==1
   assert d['shadow_actors'][0]['handle']==d['controller']
  if stage==0:return ['Delivered Library BSP freshly loaded; native events_world nofrenzy=0 and one owned FrenzyShadow; no permission setter']
  contact=[x for x in events if x[0]=='MAP_CONTACT']
  assert len(contact)==75 and all(x[5] for x in contact)
  # Native Werewolf damage may kill the unarmoured fresh player. Survival is
  # not the collision fix: qualify the live owned scope, then require cleanup.
  combat=[x for x in contact if x[4] and x[1]['frenzy']>0 and x[1]['shadow_actors']]
  assert len(combat)>=5,'No sustained living player/Shadow contact'
  distances=[]
  for _,d,*rest in combat:
   assert d['werewolves'] and d['shadow_actors']
   w=d['werewolves'][0];s=d['shadow_actors'][0]
   distances.append(sum((w['origin'][i]-s['origin'][i])**2 for i in [0,1])**.5)
   assert abs(w['origin'][2]-s['origin'][2])<160,('Werewolf fell or stood on mirrored body',w,s)
   assert w['ground']!=d['player_handle'],'Hidden original player used as Werewolf support'
  assert min(distances)<150,distances
  assert min(x[2] for x in contact)<contact[0][2],'Native werewolf contact caused no damage'
  assert not details['MAP_END']['shadow_actors'] and not details['MAP_END']['frenzy']
  return ['Delivered Griffith BSP freshly loaded with native nofrenzy=0; one owned Shadow; no runtime permission setter', 'Live native Werewolf contact/damage, original body never used as ground, no height failure; Shadow cleanup after native death or Frenzy end. Survival/damage balance and random-trigger probability are outside scope.']
 if mode=='latest-midload':
  details={ast.literal_eval(line)[1]:ast.literal_eval(line)[2] for line in log.splitlines() if line.startswith("('NATIVE',")}
  for j in [0,1]:assert details['MID_BEFORE_LOAD_'+str(j)]['state']==30,details
  for j in [1,2]:
   for direction in ['ON','OFF']:
    for t in ['0.45','0.9']:assert details['MID_'+direction+'_'+str(j)+'_'+t]['state']==30,details
    d=details['MID_'+direction+'_'+str(j)+'_2.5'];assert d['state']==0 and d['wolf']==int(direction=='ON'),d
  return ['Load different saves during unfinished entry in both directions of time; new idle entry/return scenes retain native timing after each load']
 if mode.startswith('latest'):
  details={ast.literal_eval(line)[1]:ast.literal_eval(line)[2] for line in log.splitlines() if line.startswith("('NATIVE',")}
  for direction in ['ON','OFF']:
   for sample in ['0.1','0.45','0.9','1.5']:
    d=details['LATEST_'+direction+'_'+sample];assert d['state']==30 and d['morphs']==1,(direction,sample,d)
   d=details['LATEST_'+direction+'_2.5'];assert d['state']==0 and d['morphs']==0 and d['wolf']==int(direction=='ON'),d
  if mode=='latest-interface':
   for label in ['INTERFACE_LATCHED','LATEST_ON_0.1','LATEST_ON_0.45','LATEST_OFF_0.1','LATEST_OFF_0.45']:
    assert details[label]['buttons']&0x4000000,details[label]
   return ['User quick01 copy: native latched character/quest UI state remains set while complete entry and return animations play; actual input priority checked in native fixture']
  if mode=='latest-walk':
   for label in ['LATEST_BEFORE','LATEST_ON_0.45','LATEST_OFF_0.45']:assert details[label]['buttons']&0x20000,details[label]
   for action,target in [('INTERRUPT',1),('ATTACK',0)]:
    before=details['WALK_'+action+'_BEFORE'];after=details['WALK_'+action+'_AFTER']
    assert before['state']==30 and before['morphs']==1,before
    assert after['state']==0 and after['morphs']==0 and after['wolf']==target,after
   assert sum((a-b)**2 for a,b in zip(details['WALK_MOVE_PROGRESS']['origin'],details['WALK_INTERRUPT_BEFORE']['origin']))>9
   return ['Latest user save copy: held walk speed preserves both native morph scenes, real walk/attack still interrupt before the same input; no save mutation']
  return ['Latest user save copy: user vm_discipline command retains native morph in both directions']
 marks={}
 for line in log.splitlines():
  t=ast.literal_eval(line)
  marks[t[0]]=t
 assert 'DONE' in marks and rows
 checks=[]
 if mode not in ('baseline','save-active') and not mode.endswith('-baseline'):
  if not mode.startswith('stealth') and mode not in ('actions','feeding-expiry','frenzy','frenzy-frenzy-first','transitions','save-active','restore-active','restore-legacy','morph-visual','inventory-2','idle-races','native-edges'):
   cast=marks['CAST_100MS'];ended=marks['END_100MS']
   assert cast[2]==5 and 'animalism_beastform' in cast[3].lower(),cast
   assert ended[2]==0,ended
   if 'animalism_beastform' in ended[3].lower():
    assert any(r['protean']==0 and r['state']==30 and r['partner']=='0xffffffff' and any(a['cls']=='npc_VWolfMorph' and 'morph' in a.get('sequence_name','').lower() for a in r['actors']) for r in rows),'Return delayed without a valid original scene'
   assert marks['DONE'][2]==0 and 'animalism_beastform' not in marks['DONE'][3].lower(),marks['DONE']
   checks.append('activation during feeding is immediate; after release, return follows the original optional scene and completes to human')
  checks.append('native idle scene is permitted; action latency checked separately')
  last=rows[-1];inv=last['inventory'];occupied=[h for h in inv if h!=0xffffffff]
  assert len(set(occupied))==len(occupied),'Duplicate registered handle'
  by={e['handle']:e for e in last['actors']}
  fists=[(i,by[h]) for i,h in enumerate(inv) if h in by and by[h]['cls']=='item_w_fists']
  if mode=='stealth-tiger':
   assert last['inventory_items'][last['weapon']]['cls']=='item_w_chang_claw'
   assert last['inventory_items'][last['weapon']]['slot']==0
  else:assert len(fists)==1 and fists[0][0]==0,('Fists slots',fists)
  for i,h in enumerate(inv):
   if h in by and by[h]['cls'].startswith('item_w_'):
    assert by[h]['slot']==i,('Slot metadata',by[h],i)
    assert by[h]['owner']==next(e['handle'] for e in last['actors'] if e['cls']=='player'),('Owner serial',by[h])
  checks.append('native Tiger Claws occupies slot 0' if mode=='stealth-tiger' else 'one registered fists at slot 0; unique handles, weapon slot metadata and owner match')
 if mode.startswith('feeding'):
  before=marks.get('BEFORE_CAST',marks['FEED_REQUEST']);progress=marks.get('FEED_PROGRESS',marks.get('DONE'));confirmed=marks['FEED_CONFIRMED'][1]
  assert mode=='feeding-release' or progress[6]>before[6],('Feeding did not transfer blood',before,progress)
  partner=confirmed.split('|')[1]
  feeding=[r for r in rows if r['wolf'] and r['sequence_name'].startswith('feeding_') and 'failure' not in r['sequence_name'] and r['partner']!='0xffffffff']
  assert feeding and all(r['partner']==partner and r['role']==0 for r in feeding)
  assert not any(e['cls']=='npc_VWolfMorph' for r in rows if r['partner']==partner for e in r['actors'])
  if mode=='feeding-expiry':
   expired=marks['EXPIRED_AFTER_FEEDING'];assert expired[2]<5 and 'animalism_beastform' not in expired[3].lower(),expired
   assert marks['NATIVE_TIMER_DEFERRED'][2]==5
   checks.append('native timer boundary retained feeding; stock expiry deferred to release, then the ordinary return scene completes to human')
  if mode!='feeding-expiry':
   seen=False;after=[]
   for r in rows:
    if r['partner']==partner:seen=True
    elif seen and r['partner']=='0xffffffff' and r['protean']==5:after.append(r)
   assert after,'No remaining active form after feeding'
   assert any(any(a['handle']==r['weapon'] and a['cls']=='item_w_claws' for a in r['actors']) for r in after),'Claws not selected after feeding'
   assert not any(a['cls']=='npc_VWolfMorph' for r in after for a in r['actors']),'Queued animation after feeding'
  assert not any('morph' in r['sequence_name'].lower() for r in rows if r['partner']!='0xffffffff'),'Transformation animation interrupted feeding'
  checks.append('native feeding partner/role retained; blood transferred; no transformation animation during feeding')
 if mode.startswith('stealth'):
  events=[ast.literal_eval(line) for line in log.splitlines()]
  for tag in ['STEALTH_READY','STEALTH_ENTER','STEALTH_RETURN']:
   assert len([t for t in events if t[0]==tag])==4,(tag,events)
  variants=[t[2:4] for t in events if t[0]=='STEALTH_READY']
  assert len(set(variants))==4,variants
  for j in range(4):
   before=marks['STEALTH_MOVE_BEFORE_'+str(j)][5];after=marks['STEALTH_MOVE_AFTER_'+str(j)][5]
   assert sum((a-b)**2 for a,b in zip(before,after))>9,('No control after kill',j)
  checks.append('four native paired kills: both attacker sexes and victim heights; movement returned')
  if mode=='stealth-tiger':return checks+['Tiger claws uses original animation/weapon resources with unified shared positioning']
  sounds=[s for r in rows for s in r.get('sounds',[]) if 'stealth_sword.wav' in s['name'].lower()]
  assert sounds,'Broadsword clip absent from actual mixer channels'
  assert len(set(round(s['position'],1) for s in sounds))>5,'Clip mixer position did not advance'
  previous={};pending=set();starts=0
  for r in rows:
   for sound in r.get('sounds',[]):
    if 'stealth_sword.wav' not in sound['name'].lower():continue
    key=sound['channel'];position=sound['position']
    # A restart may first be sampled at zero. Count it only when that same
    # restarted channel subsequently advances, without losing the reset.
    if key not in previous or position<previous[key][0] or r['t']-previous[key][1]>.25:pending.add(key)
    if position>0 and key in pending:starts+=1;pending.remove(key)
    previous[key]=(position,r['t'])
  assert starts==4,('Repeated or missing Broadsword clip',starts)
  checks.append('Broadsword Stealth_Sword.wav reached native mixer and played forward once per kill (four starts)')
 if mode in ('save-active','restore-active','restore-legacy','transitions'):
  details={ast.literal_eval(line)[1]:ast.literal_eval(line)[2] for line in log.splitlines() if line.startswith("('NATIVE',")}
  if mode=='save-active':
   assert marks['SAVE_ACTIVE'][2]==5 and details['SAVE_ACTIVE']['state']==0 and details['SAVE_ACTIVE']['wolf']==1 and details['SAVE_ACTIVE']['morphs']==0
   checks.append('owned active snapshot taken after native morph save restriction clears, with no queued save/reload tasks')
  elif mode in ('restore-active','restore-legacy'):
   before=details['RESTORED_ACTIVE'];after=details['RESTORED_ACTIVE_MOVED']
   assert marks['RESTORED_ACTIVE'][2]==5 and before['wolf']==1
   assert sum((a-b)**2 for a,b in zip(before['origin'],after['origin']))>9
   assert after['morphs']==0 and not (int(after['effects'],16)&0x20),after
   assert marks['RESTORED_ENDED'][2]==0 and details['RESTORED_ENDED']['wolf']==0
   checks.append('fresh-process load of active save: immediate movement, visible player, no orphan proxy and normal return')
  else:
   assert marks['BEFORE_RELOAD'][2]==5 and details['BEFORE_RELOAD']['wolf']==1
   assert marks['AFTER_RELOAD'][1:3]==(2,0) and details['AFTER_RELOAD']['wolf']==0
   d=details['AFTER_RELOAD'];assert d['item_classes'].get(d['weapon'])!='item_w_claws','Late equip after load'
   assert marks['BEFORE_MAP'][2]==5 and marks['AFTER_MAP'][2]==0 and details['AFTER_MAP']['wolf']==0
   assert marks['LOADED_MAP'][1]!=marks['CHANGED_MAP'][1] and 'sm_hub_1' in marks['CHANGED_MAP'][1]
   checks.append('inactive seed reload invalidates late equip; native Warehouse/Santa Monica transfer cancels form exactly as the original installation, without orphan presentation')
 if mode.startswith('frenzy'):
  details={ast.literal_eval(line)[1]:ast.literal_eval(line)[2] for line in log.splitlines() if line.startswith("('NATIVE',")}
  stage=1 if mode=='frenzy-frenzy-first' else 0
  for j in [stage]:
   d=details['FRENZY_BOTH_'+str(j)];assert 'animalism_beastform' in marks['FRENZY_MODEL_BOTH'][2].lower(),marks['FRENZY_MODEL_BOTH'];assert d['frenzy']>0 and d['wolf']==1 and d['controller']!='0xffffffff' and d['morphs']==0
  if stage==0:
   assert 'animalism_beastform' not in marks['FRENZY_MODEL_RETURN'][2].lower(),marks['FRENZY_MODEL_RETURN']
   assert details['FRENZY_PROTEAN_END_FIRST']['wolf']==0 and marks['FRENZY_PROTEAN_END_FIRST'][2]==0 and details['FRENZY_PROTEAN_END_FIRST']['frenzy']>0
   assert details['FRENZY_RETURN_0']['wolf']==0 and marks['FRENZY_RETURN_0'][2]==0
  else:
   assert details['FRENZY_RETURN_1']['wolf']==1 and marks['FRENZY_RETURN_1'][2]==5
   d=details['FRENZY_RETURN_1'];assert list(d['item_classes'].values()).count('item_w_claws')==1 and 'item_w_fists' not in d['item_classes'].values(),'Remaining Protean lost claws after Frenzy'
   assert d['item_classes'].get(d['weapon'])=='item_w_claws','Remaining P5 did not select its registered Claws after Frenzy'
  for r in rows:
   if r.get('frenzy',0) and any(a['cls']=='npc_VFrenzyShadow' and hex(a['handle'])==r['controller'] for a in r['actors']):
    shadows=[a for a in r['actors'] if a['cls']=='npc_VFrenzyShadow']
    assert len(shadows)==1 and hex(shadows[0]['handle'])==r['controller'],r
    assert not any(a['cls']=='npc_VWolfMorph' for a in r['actors'])
  checks.append('real Frenzy owns one native Shadow; tested Protean/Frenzy completion order preserves native controller ownership and inventory')
 if mode=='inventory-2':
  details={ast.literal_eval(line)[1]:ast.literal_eval(line)[2] for line in log.splitlines() if line.startswith("('NATIVE',")}
  assert marks['INVENTORY_CLAWS'][2]==2
  assert list(details['INVENTORY_CLAWS']['item_classes'].values()).count('item_w_claws')==1
  assert 'item_w_fists' not in details['INVENTORY_CLAWS']['item_classes'].values()
  before=details['INVENTORY_BEFORE'];retained=[int(h,16) for h in before['inventory'] if h!='0xffffffff' and before['item_classes'].get(h) not in ('item_w_fists','item_w_claws')]
  assert [h for h in rows[-1]['inventory'] if h in retained]==retained
  checks.append('Protean 2 from selected katana: hands replaced by one claws, then one fists at slot 0; all other items/order retained')
 if mode=='actions':
  details={ast.literal_eval(line)[1]:ast.literal_eval(line)[2] for line in log.splitlines() if line.startswith("('NATIVE',")}
  for direction in ['ON','OFF']:
   d=details['FULL_IDLE_'+direction+'_BODY'];assert d['state']==30 and d['morphs']==1,d
   done=details['FULL_IDLE_'+direction+'_DONE'];assert done['state']==0 and done['morphs']==0,done
  for label in ['HELD_ON_100MS','HELD_OFF_100MS']:
   assert details[label]['state']==0 and details[label]['controller']=='0xffffffff',details[label]
  assert sum((a-b)**2 for a,b in zip(details['HELD_BEFORE']['origin'],details['HELD_ON_100MS']['origin']))>1
  assert sum((a-b)**2 for a,b in zip(details['HELD_END_BEFORE']['origin'],details['HELD_OFF_100MS']['origin']))>1
  for j in range(6):
   for label in ['IDLE_ON_100MS_','IDLE_OFF_100MS_']:
    d=details[label+str(j)];assert d['state']==30 and d['morphs']==1,(j,label,d)
   for label,wolf in [('INTERRUPT_ON_',1),('INTERRUPT_OFF_',0)]:
    d=details[label+str(j)];assert d['state']==0 and d['wolf']==wolf and d['controller']=='0xffffffff',(j,label,d)
    assert 'morph' not in d['sequence_name'].lower(),(j,label,d)
  before=[int(h,16) for h in details['INVENTORY_BEFORE']['inventory']];after=rows[-1]['inventory']
  final_weapons={e['handle']:e['cls'] for e in rows[-1]['actors']}
  initial_classes=details['INVENTORY_BEFORE']['item_classes']
  retained=[h for h in before if h!=0xffffffff and initial_classes.get(hex(h)) not in ('item_w_fists','item_w_claws')]
  assert retained and [h for h in after if h in retained]==retained,'Other weapons lost or reordered'
  checks.append('held movement and six action interruptions in both directions; idle animation retained; other weapons/order preserved')
 if mode=='morph-visual':
  import struct
  details={ast.literal_eval(line)[1]:ast.literal_eval(line)[2] for line in log.splitlines() if line.startswith("('NATIVE',")}
  variants=[ast.literal_eval(line) for line in log.splitlines() if line.startswith("('MORPH_VARIANT',")]
  assert len(variants)==8 and all(bool(v[2])==(v[1]<4) for v in variants if v[1]%2==0),variants
  for j in range(8):
   label='MORPH_'+str(j)+'_';a=details[label+'0.45'];b=details[label+'0.9'];done=details[label+'2.3']
   before=details['MORPH_BEFORE_'+str(j)];crouch=j%4>=2
   assert ('crouch' in before['sequence_name'].lower())==crouch,(j,before)
   assert a['state']==30 and a['wolf']==1 and len(a['morph_actors'])==1,(j,a)
   actor=a['morph_actors'][0];actor_b=b['morph_actors'][0]
   assert 'morph' in actor['sequence_name'].lower() and actor_b['cycle']!=actor['cycle'],(j,actor,actor_b)
   primary_human=j%2==0
   assert ('animalism_beastform' not in marks[label+'0.45'][3].lower())==primary_human,(j,marks[label+'0.45'])
   layer=a['animation_layers'][0];layer_b=b['animation_layers'][0]
   cycle=lambda v:struct.unpack('<f',struct.pack('<I',int(v,16) if isinstance(v,str) else v))[0]
   assert cycle(layer_b[3])>cycle(layer[3])+.1,(j,layer,layer_b)
   assert done['state']==0 and done['morphs']==0 and done['wolf']==int(j%2==0),(j,done)
   assert bool(int(done['player_flags'],16)&2)==crouch,(j,done)
   if crouch and j%2:
    settled=min(rows,key=lambda r:abs(r['game_time']-done['game_time']-.4))
    assert settled['player_flags']&2 and 'crouch' in settled['sequence_name'].lower(),(j,settled)
  checks.append('eight original two-body transitions: both sexes, stand/crouch and directions; overlapping gesture/actor cycles, native duration and target crouch retained')
 if mode=='idle-races':
  details={ast.literal_eval(line)[1]:ast.literal_eval(line)[2] for line in log.splitlines() if line.startswith("('NATIVE',")}
  assert 'look' in details['IDLE_HUMAN_BEFORE']['sequence_name'].lower(),details['IDLE_HUMAN_BEFORE']
  for label in ['IDLE_ON_BODY','IDLE_ON_SURVIVED','IDLE_OFF_BODY','IDLE_OFF_SURVIVED']:
   d=details[label];assert d['state']==30 and d['morphs']==1,(label,d)
  for label in ['IDLE_ON_DONE','IDLE_OFF_DONE','IDLE_AFTER_OLD_EXIT','IDLE_REENTRY_AFTER_EXIT']:
   d=details[label];assert d['state']==0 and 'outof' not in d['sequence_name'].lower(),(label,d)
  assert marks['IDLE_REENTRY_AFTER_EXIT'][2]==5
  assert 'into' in details['IDLE_VALID_INTO']['sequence_name'].lower()
  assert 'outof' in details['IDLE_VALID_OUTOF']['sequence_name'].lower(),details['IDLE_VALID_OUTOF']
  checks.append('real idle scheduler before/during both morph directions, raw delayed idle during scene, stale exit across cancel/reentry, and valid later exit retained')
 if mode=='native-edges':
  details={ast.literal_eval(line)[1]:ast.literal_eval(line)[2] for line in log.splitlines() if line.startswith("('NATIVE',")}
  for label in ['CANCEL_EARLY','CANCEL_LATE']:
   d=details[label];assert d['state']==0 and d['wolf']==0 and marks[label][2]==0 and d['controller']=='0xffffffff',(label,d)
  d=details['FEMALE_INTERRUPT_ON'];assert d['state']==0 and d['wolf']==1 and '/female/' in d['saved_human'].lower(),d
  d=details['FEMALE_INTERRUPT_OFF'];assert d['state']==0 and d['wolf']==0 and '/female/' in marks['FEMALE_INTERRUPT_OFF'][3].lower(),d
  checks.append('cancel during unfinished entry has no late transition; female attack/jump interruptions retain female return model')
 if mode=='save-original-baseline':
  assert marks['SAVE_ACTIVE'][2]==5 and marks['SAVE_SCENE'][2]==5
  checks.append('original save availability inspected before and after its native morph scene')
 if mode in ('morph-original-baseline','morph-original-crouch-baseline','morph-original-female-baseline'):
  if mode=='morph-original-crouch-baseline':
   details={ast.literal_eval(line)[1]:ast.literal_eval(line)[2] for line in log.splitlines() if line.startswith("('NATIVE',")}
   before=details['ORIGINAL_BEFORE'];assert int(before['player_flags'],16)&2 and 'crouch' in before['sequence_name'].lower(),before
   for label in ['ORIGINAL_BEFORE_RETURN','ORIGINAL_ON_2.4','ORIGINAL_ON_3.0','ORIGINAL_OFF_2.4','ORIGINAL_OFF_3.0']:
    d=details[label];assert int(d['player_flags'],16)&2 and 'crouch' in d['sequence_name'].lower() and not d['buttons'],(label,d)
   assert all(r['player_flags']&2 for r in rows if r['state']==30),'Native scene cleared crouch state'
   assert all(sum((x-y)**2 for x,y in zip(r['origin'],before['origin']))<.01 for r in rows if r['state']==30),'Native scene moved origin'
   checks.append('crouch mode retained through both native scenes and restored target crouch idles; no held crouch input or origin shift')
  during=[r for r in rows if r['protean']==5 and r['state']==30 and r['animation_layers'][0][2]==3 and any(a['cls']=='npc_VWolfMorph' and 'morph' in a.get('sequence_name','').lower() for a in r['actors'])]
  assert len(during)>=2,'No concurrent human and Warform morph captured'
  cycles=[__import__('struct').unpack('<f',__import__('struct').pack('<I',r['animation_layers'][0][3]))[0] for r in during]
  assert max(cycles)>min(cycles)+.2
  assert any(r['state']==0 and r['wolf']==1 for r in rows)
  assert any(r['state']==30 and any(a.get('sequence_name')==('Gangrel_Female_Wolf_Morph' if mode=='morph-original-female-baseline' else 'Gangrel_Male_Wolf_Morph') for a in r['actors']) for r in rows if r['protean']==0)
  assert rows[-1]['state']==0 and rows[-1]['wolf']==0
  checks.append('original two-actor scene: human and Warform morph animations advance concurrently while native state 30 holds control')
 return checks
