"""Two fresh gender resets with native allocation/funding/entity observations."""
import json
import sys
import time
from pathlib import Path
from infra.core import ROOT, Blocked, Failure, atomic_json, read_json, require


def collect(folder):
    sys.path.insert(0,str(ROOT/'mods/history/tests'))
    from drive import Driver,W,u,C
    from gender_regression import initial,allocation
    from gender_regression import full_pool
    from gameplay import gender,sheet,purchase
    identity=read_json(folder/'identity.json');d=Driver(folder)
    rect=W.RECT();u.GetWindowRect(d.hwnd,C.byref(rect))
    if (rect.left,rect.top,rect.right,rect.bottom)!=(0,0,2560,1440):
        raise Blocked('History coordinates support only the recorded 2560x1440 geometry; preserve video settings and adapt coordinates first')
    neutral=initial(d)
    from infra.gameplay import loaded_inputs
    atomic_json(folder/'loaded-inputs.json',loaded_inputs(d.p,identity))
    funding=neutral['players'][0]['groups'][0]['values'][34];counts=[];transitions=[]
    for i,female in enumerate([True,False]):
        before,change,cost=purchase(d,0,(506,309),'bounded_purchase_'+str(i))
        started=time.monotonic();gender(d,female);sheet(d);after=d.snap(True)
        row={'iteration':i,'before':before,'after':after,'cost':cost,'change':change,'elapsed_seconds':time.monotonic()-started}
        with (folder/'bounded-first-results.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n');f.flush()
        require(allocation(after)==allocation(neutral),'Gender reset retained a purchase')
        require(after['players'][0]['history']==-1 and after['players'][0]['groups'][0]['values'][34]>0,'History/funding reset unavailable')
        counts.append(after['occupied_entity_slots']);transitions.append(row)
    before=transitions[0]['before'];after=transitions[-1]['after']
    # Stock XP need not return to 9000. The user requires a complete spendable
    # category pool, established by ten purchases and seven rejected extras.
    try:
        full_pool(d)
    except Exception as error:
        # Preserve the original failure. A delayed diagnostic click cannot
        # certify the first input or turn this scenario into a success.
        atomic_json(folder/'first-pool-failure.json',{'status':'FAIL','reason':repr(error)})
        if (folder/'fresh_pool_0_after.json').exists():
            d.record('pool_first_failure',True)
            time.sleep(2)
            before_retry=d.snap(True)
            d.click(506,309,.5)
            after_retry=d.snap(True)
            atomic_json(folder/'pool-diagnostic-retry.json',{'original_status':'FAIL','before':before_retry,'after':after_retry,'delay_seconds':2,'scope':'One diagnostic retry only; does not replace the original first-input result'})
            d.record('pool_diagnostic_retry',True)
        raise
    from infra.history_observations import pool_proof
    proof=pool_proof(folder);atomic_json(folder/'native-pool-proof.json',proof)
    a={'native':before,'allocation':allocation(before),'funding':before['players'][0]['groups'][0]['values'][34]}
    b={'native':after,'allocation':allocation(after),'funding':after['players'][0]['groups'][0]['values'][34],'neutral_allocation':allocation(neutral),'native_pool_proof':proof}
    observations=[{'check':name,'expected':True,'observed':True,'before':a,'after':b,'elapsed_seconds':sum(r['elapsed_seconds'] for r in transitions),'source':'offline-native-getter'} for name in ['allocation_reset','pool_reset','entity_budget']]
    evidence={**identity,'resolved_resources':identity['resources'],'first_result_preserved':True,'observations':observations,
              'metrics':{'entity_slots':counts,'scanned_handle_table_slots':8192,'declared_resets':2,'initial_entity_slots':neutral['occupied_entity_slots'],'new_purchases':proof['new_purchases'],'rejected_exhausted_categories':proof['rejected_exhausted_categories']}}
    atomic_json(folder/'observations.json',evidence)
    return {'status':'PASS','scope':'Exactly two forward/reverse resets, complete fresh category pool and rejected extras; no unlimited reset claim','entity_slots':counts}


if __name__=='__main__':
    folder=Path(sys.argv[1])
    try:result=collect(folder)
    except Blocked as error:result={'status':'BLOCKED','reason':str(error)}
    except Exception as error:result={'status':'FAIL','reason':repr(error)}
    atomic_json(folder/'collector-result.json',result);print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['status']=='PASS' else 75 if result['status']=='BLOCKED' else 1)
