"""Generate optional native-mod resources; no game writes."""
import argparse,hashlib,json,struct,sys,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,default=HERE/'local.json');args=ap.parse_args()
cfg=json.loads(args.config.read_text());game=Path(cfg['game']);out=Path(cfg['output'])
sys.path[:0]=[str(HERE/'tools'),str(HERE/'_support'),cfg['native_dependencies']]
from compact_models import pack,verify,BASES
from frenzy_models import merge,verify_pools
from mdl import seqs,anims
def sha(d):return hashlib.sha256(d).hexdigest()
report={}
def emit(component,rel,before,after):
    assert before!=after,rel
    dest=out/'Components'/component/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(after)
    report[rel]=dict(component=component,before_sha256=sha(before),sha256=sha(after),bytes=len(after))
def packed(name):
    rows=[]
    for folder in ['Vampire','Unofficial_Patch']:
        for archive in sorted((game/folder).glob('pack*.vpk')):
            with archive.open('rb') as f:
                f.seek(-9,2);count,offset=struct.unpack('<II',f.read(8));f.seek(offset);index=f.read();p=0
                for _ in range(count):
                    n=struct.unpack_from('<I',index,p)[0];p+=4;entry=index[p:p+n].decode();p+=n
                    offset,size=struct.unpack_from('<II',index,p);p+=8
                    if entry.lower()==name.lower():rows.append((archive,offset,size))
    assert rows,('Missing packed resource',name)
    archive,offset,size=rows[-1]
    with archive.open('rb') as f:f.seek(offset);return f.read(size)
def baseline(rel,digest):
    for source in [out/'inputs'/rel,Path(cfg['original_resource_root'])/rel,game/rel]:
        if source.exists() and sha(source.read_bytes())==digest:return source.read_bytes()
    data=packed(rel.split('/',1)[1]);assert sha(data)==digest,('Unsupported baseline',rel,sha(data));return data

rel='Unofficial_Patch/vdata/items/item_w_claws.txt'
before=baseline(rel,'d0e322de5b9c70a6cadcc68def0bda31d600cbb8aa74cd575e40e9b28303a58d')
anchor=b'\t\t"pickup"';assert before.count(anchor)==1
insert=b'''\t\t"stealth_kill_success"\r\n\t\t{\r\n\t\t\t"sound1"\t"Weapons/Melee/Katana/Stealth_Sword.wav"\r\n\t\t}\r\n\t\t"stealth_kill_failure"\r\n\t\t{\r\n\t\t\t"sound1"\t"Weapons/Melee/Fists/Stealth_Kill_Failure.wav"\r\n\t\t}\r\n'''
emit('StealthSound',rel,before,before.replace(anchor,insert+anchor))
rel='Unofficial_Patch/particles/stealth_claws_emitter.txt'
before=baseline(rel,'bad6314bb04455e110d04ddaaaa11ca2be9b0176ed160043a2a2eeadc0805779')
after=packed('particles/stealth_katana_emitter.txt');assert b'loop\t"0"' in after and after.count(b'stealth_katana_fx1')==2
emit('StealthBlood',rel,before,after)

for sex,digest in BASES.items():
    rel=f'Unofficial_Patch/models/character/shared/{sex}/claws.mdl'
    source=out/'inputs'/rel
    if not source.exists():
        data=(game/rel).read_bytes();assert sha(data)==digest
        source.parent.mkdir(parents=True,exist_ok=True);source.write_bytes(data)
    before=source.read_bytes();assert sha(before)==digest
    after,detail=pack(before,sex);detail['preservation']=verify(before,after,detail)
    assert 'claws_guard_enter_natural' not in seqs(after)
    assert len(seqs(after))==len(seqs(before))-1
    stock=packed(f'models/character/shared/{sex}/claws.mdl')
    assert sha(stock)=={'male':'c7b515d36d2b5dab50bd2eea178e2e455a589ef35359b565cfcf9e95e726fac8','female':'31e39caabb6ef2528d3cdab41a9bffb16c3d127fbfb5ce9bdc430c0290c0055c'}[sex]
    player=after;after=merge(player,stock);detail['frenzy_pools']=verify_pools(player,stock,after)
    emit('ClawsModels',rel,before,after);report[rel]['model_audit']=detail

(out/'resources.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({rel:{k:v for k,v in r.items() if k!='model_audit'} for rel,r in report.items()},indent=2))
