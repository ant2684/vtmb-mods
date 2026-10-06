"""Fresh actual History/None resets and purchasing; no historical PASS reuse."""
import json
import sys
import time
from pathlib import Path
from infra.core import ROOT, Blocked, atomic_json, read_json, require
from infra.history_observations import allocation, pool_proof, collect_pool


def collect(folder):
    sys.path.insert(0,str(ROOT/'mods/history/tests'))
    from drive import Driver,W,u,C
    from gender_regression import initial
    from gameplay import gender,sheet,base,purchase,select_history
    identity=read_json(folder/'identity.json');d=Driver(folder)
    rect=W.RECT();u.GetWindowRect(d.hwnd,C.byref(rect))
    if (rect.left,rect.top,rect.right,rect.bottom)!=(0,0,2560,1440):
        raise Blocked('History coordinates require recorded 2560x1440 geometry; adapt coordinates without changing video settings')
    neutral=initial(d)
    from infra.gameplay import loaded_inputs
    atomic_json(folder/'loaded-inputs.json',loaded_inputs(d.p,identity))
    observations=[];proofs=[];started=time.monotonic()

    def state(s):
        p=s['players'][0];a=allocation(s);n=allocation(neutral)
        return {'native':s,'history':p['history'],'allocation':a,
                'purchased_points':sum(max(0,x-y) for group,original in zip(a,n) for x,y in zip(group,original)),
                'history_bonus':p['groups'][0]['effective'][1]-p['groups'][0]['values'][1],
                'creation_funding':p['groups'][0]['values'][34]}

    def record(name,before,after):
        row={'check':name,'expected':True,'observed':True,'before':before,'after':after,
             'elapsed_seconds':time.monotonic()-started,'source':'offline-native-getter'}
        # First raw transition survives a later failed purchase/audit.
        with (folder/'transition-first-results.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(row)+'\n');f.flush()
        observations.append(row)

    select_history(d,10);sheet(d);first=d.snap(True)
    require(first['players'][0]['history']==78 and state(first)['history_bonus']==1,'Actual bonus History was not selected')
    purchase(d,0,(551,309),'before_repeated_history')
    select_history(d,10);sheet(d);repeat=d.snap(True)
    require(allocation(repeat)==allocation(first) and state(repeat)['history_bonus']==1,'Repeated History accumulated bonus or allocation')
    record('repeat_history_once',state(first),state(repeat))
    purchase(d,0,(551,309),'history_investment');before=d.snap(True)
    gender(d,True);sheet(d);after=d.snap(True)
    atomic_json(folder/'after_history_gender.json',{'before':before,'after':after})
    require(allocation(after)==allocation(neutral) and state(after)['history_bonus']==0 and state(after)['history']==-1,'Non-None gender reset retained allocation or bonus')
    # The category pool is proved by native purchases, never an XP constant.
    collect_pool(d);proof=pool_proof(folder);proofs.append(proof)
    a=state(after);a.update(pool=proof['new_purchases'],native_pool_proof=proof)
    record('non_none_gender',state(before),a)
    first_pool=folder/'pool_after_history';first_pool.mkdir()
    for pattern in ['fresh_pool_*.json','exhausted_*.json','full_pool_returned.json']:
        for file in folder.glob(pattern):file.rename(first_pool/file.name)
    funded=d.snap(True);base(d);sheet(d);returned=d.snap(True)
    require(allocation(funded)==allocation(returned),'Base/Sheet lost allocation')
    record('base_sheet',state(funded),state(returned))
    # This one real transition covers both None and reverse gender; it starts
    # with ten purchases and takes the opposite direction from the first reset.
    before=returned;gender(d,False);sheet(d);after=d.snap(True)
    atomic_json(folder/'after_none_reverse_gender.json',{'before':before,'after':after})
    require(state(before)['history'] in [-1,0] and allocation(after)==allocation(neutral) and state(after)['history_bonus']==0,'None/reverse reset retained allocation')
    collect_pool(d);proof=pool_proof(folder);proofs.append(proof)
    a=state(after);a.update(pool=proof['new_purchases'],native_pool_proof=proof)
    record('none_gender',state(before),a);record('reverse_gender',state(before),a)
    funded=d.snap(True)
    record('fresh_pool',state(after),{**state(funded),'native_pool_proofs':proofs})
    record('exhausted_reject',state(funded),{**state(funded),'native_pool_proofs':proofs})
    d.click(2118,1189);d.click(2120,1387);deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        accepted=d.snap(True)
        if accepted['players'] and state(accepted)['creation_funding']==0:break
        time.sleep(.25)
    else:raise Blocked('Preparation: native Accept completion not observed within 90 seconds')
    require(allocation(accepted)==allocation(funded),'Accept lost new allocation')
    record('accept',state(funded),state(accepted))
    evidence={**identity,'resolved_resources':identity['resources'],'first_result_preserved':True,
              'observations':observations,'metrics':{'new_purchases':proof['new_purchases'],
              'rejected_exhausted_categories':proof['rejected_exhausted_categories'],'history_bonus_applications':state(repeat)['history_bonus']}}
    atomic_json(folder/'observations.json',evidence)
    return {'status':'PASS','scope':'Two bounded opposite gender transitions, actual History/None purchases, both complete pools, rejection, Base/Sheet and Accept'}


if __name__=='__main__':
    folder=Path(sys.argv[1])
    try:result=collect(folder)
    except Blocked as error:result={'status':'BLOCKED','reason':str(error)}
    except Exception as error:result={'status':'FAIL','reason':repr(error)}
    atomic_json(folder/'collector-result.json',result);print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['status']=='PASS' else 75 if result['status']=='BLOCKED' else 1)
