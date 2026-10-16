"""Owned-game UI input and read-only native inventory/row observations."""
import ctypes as C
import ctypes.wintypes as W
import json
import os
import re
import struct
import sys
import time
import hashlib
from pathlib import Path
from infra.core import ROOT, Blocked, Failure, require, atomic_json, read_json
sys.path.insert(0,str(ROOT/'infra/common'))
from driver import Driver, u, INPUT, U, MI, KI

def owned_window_texts(pid):
    """Read only windows belonging to the already recorded test process."""
    rows=[];callback=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    u.EnumWindows.argtypes=[callback,W.LPARAM]
    u.EnumChildWindows.argtypes=[W.HWND,callback,W.LPARAM]
    u.GetWindowTextLengthW.argtypes=[W.HWND];u.GetWindowTextLengthW.restype=C.c_int
    u.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
    def record(hwnd,parent):
        owner=W.DWORD();u.GetWindowThreadProcessId(hwnd,C.byref(owner))
        if owner.value!=pid:return True
        length=min(8192,max(0,u.GetWindowTextLengthW(hwnd)))
        value=C.create_unicode_buffer(length+1);u.GetWindowTextW(hwnd,value,length+1)
        rows.append({'hwnd':int(hwnd),'parent':int(parent),'text':value.value})
        return True
    def top(hwnd,param):
        owner=W.DWORD();u.GetWindowThreadProcessId(hwnd,C.byref(owner))
        if owner.value==pid:
            record(hwnd,0);u.EnumChildWindows(hwnd,callback(record),int(hwnd))
        return True
    u.EnumWindows(callback(top),0)
    return rows

class MBI(C.Structure):
    _fields_=[('BaseAddress',C.c_void_p),('AllocationBase',C.c_void_p),('AllocationProtect',W.DWORD),('PartitionId',W.WORD),('RegionSize',C.c_size_t),('State',W.DWORD),('Protect',W.DWORD),('Type',W.DWORD)]

def text(p,address,limit=100):
    if not address:return ''
    return p.read(address,limit).split(b'\0')[0].decode('ascii','replace')

class Control(Driver):
    def __init__(self,folder):
        super().__init__(folder)
        self.game=Path(read_json(self.session/'launch.json')['GameRoot'])
        self.ui_address=None;self.info_address=None;self.dialog_address=None
    def command(self,line,wait=.6,transition=False):
        require('\n' not in line and '\r' not in line,'one bounded console command')
        # A pre-registered task cfg avoids keyboard layout/long command issues.
        (self.game/'Unofficial_Patch/cfg/container_probe.cfg').write_text(line+'\n',encoding='ascii')
        if not self.snap()['console']['visible']:self.toggle(True)
        control=INPUT(1,U(ki=KI(0,0x1d,8,0,0)))
        try:self.send(control);self.key(ord('A'),.03)
        finally:control.value.ki.flags=10;self.send(control,False)
        self.key(0x08,.03)
        # Python evaluation belongs to console submission, not the engine cfg
        # command buffer. Submit Python literally; cfg is for engine commands.
        submitted=line if line.startswith('__import__') else 'exec container_probe.cfg'
        for char in submitted:
            event=INPUT(1,U(ki=KI(0,ord(char),4,0,0)))
            try:self.send(event);self.delay(.008)
            finally:event.value.ki.flags=6;self.send(event,False)
        self.key(0x0d,.03)
        if transition:time.sleep(wait);return
        self.delay(wait)
        if self.snap()['console']['visible']:self.click_x(.35)
        self.delay(.3)
    def click_at(self,x,y):
        self.focus();point=W.POINT(int(x),int(y));require(u.ClientToScreen(self.hwnd,C.byref(point)),'screen coordinate')
        vx,vy,vw,vh=(u.GetSystemMetrics(i) for i in (76,77,78,79))
        self.send(INPUT(0,U(mi=MI(int((point.x-vx)*65535/(vw-1)),int((point.y-vy)*65535/(vh-1)),0,0xc001,0,0))))
        self.delay(.04)
        try:self.send(INPUT(0,U(mi=MI(0,0,0,2,0,0))));self.delay(.06)
        finally:self.send(INPUT(0,U(mi=MI(0,0,0,4,0,0))),False)
        self.delay(.35)
    def click_panel(self,object):
        bounds=self.panel(object)['bounds']
        x1,y1,x2,y2=bounds
        require(x2>x1 and y2>y1,'empty native widget bounds')
        self.click_at((x1+x2)//2,(y1+y2)//2)
    def find_ui(self,info=False,dialog=False):
        p=self.p;c=p.modules['client.dll'];vt,panel_vt=(0x228fdc,0x228fb4) if dialog else (0x24e060,0x24de9c) if info else (0x24a8a0,0x24a6dc)
        secondary=0x170 if dialog else 0x10
        cached=self.dialog_address if dialog else self.info_address if info else self.ui_address
        if cached and p.u(cached)==c+vt:return cached
        from process_reader import k
        k.VirtualQueryEx.argtypes=[W.HANDLE,C.c_void_p,C.POINTER(MBI),C.c_size_t];k.VirtualQueryEx.restype=C.c_size_t
        address=0x10000;found=[];pattern=struct.pack('<I',c+vt);deadline=time.monotonic()+20
        while address<0x80000000:
            require(time.monotonic()<deadline,'UI scan timeout')
            m=MBI()
            if not k.VirtualQueryEx(p.h,address,C.byref(m),C.sizeof(m)):break
            start=int(m.BaseAddress or 0);size=int(m.RegionSize)
            if m.State==0x1000 and (m.Type==0x20000 or (dialog and m.Type==0x1000000 and start<c+0x6e9000 and start+size>c)) and not m.Protect&0x101 and size<0x10000000:
                for off in range(0,size,0x100000):
                    try:raw=p.read(start+off,min(0x100000,size-off))
                    except OSError:continue
                    hit=raw.find(pattern)
                    while hit>=0:
                        a=start+off+hit
                        try:
                            if p.u(a+secondary)==c+panel_vt:found.append(a)
                        except OSError:pass
                        hit=raw.find(pattern,hit+4)
            address=start+size
        require(len(found)==1,'Expected one native UI object: '+str(found))
        if dialog:self.dialog_address=found[0]
        elif info:self.info_address=found[0]
        else:self.ui_address=found[0]
        return found[0]
    def dialog_choices(self):
        a=self.find_ui(dialog=True);p=self.p;active=p.read(a+0x1b4,1)[0];n=p.u(a+0x1228)
        if not active:return {'active':active,'choices':[]}
        # During an NPC line a number key means skip speech (Pick -2),
        # even though the next response strings are already populated.
        if p.read(a+0x1b3,1)[0]:return {'active':active,'choices':[],'npc_speaking':True}
        require(n<=4,'invalid native dialogue choice count')
        choices=[];raws=[]
        for i in range(n):
            raw=p.read(a+0x122c+i*0x800,0x800);raws.append(raw.hex())
            value=raw.decode('utf-16-le','replace').split('\0')[0] if raw[1:2]==b'\0' and raw[2:3]!=b'\0' else raw.split(b'\0')[0].decode('cp1252','replace')
            choices.append(value)
        entities=self.entities();players=[r for r in entities.values() if r['class']=='player']
        require(len(players)==1,'dialogue player missing/ambiguous')
        dialog=p.u(players[0]['address']+0x1d24)
        require(dialog and p.u(dialog+4)==players[0]['handle'],'dialogue PC binding differs')
        npc=entities.get(p.u(dialog));require(npc and npc['name']=='Trip','dialogue is not with the real Trip')
        if p.u(dialog+0x2834)!=n:return {'active':active,'choices':[],'transient_count_mismatch':True}
        return {'active':active,'choices':choices,'raw_hex':raws,'npc':npc,'player':players[0],'line_ids':[p.u(dialog+0x2838+i*4) for i in range(n)]}
    def entities(self):
        p=self.p;sv=p.modules['vampire.dll'];table=p.u(sv+0x566458);raw=p.read(table,8192*12);rows={}
        for idx in range(8192):
            _,ent,serial=struct.unpack_from('<III',raw,idx*12)
            if not ent:continue
            try:
                cls=text(p,p.u(ent+0x11c),70)
                if cls=='player' or cls.startswith(('item_','npc_V')):
                    rows[idx|(serial<<13)]={'address':ent,'class':cls,'name':text(p,p.u(ent+0x26c)),'handle':idx|(serial<<13)}
            except OSError:continue
        return rows
    def state(self):
        p=self.p;entities=self.entities();owners={};all_items=[]
        for handle,row in entities.items():
            if row['class']=='player' or row['class'].startswith(('item_container','npc_V')):
                try:handles=struct.unpack('<224I',p.read(row['address']+0x1624,896))
                except OSError:continue
                inventory=[]
                for slot,h in enumerate(handles):
                    if h==0xffffffff:continue
                    item=entities.get(h)
                    if item:
                        data={**item,'slot':slot,'count':p.u(item['address']+0x8d0),'owner':handle}
                        inventory.append(data);all_items.append(data)
                owners[row['name'] or row['class']]={**row,'inventory':inventory,'money':p.u(row['address']+0x13d8)}
        a=self.find_ui();c=p.modules['client.dll'];table=p.u(c+0x2b8e98);ui={'address':a,'panel':self.panel(a+0x10),'mode_inventory':p.read(a+0x181,1)[0],'action_kind':p.u(a+0x4d4),'category':p.u(a+0x44c),'rows':[]}
        for side,offset,n in [('player',0x188,24),('donor',0x2a8,32)]:
            for index in range(n):
                button=p.u(a+offset+index*12)
                if not button:continue
                h=p.u(button+0xbc)
                if h==0xffffffff:continue
                idx=h&8191;serial=h>>13;ent=p.u(table+idx*12+4)
                if not ent or p.u(table+idx*12+8)!=serial:continue
                ui['rows'].append({'side':side,'index':index,'button':button,'handle':h,'slot':p.u(ent+0x79c),'count':p.u(ent+0x954),'entity':ent,'selected':p.read(button+0xba,1)[0],'ammo_count':p.read(button+0xc4,1)[0],'panel':self.panel(button)})
        button=p.u(a+0x438)
        ui['action']={'button':button,'enabled':bool(p.u(button+0xc0)&2),'panel':self.panel(button)} if button else None
        result={'owners':owners,'items':all_items,'ui':ui,'wall':time.time(),'filter_bytes':p.read(c+0x16dfa4,18).hex(),'price_filter_bytes':p.read(p.modules['vampire.dll']+0xda3cb,6).hex()}
        if 'Trip' in owners:
            sv=p.modules['vampire.dll'];n=p.u(sv+0x74f018);table=p.u(sv+0x74f01c)
            require(0<n<1000,'invalid authored vendor table');records=[]
            for index in range(n):
                record=p.u(table+4*index)
                require(p.u(record+0x1c)<n,'unsupported sparse vendor records')
                name=text(p,p.u(record+0xc));length=p.u(record+0x14);items=p.u(record+0x18)
                require(length<1000,'invalid authored vendor list');classes=[]
                for k in range(length):
                    item=p.u(items+k*4);require(p.u(item)<length,'unsupported sparse vendor item records')
                    classes.append(text(p,p.u(item+4)))
                require(len({p.u(p.u(items+k*4)) for k in range(length)})==length,'duplicate vendor item ordinals')
                records.append({'name':name,'classes':classes,'address':record})
            require(len({p.u(p.u(table+4*k)+0x1c) for k in range(n)})==n,'duplicate vendor ordinals')
            matches=[r for r in records if r['name']=='Trip'];require(len(matches)==1,'Trip authored stock missing/ambiguous')
            authored='item_w_knife' in matches[0]['classes']
            result['vendor_policy']={'vendor':'Trip','class':'item_w_knife','authored':authored,'expected_buy_delta':0 if authored else -1,'records':records}
        return result
    def capture(self,label):
        s=self.state();atomic_json(self.session/('container-'+label+'.json'),s);print(label,json.dumps({'owners':{k:[(i['class'],i['count'],i['slot']) for i in v['inventory']] for k,v in s['owners'].items() if k in ['player','haven_refrigerator','Trip']},'ui':s['ui']}),flush=True);return s

def collect(folder):
    identity=read_json(folder/'identity.json');deadline=time.monotonic()+55
    while True:
        try:
            d=Control(folder);state=d.snap()
            ready=state['viewport_route']['player'] and state['client_time']>0 and any(r['name']=='haven_refrigerator' for r in d.entities().values())
            if ready:break
            from process_reader import k
            k.CloseHandle(d.p.h)
            if time.monotonic()>deadline:raise Blocked('Nominated map/player never became ready')
            time.sleep(.5)
        except (OSError,RuntimeError,AssertionError,KeyError):
            if time.monotonic()>deadline:raise
            time.sleep(.5)
    from infra.gameplay import loaded_inputs
    atomic_json(folder/'loaded-inputs.json',loaded_inputs(d.p,identity))
    if d.snap()['console']['visible']:d.click_x(.35)
    if d.snap()['menu']['visible']:d.key(0x1b);d.delay(.5)
    d.delay(1);d.command('developer 0')
    baseline=identity['scenario']=='container.baseline'
    narrow=identity['scenario']=='container.transfer'
    snapshots={};actions=[];checks={};reload_receipt=None
    def ready(name,timeout=55,predicate=None):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            try:
                snap=d.snap();entities=d.entities()
                if snap['viewport_route']['player'] and snap['client_time']>0 and any(r['name']==name for r in entities.values()) and (predicate is None or predicate()):
                    d.hwnd=d.p.window()
                    # The controlled load/map transition may replace Valve001.
                    # Reacquire this same owned process once, then guard input.
                    u.ShowWindow(d.hwnd,9);u.SetForegroundWindow(d.hwnd)
                    d.focus()
                    if snap['console']['visible']:d.click_x(.35)
                    if d.snap()['menu']['visible']:d.key(0x1b)
                    d.delay(.5);return snap
            except (OSError,RuntimeError,AssertionError,KeyError):pass
            time.sleep(.25)
        raise Failure('Native map/player readiness timeout: '+name)
    def capture(label):
        state=d.capture(label);snapshots[label]=state
        atomic_json(folder/'container-trace.json',{'states':snapshots,'actions':actions})
        return state
    def close():
        if d.state()['ui']['panel']['visible']:d.key(0x1b);d.delay(.4)
    def open_fridge():
        close();d.key(ord(d.bindings.get('+use','e').upper()));d.delay(.5)
        require(d.state()['ui']['panel']['visible']==1,'refrigerator UI did not open')
    def row_for(state,cls,side='donor',owner='haven_refrigerator'):
        slots=[i['slot'] for i in state['owners'].get(owner,{}).get('inventory',[]) if i['class']==cls]
        rows=[r for r in state['ui']['rows'] if r['side']==side and r['slot'] in slots and r['panel']['visible']]
        require(len(rows)==1,'Expected visible '+side+' '+cls+' row: '+str(rows));return rows[0]
    def select(cls,side='donor',owner='haven_refrigerator'):
        for attempt in range(6):
            state=d.state()
            try:row=row_for(state,cls,side,owner);break
            except Failure:
                if side!='player' or attempt==5:raise
                # The left pane has native categories; cycle its real button.
                d.click_panel(d.p.u(state['ui']['address']+0x444))
        if row['selected']==1:return state
        d.click_panel(row['button']);state=d.state()
        require(row_for(state,cls,side,owner)['selected']==1,'native row selection missing');return state
    def transfer(cls,label,side='donor',owner='haven_refrigerator'):
        before=select(cls,side,owner);actions.append({'label':label,'kind':'native-ui-click','before':before,'class':cls,'side':side})
        d.click_panel(before['ui']['action']['button']);d.delay(.4);return capture(label)
    def fixture(line):
        close();d.command(line,.8)
    def pair(name,before,after):
        checks[name]={'check':name,'expected':True,'observed':True,'before':snapshots[before],'after':snapshots[after],'elapsed_seconds':max(0,snapshots[after]['wall']-snapshots[before]['wall']),'source':'native-process-read'}
    open_fridge();capture('opened')
    transfer('item_w_knife','taken-one')
    open_fridge();capture('reopened')
    if baseline:
        transfer('item_w_knife','returned-one','player','player')
        pair('reproduction','opened','returned-one')
    else:
        transfer('item_w_knife','taken-two')
        transfer('item_w_knife','returned-first','player','player')
        if not narrow:
            # Save with one knife at each owner, then reload this task-owned save.
            close();d.command('save rc_container_state',1)
            saved=d.game/'Unofficial_Patch/save/rc_container_state.sav'
            require(saved.is_file() and saved.stat().st_size>0,'task save was not created')
            data=saved.read_bytes();save_hash=hashlib.sha256(data).hexdigest().upper()
            open_fridge();transfer('item_w_knife','reload-dirty','player','player');close()
            old_player=d.snap()['player_handle']
            d.command('load rc_container_state',.3,transition=True);d.ui_address=None;d.player=None
            ready('haven_refrigerator',predicate=lambda:d.snap()['player_handle']!=old_player)
            open_fridge();capture('reloaded')
            require(saved.read_bytes()==data,'task save changed during load')
            reload_receipt={'save_sha256':save_hash,'size':len(data),'saved':snapshots['returned-first'],'dirty':snapshots['reload-dirty'],'loaded':snapshots['reloaded'],'save_stem':'rc_container_state','ready':True}
        transfer('item_w_knife','returned-two','player','player')
        pair('transfer','opened','returned-two');pair('reopen','taken-one','reopened')
        if not narrow:pair('reload','returned-first','reloaded')
        fixture("__import__('__main__').FindPlayer().GiveItem('item_w_knife')")
        fixture("__import__('__main__').FindPlayer().GiveAmmo('item_w_knife',9)")
        open_fridge();capture('cap-ready')
        require(sum(i['count'] for i in snapshots['cap-ready']['owners']['player']['inventory'] if i['class']=='item_w_knife')==10,'full-stack fixture did not create ten knives')
        select('item_w_knife');capture('cap-selected')
        d.click_panel(d.state()['ui']['action']['button']);capture('cap-rejected')
        transfer('item_w_knife','cap-freed','player','player')
        select('item_w_knife');capture('capacity-available')
        transfer('item_w_knife','cap-refilled');pair('cap','cap-ready','cap-refilled')
        if narrow:
            evidence={**identity,'first_result_preserved':True,'resolved_resources':identity['resources'],'observations':list(checks.values()),'metrics':{},'states':snapshots,'actions':actions}
            from mods.container.tests.audit import audit
            audit(evidence);atomic_json(folder/'observations.json',evidence)
            return {'status':'PASS','scope':'container.transfer only; broader regression remains required'}
        transfer('item_g_bloodpack','blood-one')
        open_fridge();capture('blood-reopened')
        transfer('item_g_bloodpack','blood-two')
        transfer('item_g_bloodpack','blood-returned-one','player','player')
        transfer('item_g_bloodpack','blood-returned-two','player','player')
        pair('other_stack','cap-refilled','blood-returned-two')
    # Baseline and fixed use identical native fixtures for unaffected paths.
    fixture("__import__('__main__').FindPlayer().GiveItem('item_w_sledgehammer')")
    fixture('ent_fire haven_refrigerator SpawnItemInContainer item_w_sledgehammer')
    fixture("__import__('__main__').FindPlayer().GiveItem('item_w_thirtyeight')")
    fixture('ent_fire haven_refrigerator SpawnItemInContainer item_w_thirtyeight')
    open_fridge();capture('controls');pair('nonstack','controls','controls');pair('ammo','controls','controls')
    # Real Trip and his original dialogue execute StartBarter through the
    # native client response command, which supplies the server player context.
    close();d.command('changelevel sm_pawnshop_2',.3,transition=True)
    d.ui_address=None;d.player=None
    ready('Trip');capture('shop-loaded')
    d.command("__import__('__main__').G.Story_State=1",.2)
    d.command("__import__('__main__').G.Trip_Drugs=0",.2)
    if not baseline:
        d.command("__import__('__main__').FindPlayer().GiveItem('item_w_knife')",.2)
        d.command("__import__('__main__').FindPlayer().GiveAmmo('item_w_knife',9)",.2)
    context_path=folder/'python-trade.txt'
    d.command("__import__('__builtin__').open("+repr(str(context_path))+",'w').write(str((__import__('__main__').G.Story_State,__import__('__main__').G.Trip_Drugs)))",.5)
    require(context_path.is_file(),'native story/discount receipt missing')
    d.command("__import__('__main__').FindPlayer().MoneyAdd(5000)",.5)
    d.command("__import__('__main__').FindEntityByName('Trip').StartPlayerDialogRemote()",.3)
    dialogue=[];end=time.monotonic()+50;chosen=False;intro_done=False;last_lines=None
    while time.monotonic()<end:
        if d.state()['ui']['panel']['visible']:
            require(chosen,'barter appeared without a recorded dialogue choice');break
        if chosen:
            d.delay(.25);continue
        choices=d.dialog_choices()
        matches=[i for i,v in enumerate(choices['choices']) if re.search(r"buy something|gold for your goods",v,re.I)]
        signature=tuple(choices.get('line_ids',[]))
        if signature==last_lines:
            d.delay(.25);continue
        if not intro_done and signature==(2,):
            dialogue.append({**choices,'chosen_index':0,'role':'intro'})
            atomic_json(folder/'trade-dialogue.json',dialogue)
            d.key(ord('1'));intro_done=True;last_lines=signature
            d.delay(.5);continue
        if matches and not chosen:
            require(len(matches)==1 and matches[0]<10,'ambiguous native buy response')
            index=matches[0];dialogue.append({**choices,'chosen_index':index,'role':'buy'})
            atomic_json(folder/'trade-dialogue.json',dialogue)
            d.key(ord(str((index+1)%10)));chosen=True;last_lines=signature
        d.delay(.25)
    else:raise Failure('Native Trip dialogue did not open barter')
    capture('shop-opened')
    def trade(side,label):
        owner='Trip' if side=='donor' else 'player'
        before=select('item_w_knife',side,owner)
        info=d.find_ui(info=True);p=d.p;c=p.modules['client.dll'];length=p.u(info+0x298);capacity=p.u(info+0x29c);buffer=p.u(info+0x2a0)
        require(0<length<=capacity<100000,'invalid native quote buffer')
        raw=p.read(buffer,length);matches=re.findall(rb'Value:\s*\$([0-9]+)',raw)
        require(len(matches)==1,'missing/ambiguous displayed price: '+repr(raw))
        selected=row_for(before,'item_w_knife',side,owner)
        require(p.u(c+0x5fb7e8)==selected['entity'] and p.read(c+0x5fb7e4,1)==b'\0','quote belongs to another item/ammo')
        quote={'price':int(matches[0]),'text_hex':raw.hex(),'selected':selected,'selected_global':p.u(c+0x5fb7e8),'ammo_flag':p.read(c+0x5fb7e4,1)[0],'action_kind':before['ui']['action_kind'],'direction':'buy' if side=='donor' else 'sell','before':before}
        actions.append({'label':label,'kind':'native-ui-click','class':'item_w_knife','side':side,'quote':quote,'before':before})
        d.click_panel(before['ui']['action']['button']);capture(label)
    if baseline:
        trade('donor','reference-bought-one')
        trade('player','reference-sold-one')
        trade('donor','reference-bought-two')
        trade('player','reference-sold-two')
        pair('trade_reference','shop-opened','reference-sold-two')
    else:
        select('item_w_knife','donor','Trip');capture('shop-cap-selected')
        d.click_panel(d.state()['ui']['action']['button']);capture('shop-cap-rejected')
        trade('player','shop-sold-one')
        trade('donor','shop-bought-one')
        trade('player','shop-sold-two')
        trade('player','shop-sold-three')
        trade('donor','shop-bought-two')
        trade('donor','shop-bought-three')
        pair('trade','shop-opened','shop-bought-three')
    evidence={**identity,'scenario_version':identity['scenario_version'],'first_result_preserved':True,'resolved_resources':identity['resources'],'observations':[checks['reproduction'],checks['trade_reference']] if baseline else list(checks.values()),'metrics':{},'states':snapshots,'actions':actions}
    evidence['shop_context']=context_path.read_text()
    evidence['trade_fixture']={'class':'npc_VDialogPedestrian','name':'Trip','arguments':[1,0,0],'map':'sm_pawnshop_2','spawned':False,'dialogue':dialogue}
    if reload_receipt:evidence['reload_receipt']=reload_receipt
    from mods.container.tests.audit import audit
    if not baseline:
        proof=read_json(os.environ['VTMB_CONTAINER_BASELINE'])
        audit(proof)
        evidence['baseline_controls']={'evidence':proof}
    audit(evidence)
    atomic_json(folder/'observations.json',evidence)
    return {'status':'PASS','scope':identity['scenario']}

if __name__=='__main__':
    folder=Path(sys.argv[1])
    try:r=collect(folder)
    except Blocked as e:r={'status':'BLOCKED','reason':str(e)}
    except Exception as e:
        import traceback
        traceback.print_exc();r={'status':'FAIL','reason':repr(e)}
        try:atomic_json(folder/'failure-windows.json',owned_window_texts(read_json(folder/'process.json')['Id']))
        except Exception as diagnostic:r['window_diagnostic_error']=repr(diagnostic)
    atomic_json(folder/'collector-result.json',r);print(json.dumps(r),flush=True);raise SystemExit(0 if r.get('status')=='PASS' else 1)
