"""Run retained final scenarios using clean plugins and external observations.

Requires a fresh CleanSession snapshot/owned launch and preserved audio assets.
Never rebuilds, injects code, changes video mode or launches/stops the game.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--session', required=True)
    ap.add_argument('--radio-tests', required=True)
    ap.add_argument('--background-tests', required=True)
    ap.add_argument('--assets', required=True)
    ap.add_argument('--audio-helper', required=True)
    ap.add_argument('--radio-plugin', required=True)
    ap.add_argument('--background-plugin', required=True)
    ap.add_argument('--mode', choices=['radio', 'background'], required=True)
    ap.add_argument('--background-prefix', default='clean_')
    a = ap.parse_args()
    session, tests, bg = Path(a.session), Path(a.radio_tests), Path(a.background_tests)
    game = Path('LOCAL_GAME_ROOT_REQUIRED')
    launch = json.loads((session/'launch.json').read_text(encoding='utf-8-sig'))
    assert sha(a.radio_plugin) == launch['PluginHash'] == sha(game/'Bin/loader/subtitle-pause-fix.vtm')
    assert sha(a.background_plugin) == launch['BackgroundHash'] == sha(game/'Bin/loader/cutscene-subtitle-background-fix.vtm')
    def no_logs():
        for name in ['subtitle-pause-plugin.log', 'cutscene-subtitle-background-fix.log']:
            assert not (game/name).exists(), ('plugin generated log', name)
    no_logs()
    env = os.environ.copy()
    env['VTMB_AUDIO_HELPER'] = str(Path(a.audio_helper).resolve())
    def run(script, *args):
        command = [sys.executable, str(script), *map(str,args)]
        child = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        with (session/'external-regression-output.txt').open('a', encoding='utf-8') as output:
            for line in child.stdout:
                output.write(line); output.flush(); print(line.rstrip(), flush=True)
        assert child.wait() == 0, command
        no_logs()
    if a.mode == 'radio':
        run(tests/'baseline.py',session,'radio_tv','radio_tv_final')
        run(tests/'baseline.py',session,'radio_wait','radio_wait_final')
        run(tests/'controls.py',session,'controls_bound')
        run(tests/'loop_final.py',session)
        run(tests/'audit_evidence.py','--session',session,'--assets',a.assets,'--plugin',a.radio_plugin,'--output',session/'radio-gameplay.json')
    else:
        prefix=a.background_prefix
        assert prefix.replace('_','').isalnum()
        run(bg/'drive.py',session,'--command','developer 0','--seconds',0,'--label',prefix+'quiet')
        # The same previously confirmed direct scenes, through the engine's
        # normal map/trigger commands. The driver operates only the owned PID.
        run(bg/'drive.py',session,'--command','map sp_endsequences_a','--seconds',12,'--label',prefix+'scene_a_ready')
        run(bg/'drive.py',session,'--command','ent_fire Start_Give_Prince_Key Trigger','--seconds',24,'--label',prefix+'scene_a')
        run(bg/'drive.py',session,'--command','map sp_endsequences_b','--seconds',12,'--label',prefix+'scene_b_ready')
        run(bg/'drive.py',session,'--command','ent_fire Start_Camarilla_Part_1 Trigger','--seconds',28,'--label',prefix+'scene_b')
        scenes = []
        for name in ['scene_a','scene_b']:
            rows = [json.loads(line) for line in (session/(prefix+name)/'observations.jsonl').read_text().splitlines()]
            assert rows and all(r['background_branch'] == 'e9bf00000090' for r in rows)
            active = [r for r in rows if r['cinematic_fade'] > 0]
            assert len(active) >= 5, ('cinematic context not confirmed', name)
            assert any(r.get('chat_lines') for r in active), ('caption panel missing', name)
            texts = sorted({r['last_caption'] for r in active if r.get('last_caption')})
            assert texts, ('visible caption text missing', name)
            scenes.append({'scene':name,'frames':len(rows),'cinematic_frames':len(active),'texts':texts})
        run(bg/'drive.py',session,'--command','load autosave','--seconds',12,'--label',prefix+'returned_autosave')
        assert all(r['background_branch'] == 'e9bf00000090' for r in [json.loads(line) for line in (session/(prefix+'returned_autosave')/'observations.jsonl').read_text().splitlines()])
        (session/'background-gameplay.json').write_text(json.dumps({'result':'PASS','binary_sha256':sha(a.background_plugin),'scenes':scenes,'scope':'two native cinematic contexts, caption panel/text, unchanged branch on save return; images retained'}, indent=2))
    no_logs()
    print('PASS clean exact-binary',a.mode,'regression, with no plugin logs',flush=True)

if __name__ == '__main__':
    main()
