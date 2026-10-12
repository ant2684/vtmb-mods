"""Optional guarded local copy; not an installer executable or gameplay payload.
Keep backups/receipt outside Bin/loader. Never launch/stop the game or edit cvars.
"""
import argparse, datetime, hashlib, json, os, shutil, sys
from pathlib import Path
REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO))
from infra.common.clean_payload import verify_clean
SERVER_SHA='c546f4de2003624d72f54d03805e0dbe1d8157231adcc62368ff53fe6e48a76f'
NAME='flamethrower-damage-numbers.vtm'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--game',required=True);ap.add_argument('--payload',required=True);ap.add_argument('--receipt',required=True);a=ap.parse_args()
    game=Path(a.game).resolve();payload=Path(a.payload).resolve();receipt=Path(a.receipt).resolve()
    source=payload/'Bin/loader'/NAME;dest=game/'Bin/loader'/NAME
    assert sha(game/'Vampire/dlls/vampire.dll')==SERVER_SHA,'unsupported game module'
    assert (game/'Vampire.exe').is_file() and dest.parent.is_dir(),'game layout not found'
    assert not dest.is_symlink() and dest.resolve().is_relative_to(game),'unexpected destination'
    verify_clean(source,['loaded_vampire'],payload=payload)
    expected=sha(source);prior=sha(dest) if dest.exists() else None
    if prior==expected:print('Already installed; no files changed');return
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=game/'Mod_Backups'/('Flamethrower_Damage_Numbers_'+stamp)
    assert backup.resolve().is_relative_to(game/'Mod_Backups')
    backup.mkdir(parents=True,exist_ok=False)
    if prior:
        shutil.copy2(dest,backup/NAME);assert sha(backup/NAME)==prior
    record={'game':str(game),'destination':str(dest),'backup':str(backup),'before_sha256':prior,'after_sha256':expected,
            'status':'preserved','rollback':'restore backup VTM' if prior else 'remove only newly installed VTM'}
    receipt.parent.mkdir(parents=True,exist_ok=True)
    def record_state():
        text=json.dumps(record,indent=2)+'\n';receipt.write_text(text,encoding='utf8');(backup/'receipt.json').write_text(text,encoding='utf8')
    record_state()
    temp=dest.with_name(NAME+'.new')
    assert not temp.exists(),'temporary destination already exists'
    created=False
    try:
        with temp.open('xb') as f:
            created=True
            f.write(source.read_bytes())
        assert sha(temp)==expected
        assert (sha(dest) if dest.exists() else None)==prior,'destination changed after backup'
        os.replace(temp,dest)
    finally:
        if created and temp.exists() and sha(temp)==expected:temp.unlink()
    assert sha(dest)==expected
    record['status']='installed';record_state();print(json.dumps(record))
if __name__=='__main__':main()
