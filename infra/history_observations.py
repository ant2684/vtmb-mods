"""Independent category/pool audit for the recorded neutral-clan workflow.

OS delivery, owned foreground and unchanged stats alone do not prove native UI
rejection. The current collector has no native UI command observer: it records
real click receipts, then reports BLOCKED rather than inventing rejection.
An eventual native observer must supply the action-bound command readback.
"""
import json
import math
import time
import uuid
from infra.core import Blocked,atomic_json,read_json,require,sha

PROFILE='neutral-clan-2-2560x1440-v1'
EXPECTED_CATEGORIES={'physical':2,'social':0,'mental':1,'talents':3,'skills':2,'knowledges':1,'disciplines':1}
PURCHASES=[('physical',0,1,(506,309)),('physical',0,1,(551,309)),('mental',0,7,(1766,309)),
           ('talents',1,1,(460,589)),('talents',1,1,(506,589)),('talents',1,1,(551,589)),
           ('skills',1,5,(1090,589)),('skills',1,5,(1135,589)),('knowledges',1,9,(1720,589)),
           ('disciplines',2,3,(506,880))]
REJECTIONS=[('physical',0,2,(506,363)),('social',0,4,(1135,309)),('mental',0,8,(1766,363)),
            ('talents',1,2,(460,643)),('skills',1,6,(1090,643)),('knowledges',1,10,(1720,643)),
            ('disciplines',2,None,(1135,880))]


def category_for(kind,index):
    require(type(kind) is int and type(index) is int,'Native stat index/group unavailable')
    if kind==0 and 1<=index<=9:return ('physical','social','mental')[(index-1)//3]
    if kind==1 and 1<=index<=12:return ('talents','skills','knowledges')[(index-1)//4]
    if kind==2 and index>0:return 'disciplines'
    require(False,'Target is not a purchaseable attribute/ability/discipline')


def snapshot_sha(snapshot):
    return sha(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode('utf-8'))


def player_identity(snapshot):
    require(len(snapshot.get('players',[]))==1,'Exactly one observed native player required')
    player=snapshot['players'][0]
    require(all(type(player.get(n)) is int for n in ['address','index','serial']),'Native player identity unavailable')
    return {n:player[n] for n in ['address','index','serial']}


def validate_action(row,spec,label,seen):
    action=row.get('action')
    if not isinstance(action,dict):raise Blocked('Action receipt absent; unchanged native stats cannot prove a rejected purchase')
    category,kind,index,coordinates=spec
    require(action.get('profile')==PROFILE and action.get('label')==label,'Wrong action profile/label')
    require(action.get('category')==category and action.get('group')==kind and action.get('stat_index')==index,'Wrong attempted category/stat')
    require(action.get('coordinates')==list(coordinates) and action.get('window_rect')==[0,0,2560,1440],'Unsupported/incorrect click geometry')
    identifier=action.get('id')
    require(isinstance(identifier,str) and bool(identifier) and identifier not in seen,'Duplicate/missing action identity')
    seen.add(identifier)
    before,after=row['before'],row['after']
    require(action.get('before_sha256')==snapshot_sha(before) and action.get('after_sha256')==snapshot_sha(after),'Action binds different native snapshots')
    owned=action.get('owned_process',{})
    require(type(owned.get('Id')) is int and owned['Id']>0 and type(owned.get('Ticks')) is int and owned['Ticks']>0,'Owned process identity unavailable')
    require(before.get('pid')==after.get('pid')==owned['Id'],'Action/snapshot process identity differs')
    require(player_identity(before)==player_identity(after),'Native player changed during purchase attempt')
    require(before['players'][0]['groups'][0]['values'][10]==after['players'][0]['groups'][0]['values'][10]==2,'Receipt belongs to a different native clan profile')
    start,end=action.get('started_ns'),action.get('finished_ns')
    require(type(start) is int and type(end) is int and 0<=start<end,'Action timing unavailable')
    inputs=action.get('inputs',[])
    require(len(inputs)==2 and [event.get('flags') for event in inputs]==[2,4],'One actual mouse-down/up attempt required')
    last=start
    for event in inputs:
        moment=event.get('monotonic_ns');wall=event.get('wall_seconds')
        require(type(moment) is int and last<=moment<=end,'Unordered/out-of-scope physical input')
        require(isinstance(wall,(int,float)) and math.isfinite(wall) and before['wall']<=wall<=after['wall'],'Physical input outside native snapshot interval')
        require(event.get('kind')==0 and event.get('sendinput_requested')==event.get('sendinput_returned')==1,'SendInput delivery unconfirmed')
        require(event.get('foreground_owned_before') is True and event.get('foreground_owned_after') is True,'Owned foreground lost during attempt')
        require(event.get('cursor')==list(coordinates),'Actual cursor differs from requested target')
        last=moment
    return action


def validate_native_rejection(action,row,seen_events):
    native=action.get('native_ui_attempt')
    if not isinstance(native,dict):
        raise Blocked('Native UI command readback unavailable for '+action['category']+'; owned foreground, successful SendInput and unchanged native stats establish an unaccepted click, not actual category-exhausted rejection')
    require(native.get('source')=='native-ui-command-readback' and native.get('action_id')==action['id'],'Native rejection not bound to the actual action')
    require(native.get('pid')==action['owned_process']['Id'] and native.get('player')==player_identity(row['before']),'Native rejection belongs to another process/player')
    event=native.get('event_id')
    require(isinstance(event,str) and bool(event) and event not in seen_events,'Duplicate/missing native UI event')
    seen_events.add(event)
    kind,index=native.get('group'),native.get('stat_index')
    require(kind==action['group'] and category_for(kind,index)==action['category'],'Native UI attempted a different category')
    require(index<len(row['before']['players'][0]['groups'][kind]['values']),'Native UI target outside observed group')
    require(action['stat_index'] is None or index==action['stat_index'],'Native UI attempted a different stat')
    require(native.get('disposition')=='creation-category-exhausted','Native UI did not reject for exhausted category')
    wall=native.get('wall_seconds')
    require(isinstance(wall,(int,float)) and math.isfinite(wall) and action['inputs'][0]['wall_seconds']<=wall<=row['after']['wall'],'Native UI event outside this attempt')


def allocation(snapshot):
    require([group.get('type') for group in snapshot['players'][0]['groups'][:3]]==[0,1,2],'Native attribute/ability/discipline group order unavailable')
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
        receipt=folder/f'fresh_pool_{i}_action.json'
        purchases.append({'before':before,'after':after,'action':read_json(receipt) if receipt.exists() else None})
    for i in range(7):
        before=read_json(folder/f'exhausted_{i}_before.json');after=read_json(folder/f'exhausted_{i}_after.json')
        receipt=folder/f'exhausted_{i}_action.json'
        rejections.append({'before':before,'after':after,'action':read_json(receipt) if receipt.exists() else None})
    return derive_pool(purchases,rejections)


def derive_pool(purchases,rejections):
    counts=[0,0,0];categories={name:0 for name in EXPECTED_CATEGORIES};derived=[];previous=None;seen=set();seen_events=set()
    require(len(purchases)==10 and len(rejections)==7,'Missing raw purchase/rejection observations')
    owner=None;last_action_end=None
    def sequence(action,row):
        nonlocal owner,last_action_end
        identity=(action['owned_process']['Id'],action['owned_process']['Ticks'],player_identity(row['before']))
        require(owner is None or owner==identity,'Pool actions belong to different native process/player identities')
        require(last_action_end is None or last_action_end<=action['started_ns'],'Pool action timing overlaps or is reordered')
        require(previous is None or previous['wall']<=row['before']['wall'],'Native pool snapshots are reordered')
        owner=identity;last_action_end=action['finished_ns']
    for i,row in enumerate(purchases):
        action=validate_action(row,PURCHASES[i],'fresh_pool_'+str(i),seen)
        sequence(action,row)
        before,after=row['before'],row['after']
        a,b=allocation(before),allocation(after)
        require(len(a)==len(b)==3 and all(len(x)==len(y) for x,y in zip(a,b)),'Native group shape changed')
        require(previous is None or allocation(previous)==a,'Discontinuous native purchasing sequence')
        require(previous is None or previous['players'][0]['groups'][0]['values'][34]==before['players'][0]['groups'][0]['values'][34],'Discontinuous native purchase funding')
        changes=[(kind,index,old,new) for kind in range(3) for index,(old,new) in enumerate(zip(a[kind],b[kind])) if old!=new]
        require(len(changes)==1 and changes[0][3]==changes[0][2]+1,'Native fresh purchase not established')
        kind,index,old,new=changes[0];counts[kind]+=1
        category=category_for(kind,index);categories[category]+=1
        require(category==action['category'] and kind==action['group'] and index==action['stat_index'],'Actual purchased stat differs from the intended category/stat')
        cost=before['players'][0]['groups'][kind]['costs'][str(index)]
        require(type(cost) is int and cost>0,'Native positive purchase cost unavailable')
        require(after['players'][0]['groups'][0]['values'][34]==before['players'][0]['groups'][0]['values'][34]-cost,'Native purchase cost/funding mismatch')
        derived.append({'kind':kind,'index':index,'old':old,'new':new,'cost':cost,'before':before,'after':after,'action':action})
        previous=after
    require(counts==[3,6,1] and categories==EXPECTED_CATEGORIES,'Incorrect native category distribution of new purchases')
    rejected=[]
    for i,row in enumerate(rejections):
        action=validate_action(row,REJECTIONS[i],'exhausted_'+str(i),seen)
        sequence(action,row)
        before,after=row['before'],row['after']
        require(allocation(previous)==allocation(before),'Rejection does not follow completed pool')
        require(previous['players'][0]['groups'][0]['values'][34]==before['players'][0]['groups'][0]['values'][34],'Rejection funding does not follow completed pool')
        require(allocation(before)==allocation(after) and before['players'][0]['groups'][0]['values'][34]==after['players'][0]['groups'][0]['values'][34],'Extra purchase was accepted')
        validate_native_rejection(action,row,seen_events)
        rejected.append(action['category']);previous=after
    require(set(rejected)==set(EXPECTED_CATEGORIES) and len(set(rejected))==7,'Seven distinct exhausted categories not established')
    return {'new_purchases':counts,'category_purchases':categories,'rejected_exhausted_categories':len(rejected),'rejected_categories':rejected,'purchases':derived,'rejections':rejections}


def validate_pool(proof):
    derived=derive_pool(proof.get('purchases',[]),proof.get('rejections',[]))
    require(proof.get('new_purchases')==derived['new_purchases'] and proof.get('rejected_exhausted_categories')==derived['rejected_exhausted_categories'],'Collector pool summary differs from native observations')
    for field in ['category_purchases','rejected_categories']:
        require(field not in proof or proof[field]==derived[field],'Collector category summary differs from native observations')
    return derived


def record_action(driver,spec,label,operation):
    """Capture actual physical delivery; never synthesize native UI acceptance."""
    from drive import C,W,u
    owned=read_json(driver.session/'process.json')
    require(driver.p.pid==owned['Id'],'Collector process does not match owned receipt')
    rect=W.RECT();require(bool(u.GetWindowRect(driver.hwnd,C.byref(rect))),'Window geometry unavailable')
    action={'id':uuid.uuid4().hex,'profile':PROFILE,'label':label,'category':spec[0],'group':spec[1],'stat_index':spec[2],
            'coordinates':list(spec[3]),'window_rect':[rect.left,rect.top,rect.right,rect.bottom],
            'owned_process':owned,'started_ns':time.perf_counter_ns(),'inputs':[],
            'native_ui_attempt':None,'scope':'Physical click receipt only; no native UI command rejection observer is implemented'}
    original=driver.send
    def send(event,check=True):
        owner_before=u.GetForegroundWindow()==driver.hwnd
        point=W.POINT();require(bool(u.GetCursorPos(C.byref(point))),'Actual cursor unavailable')
        entry={'kind':int(event.kind),'flags':int(event.value.mi.flags),'cursor':[point.x,point.y],
               'monotonic_ns':time.perf_counter_ns(),'wall_seconds':time.time(),'foreground_owned_before':owner_before,
               'sendinput_requested':1,'sendinput_returned':0}
        action['inputs'].append(entry)
        result=original(event,check)  # Driver.send returns only after SendInput == 1.
        entry['sendinput_returned']=1;entry['foreground_owned_after']=u.GetForegroundWindow()==driver.hwnd
        return result
    driver.send=send
    first_error=None
    try:return operation()
    except BaseException as error:
        first_error=error
        raise
    finally:
        driver.send=original;action['finished_ns']=time.perf_counter_ns()
        try:
            for suffix in ['before','after']:
                path=driver.session/(label+'_'+suffix+'.json')
                if path.exists():action[suffix+'_sha256']=snapshot_sha(read_json(path))
            atomic_json(driver.session/(label+'_action.json'),action)
        except BaseException as receipt_error:
            if first_error is None:raise
            first_error.add_note('Action receipt preservation failed: '+str(receipt_error))


def collect_pool(driver):
    """Recorded ten purchases/seven clicks; actual rejection is audited separately.

    Current capture cannot read native UI dispatch. A complete pool certificate
    therefore remains BLOCKED even if all seven delivered clicks leave stats
    unchanged; the first genuine purchase failure still stops this workflow.
    """
    from gameplay import purchase,reject,base,sheet
    for i,spec in enumerate(PURCHASES):
        label='fresh_pool_'+str(i)
        record_action(driver,spec,label,lambda:purchase(driver,spec[1],spec[3],label))
    for i,spec in enumerate(REJECTIONS):
        label='exhausted_'+str(i)
        record_action(driver,spec,label,lambda:reject(driver,spec[3],label))
    funded=driver.snap(True);base(driver);sheet(driver);returned=driver.snap(True)
    require(allocation(returned)==allocation(funded) and returned['players'][0]['groups'][0]['values'][34]==funded['players'][0]['groups'][0]['values'][34],'Base/Sheet changed new allocation/funding')
    atomic_json(driver.session/'full_pool_returned.json',returned)
    return returned
