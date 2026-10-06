"""Derive allocation/pool evidence from native snapshots, not an XP constant."""
from infra.core import read_json,require


def allocation(snapshot):
    out=[]
    for group in snapshot['players'][0]['groups'][:3]:
        values=group['values'][:]
        if group['type']==0:values[11]=values[34]=0
        out.append(values)
    return out


def pool_proof(folder):
    purchases=[];rejections=[]
    for i in range(10):
        before=read_json(folder/f'fresh_pool_{i}_before.json');after=read_json(folder/f'fresh_pool_{i}_after.json')
        purchases.append({'before':before,'after':after})
    for i in range(7):
        before=read_json(folder/f'exhausted_{i}_before.json');after=read_json(folder/f'exhausted_{i}_after.json')
        rejections.append({'before':before,'after':after})
    return derive_pool(purchases,rejections)


def derive_pool(purchases,rejections):
    counts=[0,0,0];derived=[];previous=None
    require(len(purchases)==10 and len(rejections)==7,'Missing raw purchase/rejection observations')
    for row in purchases:
        before,after=row['before'],row['after']
        a,b=allocation(before),allocation(after)
        require(len(a)==len(b)==3 and all(len(x)==len(y) for x,y in zip(a,b)),'Native group shape changed')
        require(previous is None or allocation(previous)==a,'Discontinuous native purchasing sequence')
        require(previous is None or previous['players'][0]['groups'][0]['values'][34]==before['players'][0]['groups'][0]['values'][34],'Discontinuous native purchase funding')
        changes=[(kind,index,old,new) for kind in range(3) for index,(old,new) in enumerate(zip(a[kind],b[kind])) if old!=new]
        require(len(changes)==1 and changes[0][3]==changes[0][2]+1,'Native fresh purchase not established')
        kind,index,old,new=changes[0];counts[kind]+=1
        cost=before['players'][0]['groups'][kind]['costs'][str(index)]
        require(isinstance(cost,int) and cost>0,'Native positive purchase cost unavailable')
        require(after['players'][0]['groups'][0]['values'][34]==before['players'][0]['groups'][0]['values'][34]-cost,'Native purchase cost/funding mismatch')
        derived.append({'kind':kind,'index':index,'old':old,'new':new,'cost':cost,'before':before,'after':after})
        previous=after
    require(counts==[3,6,1],'Incomplete new spendable pool')
    for row in rejections:
        before,after=row['before'],row['after']
        require(allocation(previous)==allocation(before),'Rejection does not follow completed pool')
        require(allocation(before)==allocation(after) and before['players'][0]['groups'][0]['values'][34]==after['players'][0]['groups'][0]['values'][34],'Extra purchase was accepted')
    return {'new_purchases':counts,'rejected_exhausted_categories':len(rejections),'purchases':derived,'rejections':rejections}


def validate_pool(proof):
    derived=derive_pool(proof.get('purchases',[]),proof.get('rejections',[]))
    require(proof.get('new_purchases')==derived['new_purchases'] and proof.get('rejected_exhausted_categories')==derived['rejected_exhausted_categories'],'Collector pool summary differs from native observations')
    return derived
