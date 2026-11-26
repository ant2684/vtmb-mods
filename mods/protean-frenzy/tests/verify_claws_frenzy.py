"""Permanent stock-AI/player-combo contract against pinned original resources."""
import hashlib,json,os,struct,sys
from pathlib import Path
here=Path(__file__).resolve().parents[1]
cfg=json.loads(Path(os.environ['PFI_CONFIG']).read_text());out=Path(cfg['output'])
sys.path[:0]=[str(here/'tools'),str(here/'_support')]
from compact_models import pack
from frenzy_models import PREFIX,merge,verify_pools
from mdl import seqs,i,cs

FINISHER_MODELS = {
    'female': '81d49f8a7d683fb8295bc2056de7e33f527da99be9b8feae91bf002e652a6739',
    'male': '87a5936cb87707f5880ef4e53765ec7a13ff0226ac6cf1d047f280628bb89589',
}
FINISHER_EVENTS = {
    'stealth_success_attacker_shortvictim': 4,
    'stealth_success_attacker_tallvictim': 4,
    'stealth_success_victim_shortattacker': 2,
    'stealth_success_victim_tallattacker': 2,
    PREFIX + 'stealth_success_victim_shortattacker': 2,
    PREFIX + 'stealth_success_victim_tallattacker': 2,
}


def verify_release_finisher(sex, player, stock, current):
    if hashlib.sha256(current).hexdigest() != FINISHER_MODELS[sex]:
        return verify_pools(player, stock, current)

    # The released finisher appends cues and particle events to the verified pool model.
    baseline = merge(player, stock)
    assert i(current, 140) == len(current) and len(current) > len(baseline)
    assert seqs(baseline) == seqs(current)
    reconstructed = bytearray(current[:len(baseline)])
    reconstructed[140:144] = baseline[140:144]
    for name, number in FINISHER_EVENTS.items():
        sequence = seqs(baseline)[name]
        count, offset = struct.unpack_from('<ii', current, sequence + 20)
        event_start = sequence + offset
        assert count == number and len(baseline) <= event_start <= len(current) - 76 * count, name
        reconstructed[sequence + 20:sequence + 28] = baseline[sequence + 20:sequence + 28]
    assert reconstructed == baseline, 'Only the six finisher event descriptors may change'
    return verify_pools(player, stock, baseline) | {'released_finisher_only_changes_event_tables': True}


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
    rows[sex]=verify_release_finisher(sex,player,stock,current)
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
