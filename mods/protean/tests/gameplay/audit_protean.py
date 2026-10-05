"""Independent audit of retained exact-byte Protean observations."""
import ast,json,sys,hashlib
from pathlib import Path
root=Path(sys.argv[1]);plugin=Path(sys.argv[2]);digest=hashlib.sha256(plugin.read_bytes()).hexdigest().upper()
def load(label):
 s=root/label;l=json.loads((s/'launch.json').read_text(encoding='utf-8-sig'))
 assert l['SaveHash']=='9DED42B42404270F13D945575F1D4B37EE2354BB95992AAF006957280E1BCC36'
 assert any(x['Path'].endswith('protean-improved.vtm') and x['Hash']==digest for x in l['Candidates'])
 assert json.loads((s/'preserved.json').read_text(encoding='utf-8-sig'))['Result']=='PASS'
 return s,[json.loads(x) for x in (s/'actors.jsonl').read_text().splitlines()]
def player(r):return next(a for a in r['actors'] if a['class']=='player')
def shadows(r):return [a for a in r['actors'] if a['class']=='npc_VFrenzyShadow']
def row(rows,label):return next(r for r in rows if r['label']==label)
s,rows=load('protean_enemy_gate');first=json.loads((s/'runner-result.json').read_text());assert first['completed']==['repeat_one_shadow','protean_ends_first'] and not first['passed']
f=row(rows,'frenzy');repeat=row(rows,'repeat');assert len(shadows(f))==len(shadows(repeat))==1 and shadows(f)[0]['handle']==shadows(repeat)[0]['handle']==player(f)['controller']==player(repeat)['controller']
assert player(f)['wolf']==player(repeat)['wolf']==1 and player(f)['frenzy']>0 and 0<player(repeat)['frenzy']<=player(f)['frenzy']
a=[ast.literal_eval(x) for x in (s/'probe.txt').read_text().splitlines()];a={k:next(v[2]['player'] for v in a if v[1]==k) for k in ('frenzy','repeat')}
for k in ('strength','stamina','wits','Close_Combat_Brawl'):assert a['frenzy'][k]==a['repeat'][k]
end=row(rows,'end');assert player(end)['wolf']==0 and player(end)['frenzy']>0 and len(shadows(end))==1 and player(end)['model']==shadows(end)[0]['model']
wait=[r for r in rows if r['label']=='protean_first_wait'];assert not player(wait[-1])['frenzy'] and not shadows(wait[-1])
s,rows=load('protean_remaining');assert json.loads((s/'runner-result.json').read_text())['passed']
wait=[r for r in rows if r['label']=='frenzy_first_wait'];assert player(wait[-1])['wolf']==1 and not player(wait[-1])['frenzy'] and not shadows(wait[-1])
for label in ('loaded_active','map'):
 r=row(rows,label);assert not player(r)['frenzy'] and not shadows(r)
assert player(row(rows,'loaded_active'))['wolf']==0 and player(row(rows,'map'))['wolf']==1
s,rows=load('protean_filter_cvars');assert json.loads((s/'runner-result.json').read_text())['passed']
filters=[json.loads(x) for x in (s/'filter.jsonl').read_text().splitlines()];by={r['label']:r for r in filters};initial=by['protean_filter_initial']
for label in ('protean_filter_initial','protean_filter_reload_0','protean_filter_reload_1'):
 r=by[label];assert player(r)['protean']==4 and r['native_cvars']['mat_fullbright']==1 and abs(r['brightness']-initial['brightness'])<5
assert by['protean_filter_off']['native_cvars']['mat_fullbright']==0 and player(by['protean_filter_off'])['protean']==0
for label in ('redvision_initial','redvision_reload'):assert by[label]['native_cvars']['feedvision']==10 and by[label]['native_cvars']['mat_fullbright']==0
assert abs(by['redvision_reload']['brightness']-by['redvision_initial']['brightness'])<5
report=dict(result='PASS',hash=digest,workflows=['P5 Frenzy','repeat one Shadow/no observed bonus growth','Protean ends first','Frenzy ends first','load nominated clean save during active states','map transfer during active states','P4 saved-active filter two reloads/off','separate native feedvision/RedVision overlay'],first_failures_preserved=True,limitations=['Earlier preparation failures excluded','Additional saved-both request did not create a confirmed file/reload; no certificate for saving both states. Approved active-load workflow uses the nominated archival save and passed.'],cvar_semantics='client 619928 is mat_fullbright ConVar; +2c is its integer value and vfunc +4 is IsCommand, not filter enabled/type',filter_brightness={r['label']:r['brightness'] for r in filters})
(root/'protean-gameplay-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
