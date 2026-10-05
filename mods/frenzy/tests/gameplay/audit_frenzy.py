"""Audit actual native approach/hit evidence, preserving all first failures."""
import ast,json,hashlib,math,sys
from pathlib import Path
root=Path(sys.argv[1]);plugin=Path(sys.argv[2]);digest=hashlib.sha256(plugin.read_bytes()).hexdigest().upper()
def load(label):
 s=root/label;launch=json.loads((s/'launch.json').read_text(encoding='utf-8-sig'))
 assert launch['SaveHash']=='13452B2FBB1757630A0735216761DC41FF42464F53BBEE87809DE87BFFBF45CC'
 assert any(x['Path'].endswith('griffith-frenzy-werewolf-fix.vtm') and x['Hash']==digest for x in launch['Candidates'])
 assert json.loads((s/'preserved.json').read_text(encoding='utf-8-sig'))['Result']=='PASS'
 return s,[json.loads(x) for x in (s/'actors.jsonl').read_text().splitlines()]
def player(r):return next(a for a in r['actors'] if a['class']=='player')
def wolf(r):return next(a for a in r['actors'] if a['name']=='werewolf')
def shadow(r):return [a for a in r['actors'] if a['class']=='npc_VFrenzyShadow']
contacts=[]
for label,warform in [('gp_ordinary_hits',False),('gp_warform',True)]:
 s,rows=load(label);initial=next(r for r in rows if r['label']=='gp_before_frenzy');native=wolf(initial)
 assert native['vtable']==0x4cf4d4 and native['life']==0 and native['alive']==native['targetable']==1 and native['health']>0
 assert 1<=native['solid']<=6 and not native['effects']&0x20 and not native['spawn_flags']&0x8000 and not native['think_disabled']
 # Native end clears the counter/controller before deleting the Shadow;
 # retain transitional rows, certify the positive-counter combat interval.
 combat=[r for r in rows if r['label']=='gp_contact' and shadow(r) and player(r)['life']==0 and player(r)['frenzy']>0]
 assert combat and all(player(r)['frenzy']>0 and len(shadow(r))==1 and shadow(r)[0]['handle']==player(r)['controller'] and shadow(r)[0]['enemy']==wolf(r)['handle'] for r in combat)
 assert all(bool(player(r)['wolf'])==warform for r in combat)
 assert all(r['SetOrigin']==0x2af9 and wolf(r)['ground']!=player(r)['handle'] for r in combat)
 closest=min(math.dist(wolf(r)['origin'][:2],shadow(r)[0]['origin'][:2]) for r in combat)
 start=math.dist(wolf(initial)['origin'][:2],player(initial)['origin'][:2]);assert closest<160 and start-closest>10
 close=[r for r in combat if math.dist(wolf(r)['origin'][:2],shadow(r)[0]['origin'][:2])<160]
 assert all(abs(wolf(r)['origin'][2]-shadow(r)[0]['origin'][2])<20 for r in close)
 ticks=[ast.literal_eval(x) for x in (s/'probe.txt').read_text().splitlines() if "'gp_health_tick'" in x]
 assert ticks and any(t[2]['player']['health']<ticks[0][2]['player']['health'] for t in ticks[1:])
 assert all(t[2]['shadow'] for t in ticks if t[2]['player']['health']>0)
 contacts.append(dict(session=label,mode='Protean5' if warform else 'ordinary',start_xy=start,closest_xy=closest,health_before=ticks[0][2]['player']['health'],health_min=min(t[2]['player']['health'] for t in ticks),SetOrigin_stock=True,no_original_player_support=True,first_runner=json.loads((s/'runner-result.json').read_text())))
s,rows=load('gp_context');first=json.loads((s/'runner-result.json').read_text());assert first['completed']==['gp_alive_end_clear','gp_active_load_clear'] and not first['passed']
ended=next(r for r in rows if r['label']=='gp_alive_frenzy_end' and not player(r)['frenzy']);assert not player(ended)['life'] and not shadow(ended)
for session_name,before,after in [('gp_context','before_active_load','after_active_load'),('gp_map_context','before_active_map','gp_map')]:
 s,rows=load(session_name)
 if session_name=='gp_map_context':assert json.loads((s/'runner-result.json').read_text())['passed']
 b=next(r for r in rows if r['label']==before);a=next(r for r in rows if r['label']==after)
 assert player(b)['frenzy']>0 and len(shadow(b))==1 and not player(a)['frenzy'] and not shadow(a) and not player(a)['life']
report=dict(result='PASS',hash=digest,contact_evidence=contacts,active_context_end_load_map=True,scope='Native stock live Werewolf; actual approach into retained <160 XY correction scope and native damaging attacks during owned Shadow state. No literal hull-overlap claim.',first_failures_preserved=True,limitations=['Raw first runners retain their geometry/late-load failures; audit uses native hit plus measured relative approach, not an arbitrary AABB-overlap threshold','Ordinary contact ended in player death; separate context session verifies living native completion/load/map'])
(root/'frenzy-gameplay-verification.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS exact-byte Frenzy native contact and context audit')
