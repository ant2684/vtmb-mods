"""Package an already finalized candidate; never rebuild or alter its bytes."""
import argparse, hashlib, json, sys, zipfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO))
from infra.common.clean_payload import verify_clean
MANUAL="""Flamethrower Damage Numbers

Enables the game's normal floating hit numbers for flamethrower damage to NPCs.
Uses the existing Damage Floaters option and normal hit-number calculation.
Damage, fuel consumption and other combat rules are unchanged.
Requires the Unofficial Patch Game Mod Loader and the supported Bloodlines server.

Manual installation
1. Exit the game.
2. If Bin/loader/flamethrower-damage-numbers.vtm already exists, preserve a copy
   outside Bin/loader before replacing it.
3. Copy the included Bin folder into the game directory beside Vampire.exe,
   preserving the included folder layout.
4. Start the game through the usual Unofficial Patch Mod Loader setup.
   Damage Floaters must be enabled in the game's Gameplay settings.

Rollback
Exit the game and remove Bin/loader/flamethrower-damage-numbers.vtm.
If you replaced an earlier file, restore your preserved original instead.
Restart the game. No game DLL, save or configuration file needs restoration.
"""
SOURCE=[
 'LICENSE','NOTICE','requirements.txt',
 'infra/common/native_fixture.h','infra/common/finalize_pe.py','infra/common/clean_payload.py',
 'mods/flamethrower/Build.ps1','mods/flamethrower/Verify.ps1',
 'mods/flamethrower/plugin/flamethrower_numbers.c',
 'mods/flamethrower/tests/exact.c','mods/flamethrower/tests/verify_flow.py',
 'mods/flamethrower/tools/package.py','mods/flamethrower/tools/install_local.py',
]
def digest(b):return hashlib.sha256(b).hexdigest().upper()
def check_zip(path, expected):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        assert set(z.namelist())==set(expected)
        assert len(z.namelist())==len(expected)
        for name,b in expected.items():assert z.read(name)==b,(path,name)
def create_zip(path,entries):
    assert not path.exists(),'refuse overwriting an existing archive'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,b in sorted(entries.items()):
            info=zipfile.ZipInfo(name,(2026,10,12,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16;z.writestr(info,b)
    check_zip(path,entries)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plugin',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    plugin=Path(a.plugin).resolve();output=Path(a.output).resolve();output.mkdir(parents=True,exist_ok=True)
    data=plugin.read_bytes();verify_clean(plugin,['loaded_vampire'],source=REPO/'mods/flamethrower/plugin')
    folder=output/'VTMB Flamethrower Damage Numbers - Test';assert not folder.exists(),'refuse overwriting payload'
    (folder/'Bin/loader').mkdir(parents=True)
    (folder/'Bin/loader'/plugin.name).write_bytes(data);(folder/'README.txt').write_text(MANUAL,encoding='utf8',newline='\r\n')
    verify_clean(plugin,['loaded_vampire'],payload=folder)
    entries={p.relative_to(folder).as_posix():p.read_bytes() for p in folder.rglob('*') if p.is_file()}
    assert set(entries)=={'README.txt','Bin/loader/flamethrower-damage-numbers.vtm'}
    assert not any(word in MANUAL.lower() for word in ('verify','test checklist','diagnostic','installer'))
    gameplay=output/'VTMB Flamethrower Damage Numbers - Test.zip';create_zip(gameplay,entries)
    source={name:(REPO/name).read_bytes() for name in SOURCE}
    source['README.md']=(REPO/'mods/flamethrower/README.md').read_bytes()
    assert sum(name.lower().endswith('readme.md') for name in source)==1
    assert not any(Path(n).suffix.lower() in {'.exe','.dll','.vtm','.pdb','.log','.sav'} for n in source)
    capsule=output/'VTMB Flamethrower Damage Numbers - Test Source.zip';create_zip(capsule,source)
    result={'binary_sha256':digest(data),'archives':{p.name:{'sha256':digest(p.read_bytes()),'bytes':p.stat().st_size} for p in (gameplay,capsule)},'source_members':len(source),'gameplay_members':len(entries),'result':'PASS'}
    (output.parent/'package-evidence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
if __name__=='__main__':main()
