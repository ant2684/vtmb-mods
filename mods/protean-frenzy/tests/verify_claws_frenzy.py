"""Permanent stock-AI/player-combo contract against pinned original resources."""
import hashlib,json,os,struct,sys
from pathlib import Path
here=Path(__file__).resolve().parents[1]
cfg=json.loads(Path(os.environ['PFI_CONFIG']).read_text());out=Path(cfg['output'])
sys.path[:0]=[str(here/'tools'),str(here/'_support')]
from compact_models import pack
from frenzy_models import PREFIX,verify_pools
from mdl import seqs,i,cs

def stock_model(sex):
    target='models/character/shared/'+sex+'/claws.mdl'
    with (Path(cfg['game'])/'Vampire/pack001.vpk').open('rb') as f:
        f.seek(-9,2);n,t=struct.unpack('<II',f.read(8));f.seek(t);data=f.read();q=0
        for _ in range(n):
            size=struct.unpack_from('<I',data,q)[0];q+=4;name=data[q:q+size].decode();q+=size
            offset,size=struct.unpack_from('<II',data,q);q+=8
            if name.lower()==target:f.seek(offset);return f.read(size)
    raise AssertionError(target)

rows={}
for sex in ['male','female']:
    rel=Path('Unofficial_Patch/models/character/shared')/sex/'claws.mdl'
    player,_=pack((out/'inputs'/rel).read_bytes(),sex)
    stock=stock_model(sex);current=(out/'Components/ClawsModels'/rel).read_bytes()
    rows[sex]=verify_pools(player,stock,current)
    original=[(n,i(stock,q+16)) for n,q in seqs(stock).items() if cs(stock,q+i(stock,q+4))=='ACT_MELEE_ATTACK_CLAWS']
    observed=[(n[len(PREFIX):],i(current,q+16)) for n,q in seqs(current).items() if n.startswith(PREFIX) and cs(current,q+i(current,q+4))=='ACT_MELEE_ATTACK_CLAWS']
    assert observed==original and ('claws_attack_low',0) in observed and len(observed)==6
    # The former custom-only model must fail this contract; absence of stock
    # low/range alternatives cannot be silently accepted by a preservation test.
    try:verify_pools(player,stock,player)
    except AssertionError:pass
    else:raise AssertionError('Previous custom-only model incorrectly qualifies')
    rows[sex]['previous_model_rejected']=True
(out/'claws-frenzy-models.json').write_text(json.dumps(rows,indent=2)+'\n')
print('PASS both sexes: complete base-game candidate pools/zero weights; exact player combos; stock motion within compression quantum; previous broken model rejected')
