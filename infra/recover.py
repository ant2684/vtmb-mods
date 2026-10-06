"""Explicit recovery refuses uncertain process ownership or unknown changes."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from infra.core import ROOT, read_json, run, need
from infra.session import Transaction


def settings_restore_allowed(folder,current):
    """A historical owned PID does not own later personal settings."""
    from infra.core import Blocked
    original=read_json(folder/'settings.json')
    unchanged=all(current[k]==original[k] for k in ['Video','Shortcuts'])
    snapshot=folder/'settings-after-stop.json'
    frozen=read_json(snapshot) if snapshot.exists() else None
    matches=frozen is not None and all(current[k]==frozen[k] for k in ['Video','Shortcuts'])
    if not unchanged and not matches:
        raise Blocked('Settings changed without a matching after-stop snapshot; preserve newer user values and reconcile explicitly before recovery')


def recover(config):
    transaction=Transaction(need(config,'game_root'),need(config,'state_root'))
    from infra.core import require
    require(transaction.data is not None and transaction.data['game_root']==str(transaction.game),'Recovery journal missing or belongs to another installation; refuse process control')
    if transaction.data and transaction.data['state']=='RESTORED':
        return transaction.restore()
    transaction.acquire_installation()
    folder=transaction.state/transaction.data['id']
    if transaction.data['owned_process']:
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
