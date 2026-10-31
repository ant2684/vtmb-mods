"""Read-only preflight. Native signature guards remain authoritative at runtime."""
import argparse,configparser,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
KEYS=['WarformFrenzy','FilterLoadFix','InventoryFixes','ProteanTransformFixes','ClawsComboBuffer','ClawsStealthPosition','MeleeFrenzy','GriffithFrenzyCollision']
OLD=['protean-improved.vtm','protean-lifecycle.vtm','claws-flow.vtm','claws-stealth-position.vtm','frenzy-melee-katana-test.vtm','griffith-frenzy-werewolf-fix.vtm']
ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,default=HERE/'local.json');ap.add_argument('--installed',action='store_true');args=ap.parse_args()
cfg=json.loads(args.config.read_text());game=Path(cfg['game']);out=Path(cfg['output'])
root=game if args.installed else out/'Payload'
ini=root/'Bin/loader/protean-frenzy-improved.ini';parser=configparser.ConfigParser(interpolation=None,strict=False)
parser.read(ini);errors=[];options={}
if not ini.exists():errors.append('Missing INI: native defaults are all enabled')
for key in KEYS:
    value=parser.get('Fixes',key,fallback='1').strip()
    options[key]=value=='1'
    if value not in ['0','1']:errors.append('Invalid value disables '+key+': '+repr(value))
for dependent in ['ProteanTransformFixes','MeleeFrenzy']:
    if options[dependent] and not options['InventoryFixes']:errors.append(dependent+' requires InventoryFixes=1; runtime refuses this dependent feature')
if args.installed:
    for name in OLD:
        if (game/'Bin/loader'/name).exists():errors.append('Remove replaced module from active loader: '+name)
    if options['ClawsComboBuffer']:
        for sex,digest in [('male','93c55229b2bb9b687f7fe0d6c0e1b511de4c250680190a25118ca7e23d06a0f8'),('female','b51f1d20916f393911426bae69b65f8b2efee45520987ce2bdfad254cacdaf86')]:
            model=game/('Unofficial_Patch/models/character/shared/'+sex+'/claws.mdl')
            if not model.exists() or hashlib.sha256(model.read_bytes()).hexdigest()!=digest:errors.append('Install matching ClawsModels: '+sex)
for rel,digest in [('Vampire/dlls/vampire.dll','c546f4de2003624d72f54d03805e0dbe1d8157231adcc62368ff53fe6e48a76f'),('Vampire/cl_dlls/client.dll','e88beae0dd03af06493c71c5e8d87a6993b54e590cb6ad37cd3513c588582870')]:
    file=game/rel
    if not file.exists() or hashlib.sha256(file.read_bytes()).hexdigest()!=digest:errors.append('Unsupported native input: '+rel)
print(json.dumps(dict(passed=not errors,scope='read-only preflight; runtime ownership and signature guards still apply',options=options,issues=errors),indent=2))
raise SystemExit(bool(errors))
