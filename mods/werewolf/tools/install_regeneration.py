"""Guarded local installation/rollback; no game launch, template edit or ZIP work."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'resources'))
from build_regeneration import (build_map, build_script, MAP_PIN, SCRIPT_PIN,
                               PREVIOUS_MAP_PIN, PREVIOUS_SCRIPT_PIN, CURRENT_MAP_PIN, CURRENT_SCRIPT_PIN,
                               LIFE_MAP_PIN, LIFE_SCRIPT_PIN)
from verify_regeneration import verify, VTM, INI, MAP, SCRIPT

OLD_VTM = '4f1dc7b0244049593adeb19cada3e7367d4a80ed9d9450d0f544ee9ac241b64c'
OLD_REGEN_VTM = '785380fe615b7ab0641bf9f2b210fa35f1a9d8e6fc91869f39cc23f35960b6aa'
LIFE_VTM = '1a2b67cdcb7ca12d92b6c09cf81efb6b4c48518111216de4853636c39e336cc6'
REGEN_VTM = '627c90962aaa49ee229f1e05c397a7dc2718f2dfd11418292309900041433f01'
CACHE = 'Unofficial_Patch/python/griffith/griffith.pyc'
GRAPH = 'Unofficial_Patch/maps/graphs/sp_observatory_2.ain'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def idle():
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
        "@(Get-CimInstance Win32_Process -Filter \"Name='Vampire.exe'\").Count"], capture_output=True, text=True, check=True)
    if result.stdout.strip() != '0':
        raise RuntimeError('Game is running: installation/rollback refused; no process stopped')

def safe(game, name):
    path = (game / name).resolve()
    path.relative_to(game)
    return path

def record(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf8')

def snapshot(path):
    if not path.exists(): return {'exists': False}
    st = path.stat()
    return {'exists': True, 'sha256': sha(path), 'atime_ns': st.st_atime_ns, 'mtime_ns': st.st_mtime_ns}

def matches(path, state):
    current = snapshot(path)
    # Reading can affect access times on some volumes; don't call it a user edit.
    return {k:v for k,v in current.items() if k != 'atime_ns'} == {k:v for k,v in state.items() if k != 'atime_ns'}

def restore(game, backup, originals):
    for name, state in originals.items():
        path = safe(game, name)
        if state['exists']:
            source = backup / 'originals' / name
            if sha(source) != state['sha256']: raise RuntimeError('Changed backup: ' + name)
            shutil.copy2(source, path)
            os.utime(path, ns=(state['atime_ns'], state['mtime_ns']))
        elif path.exists():
            path.unlink()

def install(game, plugin, output):
    idle()
    game, output = game.resolve(), output.resolve()
    if output.exists(): raise FileExistsError('Occupied stage')
    identity = tuple(sha(safe(game, name)) for name in (VTM, MAP, SCRIPT))
    if identity not in ((OLD_VTM, MAP_PIN, SCRIPT_PIN),
                        (OLD_REGEN_VTM, PREVIOUS_MAP_PIN, PREVIOUS_SCRIPT_PIN),
                        (OLD_REGEN_VTM, CURRENT_MAP_PIN, CURRENT_SCRIPT_PIN),
                        (LIFE_VTM, LIFE_MAP_PIN, LIFE_SCRIPT_PIN)):
        raise RuntimeError('Unexpected existing Wolf resource set; no replacement')
    if sha(plugin) != REGEN_VTM:
        raise RuntimeError('Unqualified native candidate')
    protected = {}
    for folder in ['Unofficial_Patch/SAVE', 'Unofficial_Patch/cfg', 'Bin/loader', 'Vampire/dlls']:
        for path in (game / folder).rglob('*'):
            if path.is_file() and path.relative_to(game).as_posix() not in [VTM, INI]:
                protected[path.relative_to(game).as_posix()] = snapshot(path)
    template = 'Unofficial_Patch/vdata/system/npctemplate001.txt'
    protected[template] = snapshot(safe(game, template))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = game / 'Mod_Backups' / ('Griffith_Wolf_Regeneration_' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    names = [VTM, INI, MAP, SCRIPT, CACHE, GRAPH]
    originals = {name: snapshot(safe(game, name)) for name in names}
    for name, state in originals.items():
        if state['exists']:
            destination = backup / 'originals' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(safe(game, name), destination)
            if sha(destination) != state['sha256']: raise RuntimeError('Backup verification failed')
    output.mkdir(parents=True)
    for name, builder in [(MAP, build_map), (SCRIPT, build_script)]:
        path = output / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(builder((backup / 'originals' / name).read_bytes()))
    mod = Path(__file__).resolve().parents[1]
    ini_source = backup / 'originals' / INI if originals[INI]['exists'] else mod / 'docs/griffith-wolf-native-damage.ini'
    for source, name in [(plugin, VTM), (ini_source, INI),
                         (mod / 'docs/manual_regeneration_README.txt', 'README.txt')]:
        path = output / name; path.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, path)
    identities = verify(output, backup / 'originals')
    changes = [name for name in [VTM, INI, MAP, SCRIPT]
               if not originals[name]['exists'] or originals[name]['sha256'] != identities[name]]
    receipt = {'game': str(game), 'stage': str(output), 'status': 'backed-up',
               'originals': originals, 'after': identities, 'protected': protected}
    receipt_path = backup / 'receipt.json'; record(receipt_path, receipt)
    for name in [VTM, INI, MAP, SCRIPT]:
        if safe(game, name).with_name(safe(game, name).name + '.wolf_regen_new').exists():
            raise FileExistsError('Occupied installation temporary path')
    written = []; cache_changed = graph_changed = False
    try:
        idle()
        for name, state in originals.items():
            if not matches(safe(game, name), state): raise RuntimeError('Concurrent modification: ' + name)
        for name in changes:
            path = safe(game, name); temporary = path.with_name(path.name + '.wolf_regen_new')
            shutil.copy2(output / name, temporary)
            if sha(temporary) != identities[name]: raise RuntimeError('Copy mismatch')
            os.replace(temporary, path); written.append(name)
            if sha(path) != identities[name]: raise RuntimeError('Installed mismatch')
        if originals[CACHE]['exists']:
            safe(game, CACHE).unlink(); cache_changed = True
        if MAP in changes and originals[GRAPH]['exists']:
            graph = safe(game, GRAPH)
            os.utime(graph, ns=(originals[GRAPH]['atime_ns'], max(originals[GRAPH]['mtime_ns'], safe(game, MAP).stat().st_mtime_ns + 1000000000)))
            graph_changed = True
        for name, state in protected.items():
            if not matches(safe(game, name), state): raise RuntimeError('Protected user file changed: ' + name)
        receipt['installed_state'] = {name: snapshot(safe(game, name)) for name in names}
        receipt['status'] = 'installed'; record(receipt_path, receipt)
    except Exception:
        # Only own successful replacements/cache/graph changes; don't undo a raced user edit.
        recover = {}
        for name in written:
            if safe(game, name).exists() and sha(safe(game, name)) == identities[name]: recover[name] = originals[name]
        if cache_changed and not safe(game, CACHE).exists(): recover[CACHE] = originals[CACHE]
        if graph_changed and sha(safe(game, GRAPH)) == originals[GRAPH]['sha256']: recover[GRAPH] = originals[GRAPH]
        restore(game, backup, recover)
        for name in [VTM, INI, MAP, SCRIPT]:
            path = safe(game, name).with_name(safe(game, name).name + '.wolf_regen_new')
            # Preflight refused existing paths. Delete only our exact verified
            # candidate copies, never an unexpected/raced temporary file.
            if path.exists() and sha(path) == identities[name]: path.unlink()
        receipt['status'] = 'failed-restored-owned-files'; record(receipt_path, receipt)
        raise
    print(json.dumps({'backup': str(backup), 'installed': identities, 'protected_count': len(protected)}, indent=2))

def rollback(backup):
    receipt_path = backup / 'receipt.json'; receipt = json.loads(receipt_path.read_text())
    game = Path(receipt['game']).resolve()
    if backup.resolve().parent != game / 'Mod_Backups' or receipt['status'] != 'installed':
        raise ValueError('Unrecognized active rollback receipt')
    idle()
    for name, state in receipt['installed_state'].items():
        if not matches(safe(game, name), state): raise RuntimeError('Later user change; rollback refused: ' + name)
    restore(game, backup, receipt['originals'])
    receipt['status'] = 'rolled-back'; record(receipt_path, receipt)
    print('PASS complete guarded rollback')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-root', type=Path)
    parser.add_argument('--plugin', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    if args.rollback: rollback(args.rollback)
    elif args.game_root and args.plugin and args.output: install(args.game_root, args.plugin, args.output)
    else: parser.error('Provide game-root/plugin/output or rollback')
