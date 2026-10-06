"""Task-owned diagnostic session; stock comparison disables only History."""
import json,sys,os,shutil,traceback
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from infra.core import read_json,atomic_json,digest,catalog,run
from infra.session import Transaction
from infra.gameplay import windows,preserve_session
import argparse
ap=argparse.ArgumentParser()
ap.add_argument('--config',required=True);ap.add_argument('--mode',choices=['baseline','stock','candidate'],required=True)
ap.add_argument('--candidate');ap.add_argument('--full',action='store_true');opts=ap.parse_args()
config=read_json(opts.config);game=Path(config['game_root'])
mode=opts.mode;
if mode=='candidate':
    if not opts.candidate:ap.error('--candidate is required')
    from infra.native import exact
    exact('history',config,opts.candidate)
import tempfile
with tempfile.TemporaryDirectory(prefix='vtmb-history-preflight-') as preflight:
    windows(config,'Inspect',Path(preflight))
    if read_json(Path(preflight)/'settings-current.json')['Processes']:
        raise RuntimeError('User game is running; no installation transaction started')
t=Transaction(game,config['state_root']);folder=t.start()
print('SESSION',str(folder),flush=True)
try:
    windows(config,'Inspect',folder);settings=read_json(folder/'settings-current.json')
    if settings['Processes']:raise RuntimeError('User game is running')
    atomic_json(folder/'settings.json',settings);t.watch_inventory()
    for directory in ['Bin/loader','Unofficial_Patch/cfg','Vampire/cfg','Unofficial_Patch/save','Vampire/save','Unofficial_Patch/python','Vampire/python','Unofficial_Patch/resource']:
        for p in (game/directory).rglob('*'):
            if p.is_file():t.preserve(p.relative_to(game).as_posix())
    for relative in catalog()['native_modules']:t.preserve(relative)
    for directory in ['', 'Unofficial_Patch','Vampire']:
        for p in (game/directory).glob('*'):
            if p.is_file() and p.suffix.lower() in ['.cfg','.log','.txt','.exe','.inf']:t.preserve(p.relative_to(game).as_posix())
    for directory in ['Unofficial_Patch/python','Vampire/python']:
        for p in (game/directory).rglob('*.py'):
            for ext in ['.pyc','.pyo']:t.allow_runtime(p.with_suffix(ext).relative_to(game).as_posix())
    for p in (game/'Unofficial_Patch/cfg').glob('*.cfg'):t.allow_runtime(p.relative_to(game).as_posix())
    if opts.full:
        for extension in ['HL1','HL2','HL3']:
            t.allow_runtime('Unofficial_Patch/save/sp_genesisdevice_1.'+extension)
    plugin='Bin/loader/history-stat-reset-fix.vtm';t.preserve(plugin)
    if mode=='stock':
        # Rename within the transaction rather than touch any other plugin.
        original=(game/plugin).read_bytes()
        t.write('Bin/loader/history-stat-reset-fix.disabled',original)
        # A zero-byte .vtm aborts this loader. Record removal before disabling
        # the preserved file; the live restoration seal owns this exact change.
        t.allow_runtime(plugin)
        (game/plugin).unlink()
    elif mode=='candidate':t.write(plugin,Path(opts.candidate).read_bytes())
    args=['-game','Unofficial_Patch','-dev','-novid','-console','+developer','0']
    phash=digest(game/plugin) if (game/plugin).exists() else None
    atomic_json(folder/'identity.json',{'mode':mode,'modules':{n:digest(game/n) for n in catalog()['native_modules']},'plugin':phash})
    atomic_json(folder/'launch.json',{'Arguments':args,'Candidates':[{'Path':str(game/plugin),'Hash':phash}] if phash else []})
    t.launch_intent(game/'Vampire.exe',args);windows(config,'Launch',folder,folder/'launch.json')
    owned=read_json(folder/'process.json');t.owned_process(owned['Id'],owned['Ticks'])
    command=[sys.executable,'-B',Path(__file__).with_name('history_auto_spend.py'),folder]
    if opts.full:command.append('full')
    print(run(command,timeout=600,
        env={'PYTHONPATH':str(root)+os.pathsep+config['dependencies']},process_tree=True),flush=True)
finally:
    preserve_session(t,config,folder)
    print('RESTORED',str(folder),flush=True)
