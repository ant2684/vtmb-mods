"""Regression for UP's file-copy side effects; fake filesystem only, no game."""
import argparse,hashlib,json,os,re,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,required=True);args=ap.parse_args()
cfg=json.loads(args.config.read_text());out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
os.environ['PFI_CONFIG']=str(args.config.resolve());sys.path[:0]=[str(HERE/'tests/gameplay'),str(HERE/'_support'),cfg['native_dependencies']]
import run_game as runner
source=(Path(cfg['original_resource_root'])/'Unofficial_Patch/python/vamputil.py').read_bytes()
paths={'Unofficial_Patch/'+p.replace('\\\\','/').lstrip('/') for p in re.findall(r'dst = .*?fileutil\.moddir \+ "([^"]+)"',source.decode())}
paths.add('Unofficial_Patch/vdata/hackterminals/haven_pc.txt');assert len(paths)==24
with tempfile.TemporaryDirectory(prefix='backup-scope-',dir=out) as raw:
    root=Path(raw).resolve();assert root.is_relative_to(out.resolve())
    game=root/'game';game.mkdir();session=root/'session';session.mkdir()
    for rel in paths|{'Unofficial_Patch/python/vamputil.py','Unofficial_Patch/models/character/shared/male/claws.mdl','Unofficial_Patch/models/character/shared/female/claws.mdl'}:
        p=game/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(source if rel.endswith('vamputil.py') else ('original '+rel).encode())
    original={p.relative_to(game).as_posix():(p.read_bytes(),p.stat().st_mtime_ns) for p in game.rglob('*') if p.is_file()}
    runner.GAME=game;runner.gr.running_games=lambda:False;runner.gr.video_snapshot=lambda:{}
    runner.gr.restore_video=lambda v:None;runner.gr.shortcut_snapshot=lambda:'{}';runner.gr.PINS={}
    tx=runner.Transaction(game,session);tx.begin()
    assert paths.issubset(tx.records),'UP copy targets are not fully backed up'
    for index,rel in enumerate(sorted(paths)):
        p=game/rel
        if index%2:p.unlink()
        else:p.write_bytes(b'changed by simulated UP startup')
    created=game/'Unofficial_Patch/python/owned_test.py';created.write_bytes(b'generated')
    tx.restore();assert not created.exists()
    for rel,(data,mtime) in original.items():
        p=game/rel;assert p.read_bytes()==data and p.stat().st_mtime_ns==mtime,rel
result=dict(passed=True,up_side_effect_paths=len(paths),scope='All 24 UP Vampire/Hunter/haven paths covered; fake modifications/deletions restore exact bytes/mtime and generated files are archived/removed. No game process or real game writes.')
(out/'backup-scope.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
