"""Explicit recovery refuses uncertain process ownership or unknown changes."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from infra.core import ROOT, read_json, run, need
from infra.session import Transaction


def settings_restore_allowed(folder,current,registry_base='Software\\Troika\\Vampire'):
    """A historical owned PID does not own later personal settings."""
    from infra.core import Blocked
    original=read_json(folder/'settings.json')
    unchanged=all(current[k]==original[k] for k in ['Video','Shortcuts'])
    snapshot=folder/'settings-after-stop.json'
    frozen=read_json(snapshot) if snapshot.exists() else None
    matches=frozen is not None and all(current[k]==frozen[k] for k in ['Video','Shortcuts'])
    if unchanged or matches:return
    intents=folder/'settings-intents.jsonl'
    if frozen is None or not intents.exists():raise Blocked('Settings changed without a matching after-stop snapshot/intents; preserve newer user values and reconcile explicitly before recovery')
    import json
    records=[json.loads(line) for line in intents.read_text(encoding='utf-8-sig').splitlines() if line]
    missing={'@missing':True}
    def fields(snapshot):
        out={}
        for sub in snapshot['Video']:
            out[('key',sub['Sub'])]=sub['Exists']
            for value in sub['Values']:out[('value',sub['Sub'],value['Name'])]=value
        for link in snapshot['Shortcuts']:
            out[('shortcut',link['Path'])]=link
        return out
    before,after,now=map(fields,[original,frozen,current])
    for key in before.keys()|after.keys()|now.keys():
        a,b,c=before.get(key,missing),after.get(key,missing),now.get(key,missing)
        if c==b or c==a==b:continue
        if c!=a:raise Blocked('Unknown later setting change retained: '+str(key))
        if key[0]=='shortcut':
            operation='RestoreShortcut';target=key[1];value=a
        else:
            target='HKCU:\\'+registry_base+'\\'+key[1]
            if key[0]=='key':operation='CreateOriginalKey' if a is True else 'DeleteNewKey';value=None
            else:
                target+='\\'+key[2];operation='DeleteNewValue' if a==missing else 'RestoreOriginalValue';value=None if a==missing else a
        if not any(r.get('Operation')==operation and r.get('Target')==target and r.get('Value')==value for r in records):
            raise Blocked('Partial restoration lacks a matching write-ahead intent: '+str(key))


def recover(config):
    transaction=Transaction(need(config,'game_root'),need(config,'state_root'))
    from infra.core import require
    require(transaction.data is not None and transaction.data['game_root']==str(transaction.game),'Recovery journal missing or belongs to another installation; refuse process control')
    if transaction.data and transaction.data['state']=='RESTORED':
        return transaction.restore()
    transaction.acquire_installation()
    folder=transaction.state/transaction.data['id']
    if transaction.data['owned_process']:
        from infra.gameplay import verify_process_record
        verify_process_record(transaction,folder)
        run([config.get('powershell','pwsh'),'-NoProfile','-File',ROOT/'infra/windows.ps1','-Action','Stop','-GameRoot',config['game_root'],'-LaunchUser',need(config,'launch_user'),'-InputFile',folder/'process.json'])
    from infra.gameplay import windows
    windows(config,'Inspect',folder)
    if read_json(folder/'settings-current.json')['Processes']:
        from infra.core import Blocked
        raise Blocked('User game is running; recovery leaves files/settings untouched until its owner closes it')
    if (folder/'settings.json').exists():settings_restore_allowed(folder,read_json(folder/'settings-current.json'))
    result=transaction.restore(process_stopped=True,finalize=False)
    if (folder/'settings.json').exists():
        import shutil
        archive=folder/'after-tests/settings-before-restoration.json';archive.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(folder/'settings-current.json',archive)
        run([config.get('powershell','pwsh'),'-NoProfile','-File',ROOT/'infra/windows.ps1','-Action','RestoreSettings','-GameRoot',config['game_root'],'-LaunchUser',need(config,'launch_user'),'-InputFile',folder/'settings.json'])
        from infra.gameplay import windows
        windows(config,'Inspect',folder)
        original=read_json(folder/'settings.json');current=read_json(folder/'settings-current.json')
        from infra.core import require
        require(current['Video']==original['Video'] and current['Shortcuts']==original['Shortcuts'] and not current['Processes'],'Restored real-user settings mismatch')
    transaction.finish()
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);a=p.parse_args()
    print(recover(read_json(a.config)))
