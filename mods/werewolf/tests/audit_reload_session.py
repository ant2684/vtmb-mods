"""Portable read-only audit of retained external clean-gameplay evidence.

No logs/saves are bundled. Supply the local session and, before permanent
installation, game-root to independently verify rollback membership and bytes.
The bounded local launcher remains in the original source capsule; this audit
does not fabricate a missing gameplay scenario or certify manual acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path

IDENTITIES = {
    'Bin/loader/griffith-wolf-native-damage.vtm': '627c90962aaa49ee229f1e05c397a7dc2718f2dfd11418292309900041433f01',
    'Unofficial_Patch/python/griffith/griffith.py': '866b57f095fe6b10f039d79574965b66c858d846d51cd4ddf957ea711be4ed2e',
}

def check(ok, message):
    if not ok:
        raise ValueError(message)

def verify(session, game=None):
    result = json.loads((session/'result.json').read_text())
    check(result.get('complete') and result.get('restored'), 'Incomplete scenario or rollback')
    check(result.get('candidate') == IDENTITIES and not result.get('temporary_python_trace'), 'Not the exact clean candidate')
    launch = json.loads((session/'launch.json').read_text())['command']
    check('-condebug' not in launch and '-novid' in launch and '+load' in launch, 'Unexpected launch')
    check(not set(launch) & {'-window','-windowed','-sw','-fullscreen','-full','-w','-width','-h','-height'}, 'Video overrides')
    commands = [json.loads(x) for x in (session/'commands.jsonl').read_text().splitlines()]
    check(not any('nativeWolfRegenRestore' in x['command'] for x in commands), 'Manual restoration is not acceptance')
    if 'initial_healing' in result:
        for key in ['initial_healing','reload_healing','disabled_timer_healing','consecutive_healing','unpaused_healing']:
            window=result[key]; hp=window['hp']; clock=window['game_clock']
            changes=[(hp[i]-hp[i-1],clock[i]) for i in range(1,len(hp)) if hp[i]!=hp[i-1]]
            check(window['healed']>0 and changes, 'No automatic healing: '+key)
            check(all(0 < n <= 50 for n,t in changes), 'Duplicate/oversized tick: '+key)
            check(all(.7 <= changes[i][1]-changes[i-1][1] <= 1.3 for i in range(1,len(changes))), 'Unexpected observed cadence: '+key)
            check(max(hp)<=900, 'Maximum exceeded')
        check(result.get('pause_preserved') and result.get('completed_flag_control'), 'Missing pause/completed controls')
        scope='automatic reload, disabled timer, consecutive reloads, pause; direct wound/completed flag are diagnostic controls'
    elif result.get('real_combat_death'):
        check(result.get('temporary_zero_regen_for_real_death') and result.get('combat_acceptance'), 'Unqualified real-death control')
        check(result['completed_flags']['Werewolf_Dead'] and result['completed_flags']['GP_Wolf_Rewarded'], 'Missing real completion/reward')
        scope='real claws and combat death at temporary zero regeneration; final settings restored'
    elif result.get('real_completed_loaded'):
        check(result['completed_flags']['Werewolf_Dead'] and result['completed_flags']['GP_Wolf_Rewarded'], 'Not a completed battle')
        scope='real completed-battle save loaded with normal50HP settings; no revival'
    else:
        check(result.get('combat_acceptance') and result['real_claw_hit']['current_attributes']['hp']<900, 'No real claw hit')
        check(result['claw_healing']['healed']>0, 'No healing after claws')
        for name in ['AttributesBase[ v_attribute_strength','AbilitiesBase[ v_ability_brawl','DisciplinesBase[ v_discipline_protean','ActiveDisciplinesCurrent[ v_discipline_protean']:
            check([v for k,v in result['build'].items() if 'm_iV'+name in k]==[5], 'Wrong combat build')
        check(not any('TakeDamage' in x['command'] for x in commands), 'Script damage is not a claw test')
        scope='real Brawl5/baseStrength5/activeProtean5 claws and healing'
    if game:
        trees={'save':'Unofficial_Patch/save','cfg':'Unofficial_Patch/cfg','vampire-cfg':'Vampire/cfg','python':'Unofficial_Patch/python','graphs':'Unofficial_Patch/maps/graphs'}
        manifests=json.loads((session/'manifests.json').read_text())
        for name,relative in trees.items():
            root=game/relative
            check({str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}==set(manifests[name]), 'Tree membership changed: '+name)
            for rel,state in manifests[name].items():
                path=root/rel
                check(hashlib.sha256(path.read_bytes()).hexdigest()==state['sha256'] and path.stat().st_mtime_ns==state['mtime_ns'], 'Original changed: '+str(path))
        for rel,state in json.loads((session/'protected.json').read_text()).items():
            path=game/rel
            check(hashlib.sha256(path.read_bytes()).hexdigest()==state['sha'] and path.stat().st_mtime_ns==state['mtime'], 'Protected resource changed: '+rel)
    return {'result':'PASS','scope':scope,'full_manual_acceptance':False,'exact_clean_identities':IDENTITIES}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('session',type=Path);parser.add_argument('--game-root',type=Path)
    args=parser.parse_args();print(json.dumps(verify(args.session,args.game_root),indent=2))
