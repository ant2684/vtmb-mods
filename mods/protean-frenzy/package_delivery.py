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
game_readme='''Protean & Frenzy Improved - native runtime

One native plugin with eight startup INI settings. Requires 32-bit Steam
Bloodlines, supported Unofficial Patch 12.0 native modules and Game Mod Loader.
All mod logic runs in the plugin. No modified Python file is supplied or required;
the game retains its own stock scripts. Native hook ownership is checked at load.

MANUAL INSTALLATION AND UPGRADE
Close the game. Back up every file you replace and your current vamputil.py.
Copy the CONTENTS of Core into the game root.
Keep protean-frenzy-improved.ini beside protean-frenzy-improved.vtm.
If upgrading from the earlier Python-supported release, restore your ORIGINAL,
unmodified UP 12.0 Unofficial_Patch/python/vamputil.py from your own backup or
matching patch installation. This package intentionally does not replace it.
For a file customized by other mods, preserve those changes and remove only the
previous Protean support after comparing your original; arbitrary script/native
mod combinations are outside the tested compatibility claim.

OPTIONAL RESOURCES
Copy the contents of the chosen Optional directory into the game root:
ClawsModels: the matching male/female compact Claws models and their existing
animations, combos and hit metadata. Required by ClawsComboBuffer.
StealthSound: Broadsword success clip and original failed Claws clip.
StealthBlood: finite Katana-equivalent blood emitter.
FrenzyLibrary / FrenzyGriffith: Frenzy permission on the supplied supported maps.
Native settings cannot undo copied models, sounds, particles or maps. Back up
custom resources and do not overwrite custom map edits without review.

SETTINGS IN [Fixes]
WarformFrenzy: Protean 5/Frenzy ownership, bonuses and end ordering.
FilterLoadFix: saved-active Protean brightness independently of RedVision.
InventoryFixes: duplicate/nested registration, fists slot, retained Claws and
native owned-Shadow Frenzy effects/equipment even when map Outputs are disabled.
ProteanTransformFixes: paired scene, immediate action interruption, feeding/timer,
return FX, load recovery and native delayed-idle ownership. Requires InventoryFixes.
ClawsComboBuffer: fresh-click 150ms continuation buffer; holding does not combo.
ClawsStealthPosition: shared Protean/Tiger successful paired positioning and exit.
MeleeFrenzy: selected supported native melee weapon. Requires InventoryFixes.
GriffithFrenzyCollision: scoped Werewolf/Shadow collision and ground support;
map Frenzy permission is a separate resource component.
All default to 1. Use 0 to disable; invalid values disable the affected option.
Missing settings default to 1. Restart after edits. InventoryFixes=0 also prevents
native transform and custom Melee binding. Historical Core aliases are not read.
Full descriptions and dependency/disabled behavior are in the INI.

ROLLBACK
Close the game. Remove protean-frenzy-improved.vtm and its INI. Restore your old
native modules and all resources you replaced. Restore BOTH models together.
Restore your previous vamputil.py if you changed it during upgrade. Remove an
added loose resource only if it was absent before installation. The separate
local rollback archive applies only to the local setup recorded in that archive.

SCOPE
No rejected guard, global idle-command suppression, Tiger pose redesign or new
attack-speed/damage balance. Native owned timers discard stale scheduled alert
exits; ordinary direct idle commands remain available outside an owned morph.
Supported local setup only; arbitrary clan/armor/mod combinations and exact Frenzy
cadence equivalence are not certified. Technical checks and owner acceptance are
separate. This archive has no executable installer or diagnostic plugin.
'''
rollback_readme='''Protean & Frenzy Improved - LOCAL PRE-INSTALLATION ROLLBACK

This archive preserves the local setup recorded when the unified package was
prepared. It is not a pristine game baseline and is not universal for other PCs.
Close the game. Remove Bin/loader/protean-frenzy-improved.vtm and
Bin/loader/protean-frenzy-improved.ini (both were absent in this recorded setup).
Copy the contents of Original into the game directory, replacing the included
old plugins/resources. Restore both Claws models together and restore the prior
vamputil.py. Do not load the unified and replaced plugins simultaneously.
Keep unrelated mods, settings and saves. For a different installation, use its
own pre-installation backup instead. This archive contains no executable installer.
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
    game_readme="""Protean & Frenzy Improved - Complete Native Package

Requires 32-bit Bloodlines, supported Unofficial Patch 12.0 and Game Mod Loader.
This is the complete package, not an update requiring an earlier Protean package.
It includes one native VTM, its INI, both matching Claws models, stealth sound and
blood resources, and the two supported maps with Frenzy permission enabled.

INSTALLATION
Close the game. Preserve your previous versions of the files you replace. Extract
the CONTENTS of this archive into the game root, beside Vampire.exe. Install both
Claws models with this VTM. Keep existing INI values when upgrading custom settings.
The map files replace the supplied supported variants; preserve custom map edits.

Keep unrelated plugins. No additional standalone plugin, test helper, Python file
or executable installer belongs in this package. Keep your stock UP12 vamputil.py;
restore it from your own original when upgrading from the old Python-supported mod.

BEHAVIOR AND SETTINGS
The VTM combines Protean/Frenzy lifecycle, inventory, melee, combo buffer, stealth
positioning and Griffith collision fixes. The INI documents eight startup options.
Use 0/1 and restart the game. InventoryFixes=0 disables dependent transform/Melee
fixes, but model attack-pool separation stays active independently of all switches
and inventory-hook readiness. This separation preserves ordinary custom combos
and the stock NPC/Frenzy candidate pools. Original models without those pools forward
unchanged. Native hunger Frenzy and its feeding rules are retained.

The installed models, sounds, particles and map permissions are resource changes;
INI switches do not restore their original bytes. Both model pools are deliberate.

ROLLBACK
Close the game. Restore your prior VTM, INI and any replaced resources from your
existing backup/archive. Remove a supplied loose file only if it was absent before
installation. Restore both prior models together. Do not load the unified plugin
and the replaced native modules together. This archive has no redundant rollback
copy, debug plugin, save, log or gameplay checklist.
"""
if args.version=='1.3.2':
    game_readme+='''
CHANGES IN 1.3.2
NPCs with Claws, including the Serial Killer, retain their original AI attack
pool instead of receiving the player's directional combos. Ordinary player
combos and owned Frenzy selection are preserved. Models, INI defaults, damage,
speed, sounds and maps are unchanged from 1.3.1. Restart after replacing the VTM.
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
