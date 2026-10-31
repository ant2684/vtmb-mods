"""Change only a supported map's single Frenzy permission byte; no game writes."""
import argparse,hashlib,json,re,struct
from pathlib import Path
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,default=HERE/'local.json');args=ap.parse_args()
cfg=json.loads(args.config.read_text());game=Path(cfg['game']);out=Path(cfg['output'])
source_root=Path(cfg.get('map_resource_root',str(game/'Unofficial_Patch/maps')))
# On-state identities distinguish supported UP map variants. Never migrate their
# exit identifiers or any geometry between variants merely to enable Frenzy.
supported={
 'la_library_1.bsp':{'557c5138c2b56739897b0f8bb7650b24f0fb06f00c2ea4b117df4608fb6ce403',
                     'e92af309033ce32cfbf97723d49fc6ccb7357f71ce79179b33980718080a966a'},
 'sp_observatory_2.bsp':{'6690798013dd82432a4c94f199111e35c5ca581bbc5ad351b0ba626ffec05cb7'}
}
def sha(data):return hashlib.sha256(data).hexdigest()
report={}
for name,accepted in supported.items():
    before=(source_root/name).read_bytes()
    assert before[:8]==b'VBSP\x11\0\0\0',('Unsupported BSP format',name)
    offset,length=struct.unpack_from('<II',before,8)
    assert 0<offset<offset+length<=len(before)
    entity=before[offset:offset+length]
    matches=list(re.finditer(rb'"nofrenzyarea"\s+"([01])"',entity));assert len(matches)==1
    position=offset+matches[0].start(1)
    after=before[:position]+b'0'+before[position+1:]
    assert sha(after) in accepted,('Unsupported map variant',name,sha(before),sha(after))
    assert [i for i,(a,b) in enumerate(zip(before,after)) if a!=b] in [[],[position]]
    component='FrenzyLibrary' if name.startswith('la_') else 'FrenzyGriffith'
    dest=out/'Components'/component/'Unofficial_Patch/maps'/name
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(after)
    report[name]=dict(component=component,before_sha256=sha(before),sha256=sha(after),bytes=len(after),
        permission_offset=position,changed_bytes=int(before[position]!=after[position]),
        scope='Only nofrenzyarea. Original entity names, other lumps and all other bytes preserved.')
(out/'maps.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
