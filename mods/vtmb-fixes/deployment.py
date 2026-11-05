"""Internal owned-test transaction and manual-payload staging; not an installer executable."""
import argparse,hashlib,json,re,shutil,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['stage','restage','restore','install']);ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--game',type=Path,required=True);ap.add_argument('--state',type=Path,required=True);ap.add_argument('--plugin',type=Path,required=True);ap.add_argument('--guard',type=Path,required=True);ap.add_argument('--protean',type=Path,required=True);a=ap.parse_args()
sys.path.insert(0,str(a.repo/'mods/protean-frenzy/tests/gameplay'))
import transaction as tr
game=a.game.resolve();state=a.state.resolve()
assert not state.is_relative_to(game),'Recovery/evidence must stay outside game'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
OLD=['console-pause-fix','subtitle-pause-fix','history-stat-reset-fix','container-stack-fix','protean-improved','griffith-frenzy-werewolf-fix']
class Transaction(tr.Transaction):
 def begin(self):
  super().begin()
  # Retain every additional fresh-map/character-creation write target and the
  # exact original files replaced by these packages, once for this whole task.
  extra_trees=['Bin/loader','Vampire/python','Vampire/save','Vampire/maps/graphs',
   'Unofficial_Patch/vdata','Unofficial_Patch/particles','Unofficial_Patch/resource',
   'screenshots','Vampire/screenshots','Unofficial_Patch/screenshots','logs','Vampire/logs','Unofficial_Patch/logs']
  self.created_dirs=[rel for rel in extra_trees if not (game/rel).exists()]
  for tree in extra_trees:
   self.trees.append(tree);self.directories[tree]=[str(p.relative_to(game)) for p in (game/tree).rglob('*') if p.is_dir()]
   for p in (game/tree).rglob('*'):
    if p.is_file():self.preserve(p)
  for sex in ['male','female']:self.single.append('Unofficial_Patch/models/character/shared/'+sex+'/claws.mdl')
  for root in [game,game/'Vampire',game/'Unofficial_Patch']:
   for p in root.iterdir():
    if p.is_file() and p.suffix.lower() in ['.cfg','.txt','.log','.inf']:
     self.single.append(str(p.relative_to(game)))
  self.single+=['.vtmb-regression.lock','p5_owned_python_errors.txt']
  for rel in self.single:
   if (game/rel).is_file():self.preserve(game/rel)
  dump(state/'transaction.json',{'game':str(game),'trees':self.trees,'single':self.single,'files':self.records,'directories':self.directories,'created_dirs':self.created_dirs})
 def preserve(self,p):
  p=self.inside_game(p);rel=str(p.relative_to(game))
  if rel in self.records:return
  q=state/'backup'/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
  assert sha(p)==sha(q)
  self.records[rel]={'sha256':sha(p),'mtime_ns':p.stat().st_mtime_ns}

def stage():
 assert not tr.running_games(),'An existing user game must remain untouched'
 assert sha(a.plugin)=='2db0d54fee2eff63e79a7ac5307c0070f229b99ce4f2478987de598498137a9d'
 assert sha(a.guard)=='2f9b26347616c0cf1311b34e6cc58b091e24c6ee8c72f0c387bf726d44d3804b'
 assert sha(a.protean)=='7f7372ffb5d7c16466cf8234275c7f5fcaec7afac6aebd5bc8f365b95106d3c1'
 payload={};skipped={}
 with zipfile.ZipFile(a.protean) as z:
  assert z.testzip() is None
  for rel in z.namelist():
   if rel.endswith('/') or rel=='README.txt':continue
   if rel=='Unofficial_Patch/maps/la_library_1.bsp':
    assert sha(game/rel)=='2008a86c9f6727f9b25d9885f4dc2a1706a81ea1c16fb02a9185aaa872b6fd4b'
    skipped[rel]='Owner approved installed map: nofrenzyarea=0 and independent Priest equipment change';continue
   data=z.read(rel)
   if (game/rel).exists() and sha(game/rel)==hashlib.sha256(data).hexdigest():skipped[rel]='Already exact release bytes; no write';continue
   payload[rel]=data
 payload['Bin/loader/ant2684-fixes-adjustments.vtm']=a.plugin.read_bytes();payload['Bin/loader/ant2684-fixes-adjustments.ini']=(HERE/'ant2684-fixes-adjustments.ini').read_bytes()
 payload['Bin/loader/vtmb-loading-input-guard.vtm']=a.guard.read_bytes()
 payload['Bin/loader/vtmb-loading-input-guard.ini']=(HERE/'vtmb-loading-input-guard.ini').read_bytes()
 deleted=[rel for rel in ['Bin/loader/vtmb-fixes.vtm','Bin/loader/vtmb-fixes.ini'] if (game/rel).is_file()]
 for stem in OLD:
  for ext in ['.vtm','.txt']:
   rel='Bin/loader/'+stem+ext
   if (game/rel).exists():deleted.append(rel)
 target_records={rel:({'exists':True,'sha256':sha(game/rel),'mtime_ns':(game/rel).stat().st_mtime_ns} if (game/rel).is_file() else {'exists':False}) for rel in [*payload,*deleted]}
 if a.mode=='stage':dump(state/'deployment-plan.json',{'replaced':target_records,'deleted':deleted,'skipped':skipped,'expected':{k:hashlib.sha256(v).hexdigest() for k,v in payload.items()}})
 else:
  expected=json.loads((state/'deployment-plan.json').read_text(encoding='utf-8'))
  assert target_records==expected['replaced'],'Baseline must be restored exactly before final installation'
 for rel,data in payload.items():
  p=game/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);assert sha(p)==hashlib.sha256(data).hexdigest()
 for rel in deleted:(game/rel).unlink()
 assert len(list((game/'Bin/loader').glob('*.vtm')))==9,'Unexpected active plugin inventory'
 dump(state/('staged.json' if a.mode in ['stage','restage'] else 'installed.json'),{'game':str(game),'plugin_sha256':sha(a.plugin),'protean_archive':sha(a.protean),'installed':{rel:sha(game/rel) for rel in payload},'deleted':deleted,'skipped':skipped,'active_plugins':{p.name:sha(p) for p in (game/'Bin/loader').glob('*.vtm')}})

if a.mode=='stage':
 assert not state.exists(),'Use a fresh baseline transaction'
 state.mkdir(parents=True)
 tx=Transaction(game,state);tx.begin();dump(game/'.vtmb-regression.lock',{'task':'vtmb-fixes','state':str(state)})
 try:stage()
 except BaseException:
  tx.restore();raise
 print('STAGED approved payloads; one original recovery set:',state,flush=True)
elif a.mode=='restore':
 d=json.loads((state/'transaction.json').read_text(encoding='utf-8'));assert Path(d['game']).resolve()==game
 tx=Transaction(game,state)
 for key,value in [('trees',d['trees']),('single',d['single']),('records',d['files']),('directories',d['directories']),('video',json.loads((state/'video-before.json').read_text()))]:setattr(tx,key,value)
 tx.restore()
 for rel in d['created_dirs']:
  p=(game/rel).resolve();assert p.is_relative_to(game)
  if p.is_dir() and not any(p.iterdir()):p.rmdir()
 print('RESTORED original bytes, mtime, settings and shortcuts; recovery set retained for final installation',flush=True)
else:
 assert (state/'restored.json').exists(),'Restore and verify temporary test state first'
 stage()
 if a.mode=='restage':
  dump(game/'.vtmb-regression.lock',{'task':'vtmb-fixes','state':str(state)})
  print('RESTAGED for validation; same original recovery set retained',flush=True)
 else:print('INSTALLED exact tested payloads; same useful recovery set retained',flush=True)
