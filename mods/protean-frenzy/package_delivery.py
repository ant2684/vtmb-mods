"""Package sealed, tested bytes. No game writes, rebuilds or publication."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent

ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,default=HERE/'local.json');ap.add_argument('--destination',type=Path,required=True)
ap.add_argument('--preserve-rollback',action='store_true',help='Verify and retain the existing manifest-backed rollback archive without reading the game installation')
ap.add_argument('--no-rollback',action='store_true',help='Reuse manifest-pinned existing rollback archives; do not create a duplicate')
ap.add_argument('--flat-game',action='store_true',help='Complete game layout with all eight files ready to copy into the game root')
ap.add_argument('--version',help='Public release version, for example 1.3.1')
ap.add_argument('--source-root',type=Path,help='Selected clean standalone source tree; defaults to this module')
args=ap.parse_args()
assert not args.version or re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',args.version),'Invalid release version'
assert not(args.no_rollback and args.preserve_rollback),'Choose one rollback policy'
cfg=json.loads(args.config.read_text());out=Path(cfg['output']);game=Path(cfg['game']);dest=args.destination.resolve();dest.mkdir(parents=True,exist_ok=True)
def sha(data):return hashlib.sha256(data).hexdigest()
seal=json.loads((out/'accepted.json').read_text());assert seal['passed']
plugin=out/'Payload/Bin/loader/protean-frenzy-improved.vtm';assert sha(plugin.read_bytes())==seal['plugin_sha256']
game_readme='''Protean & Frenzy Improved

Improves Protean transformations, Claws combat and Frenzy behavior, including
Claws sneak attacks and the Griffith Park werewolf encounter.
Requires Bloodlines, Unofficial Patch 12.0 and Game Mod Loader.

INSTALLATION
1. Close the game and back up the files you will replace.
2. Copy the contents of Core into the game folder containing Vampire.exe.
3. Copy any chosen Optional components into the same game folder.

OPTIONAL COMPONENTS
ClawsModels: updated Claws animations. Install both male and female models.
StealthSound: Claws sneak-attack sounds.
StealthBlood: Claws sneak-attack blood effects.
FrenzyLibrary / FrenzyGriffith: enable Frenzy on the included Library and
Griffith Park maps. Back up existing map files before replacing them.

SETTINGS
Edit Bin/loader/protean-frenzy-improved.ini. Set an option to 1 to enable it
or 0 to disable it, then restart the game. Descriptions are beside each option.
InventoryFixes is required by ProteanTransformFixes and MeleeFrenzy.
ClawsComboBuffer requires the supplied Claws models.
Model and map changes remain installed when INI options are disabled.

ROLLBACK
Close the game and restore the files you backed up before installation.
Remove a supplied file only if it was absent before installation.
Restore both Claws models together.
'''
rollback_readme='''Protean & Frenzy Improved - Local pre-installation backup

Use this backup only with the installation it was created from.
Close the game. Remove the added protean-frenzy-improved.vtm and its INI,
then copy the contents of Original into the game folder.
Restore both Claws models together.
'''
payload={}
for p in (out/'Payload').rglob('*'):
    if p.is_file():payload['Core/'+p.relative_to(out/'Payload').as_posix()]=p.read_bytes()
for component in ['ClawsModels','StealthSound','StealthBlood','FrenzyLibrary','FrenzyGriffith']:
    root=out/'Components'/component
    for p in root.rglob('*'):
        if p.is_file():
            relative=p.relative_to(root).as_posix();assert sha(p.read_bytes())==seal['resources'][component+'/'+relative]
            prefix='Optional/'+component+'/'
            payload[prefix+relative]=p.read_bytes()
assert len(payload)==8 and all(not x.endswith(('.exe','.lib','.pdb','.py','.pyc','.pyo')) for x in payload)
# Preserve the original acceptance input; only its UP version comment was wrong.
ini_name='Core/Bin/loader/protean-frenzy-improved.ini'
assert sha(payload[ini_name])==seal['ini_sha256']
payload[ini_name]=payload[ini_name].replace(b'supported UP 11.5 modules.',b'supported UP 12.0 modules.')
assert payload[ini_name]==(HERE/'protean-frenzy-improved.ini').read_bytes()
if args.flat_game:
    flat={}
    for name,data in payload.items():
        rel=name[len('Core/'):] if name.startswith('Core/') else '/'.join(name.split('/')[2:])
        assert rel and rel not in flat,('Duplicate complete-game destination',name)
        flat[rel]=data
    payload=flat
    game_readme="""Protean & Frenzy Improved

Improves Protean transformations, Claws combat and Frenzy behavior, including
Claws sneak attacks and the Griffith Park werewolf encounter.
Requires Bloodlines, Unofficial Patch 12.0 and Game Mod Loader.

INSTALLATION
1. Close the game and back up the files this archive will replace.
2. Extract the archive into the game folder containing Vampire.exe, merging
   the Bin and Unofficial_Patch folders.
3. Start the game.

The archive includes both Claws models, sneak-attack effects and the Library
and Griffith Park map files. Back up custom map edits before replacing them.

UPDATING FROM 1.3.1
Replace only Bin/loader/protean-frenzy-improved.vtm and restart the game.
All other game files are unchanged. Keep your existing INI settings.

SETTINGS
Edit Bin/loader/protean-frenzy-improved.ini. Set an option to 1 to enable it
or 0 to disable it, then restart the game. Descriptions are beside each option.
InventoryFixes is required by ProteanTransformFixes and MeleeFrenzy.
Model and map changes remain installed when INI options are disabled.

ROLLBACK
Close the game and restore the files you backed up before installation.
Remove a supplied file only if it was absent before installation.
Restore both Claws models together.
"""
if args.version=='1.3.2':
    game_readme+='''
CHANGES IN 1.3.2
Fixes missing Claws attacks on NPCs such as the Serial Killer.
Player combos and Frenzy behavior are preserved.
'''
if args.version:
    first,rest=game_readme.split('\n',1);game_readme=first+' '+args.version+'\n'+rest
payload['README.txt']=game_readme.encode('ascii')
source={}
source_root=args.source_root.resolve() if args.source_root else HERE
for p in source_root.rglob('*'):
    if not p.is_file() or p.name=='local.json' or '__pycache__' in p.parts:continue
    if p.suffix.lower() not in ['.py','.c','.h','.inc','.ini','.json','.md']:continue
    assert p.name not in ['accepted.json'],p
    source[p.relative_to(source_root).as_posix()]=p.read_bytes()
assert [x for x in source if Path(x).name.lower().startswith('readme')]==['README.md']
helper=source['tests/gameplay/game_probe.py'].decode('utf-8')
assert "n.SetRelationship('player D_HT 10')" in helper and "player D_HT 99" not in helper[helper.index('native_targets=[]'):]
assert 'tests/exact_claws_pools.c' in source and 'tests/verify_fixture_priorities.py' in source
preserved_rollback=None
if args.no_rollback:
    references=seal.get('rollback_references',[])
    assert references,'No manifest-pinned prior rollback set'
    for row in references:
        archive=Path(row['path']);assert sha(archive.read_bytes())==row['sha256']
elif args.preserve_rollback:
    prior=json.loads((out/'archives.json').read_text());assert prior['passed']
    preserved_rollback=next(r for r in prior['archives'] if r['kind']=='Local-Rollback')
    archive=dest/'Protean-and-Frenzy-Improved-Local-Rollback.zip'
    assert archive.resolve()==Path(preserved_rollback['path']).resolve()
    assert archive.stat().st_size==preserved_rollback['bytes']
    assert sha(archive.read_bytes())==preserved_rollback['sha256']
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(set(z.namelist()))
        assert set(z.namelist())==set(preserved_rollback['files'])
        for name,digest in preserved_rollback['files'].items():assert sha(z.read(name))==digest
else:
    rollback={}
    old=['protean-improved','protean-lifecycle','frenzy-melee-katana-test','claws-flow','claws-stealth-position','griffith-frenzy-werewolf-fix']
    for name in old:
        for ext in ['.vtm','.ini']:
            p=game/'Bin/loader'/(name+ext)
            if p.exists():rollback['Original/Bin/loader/'+p.name]=p.read_bytes()
    for component in ['ClawsModels','StealthSound','StealthBlood','FrenzyLibrary','FrenzyGriffith']:
        root=out/'Components'/component
        for p in root.rglob('*'):
            if p.is_file():
                rel=p.relative_to(root);original=game/rel
                assert original.exists(),('Local rollback needs an absence ledger for this different setup',rel)
                rollback['Original/'+rel.as_posix()]=original.read_bytes()
    original_python=game/'Unofficial_Patch/python/vamputil.py'
    rollback['Original/Unofficial_Patch/python/vamputil.py']=original_python.read_bytes()
    assert not (game/'Bin/loader/protean-frenzy-improved.vtm').exists()
    rollback['README.txt']=rollback_readme.encode('ascii')
reports=[]
packages=[('Game',payload),('Source-and-Tests',source)]
if preserved_rollback is None and not args.no_rollback:packages.append(('Local-Rollback',rollback))
for label,files in packages:
    if args.version:
        assert label in ['Game','Source-and-Tests'],'Versioned packaging requires reused rollback references'
        name=('VTMB Protean and Frenzy Improved '+args.version+'.zip') if label=='Game' else ('Protean and Frenzy Improved '+args.version+' Source.zip')
        archive=dest/name
    else:archive=dest/('Protean-and-Frenzy-Improved-'+label+'.zip')
    assert not archive.exists(),'Never overwrite a frozen release archive' 
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,10,29,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and set(z.namelist())==set(files)
        for name,data in files.items():assert z.read(name)==data
    reports.append(dict(kind=label,path=str(archive),sha256=sha(archive.read_bytes()),bytes=archive.stat().st_size,files={name:sha(data) for name,data in sorted(files.items())}))
if preserved_rollback is not None:reports.append(preserved_rollback)
(out/'archives.json').write_text(json.dumps(dict(passed=True,archives=reports),indent=2)+'\n')
print(json.dumps([{k:v for k,v in r.items() if k!='files'} for r in reports],indent=2))
