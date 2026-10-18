"""External transition recorder: owned PID, physical input, clean plugin.

The complete scenario runs automatically. --interactive-debug consumes numbered
actions in OUTPUT/control.json for diagnosis only; every action is recorded.
The nominated tutorial save is copied; no apartment save substitutes for entry.
"""
import argparse
import ctypes as C
import json
import math
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path
from PIL import ImageGrab

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'infra/common').is_dir())
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from infra.core import atomic_json,digest,read_json,require
from infra.session import Transaction
from infra.gameplay import windows,preserve_session
from startup_gameplay import StartupProbe, radio, advancing
from infra.container_gameplay import Control
from probe import k,u,INPUT,U,MI


class TransitionProbe(StartupProbe):
    def command(self,text):
        require(text in ['save rc_startup_on','load rc_startup_on','map hw_redspot_1','bind F11 pause','unbind F11'],'Unregistered transition command')
        if not self.console():self.key(0x29);time.sleep(.5)
        require(self.console(),'Console did not open')
        try:self.send(0x1d,8);self.key(0x1e)
        finally:self.send(0x1d,10,False)
        self.key(0x0e)
        for char in text:
            try:self.send(ord(char),4);time.sleep(.025)
            finally:self.send(ord(char),6,False)
        self.key(0x1c);time.sleep(.7)
        if self.console():self.key(0x29)

    def mouse(self,dx,dy):
        self.focus();event=INPUT(0,U(mi=MI(dx,dy,0,1,0,0)))
        require(u.SendInput(1,C.byref(event),C.sizeof(event))==1,'Mouse event rejected');time.sleep(.25)

    def origin(self,entity):return struct.unpack('<3f',self.p.read(entity+0x404,12))

    def orient(self,yaw,pitch):
        def angles():return struct.unpack('<3f',self.p.read(self.p.modules['engine.dll']+0x314868,12))
        for axis,target in [(1,yaw),(0,pitch)]:
            before=angles();self.mouse(50 if axis==1 else 0,50 if axis==0 else 0);after=angles()
            scale=((after[axis]-before[axis]+180)%360-180)/50
            require(.001<abs(scale)<2,'Mouse input unavailable')
            for _ in range(60):
                error=(target-angles()[axis]+180)%360-180
                if abs(error)<.5:break
                count=max(-100,min(100,round(error/scale)))
                self.mouse(count if axis==1 else 0,count if axis==0 else 0)
            require(abs((target-angles()[axis]+180)%360-180)<1,'Aim did not converge')
        return angles()

    def approach(self,target,height=8,walk=True,finish_aim=True):
        player=next(x for x in self.entities() if x['class']=='player')
        origin=self.origin(player['entity']);delta=[target[i]-origin[i] for i in range(3)]
        yaw=math.degrees(math.atan2(delta[1],delta[0]));distance=math.hypot(*delta[:2])
        self.orient(yaw,0)
        if walk and distance>65:
            try:self.send(0x11,8);time.sleep(min(1.5,(distance-65)/190))
            finally:self.send(0x11,10,False)
            time.sleep(.4)
        if not finish_aim:return {'player':self.origin(player['entity']),'target':target}
        origin=self.origin(player['entity']);delta=[target[i]-origin[i] for i in range(3)];delta[2]+=height-64
        aim=self.orient(math.degrees(math.atan2(delta[1],delta[0])),-math.degrees(math.atan2(delta[2],math.hypot(*delta[:2]))))
        return {'player':origin,'target':target,'aim':aim}

    def aim_radio(self):
        radio=next(x for x in self.entities() if x['class']=='prop_radio')
        return self.approach(self.origin(radio['entity']))

    def approach_jack(self):
        table=self.p.u(self.p.modules['vampire.dll']+0x566458)
        for i in range(8192):
            entity=self.p.u(table+i*12+4)
            if entity and self.string(self.p.u(entity+0x26c),80)=='Jack':
                return self.approach(self.origin(entity),64,finish_aim=False)
        raise RuntimeError('Jack not found')

    def dialogue_state(self):
        for name in ['dialog_address','ui_address','info_address']:
            if not hasattr(self,name):setattr(self,name,None)
        a=Control.find_ui(self,dialog=True);p=self.p
        active=p.read(a+0x1b4,1)[0]
        if not active:return {'active':False,'choices':[]}
        if p.read(a+0x1b3,1)[0]:return {'active':True,'npc_speaking':True,'choices':[]}
        n=p.u(a+0x1228);require(n<=4,'Unsupported dialogue response count')
        choices=[]
        for i in range(n):
            raw=p.read(a+0x122c+i*0x800,0x800)
            choices.append(raw.decode('utf-16-le','replace').split('\0')[0] if raw[1:2]==b'\0' and raw[2:3]!=b'\0' else raw.split(b'\0')[0].decode('cp1252','replace'))
        player=next(e for e in self.entities() if e['class']=='player');dialog=p.u(player['entity']+0x1d24)
        require(dialog and p.u(dialog+4)==player['idx']|(player['serial']<<13),'Dialogue player binding differs')
        handle=p.u(dialog);table=p.u(p.modules['vampire.dll']+0x566458)
        npc=p.u(table+(handle&8191)*12+4);serial=p.u(table+(handle&8191)*12+8)
        require(npc and serial==handle>>13 and self.string(p.u(npc+0x26c),80)=='Jack','Dialogue is not with Jack')
        if p.u(dialog+0x2834)!=n:return {'active':True,'choices':[]}
        return {'active':True,'choices':choices,'line_ids':[p.u(dialog+0x2838+i*4) for i in range(n)]}

    def tutorial_dialogue(self):
        self.approach_jack();end=time.monotonic()+45;last=None;selected=[];last_pick=0;last_observed=None;attempts={}
        with (self.session/'tutorial-dialogue.jsonl').open('x') as out:
            while time.monotonic()<end:
                if any(e['class']=='prop_radio' for e in self.entities()):
                    require(selected==[12,26,1027,1033] or selected==[12,26,1027,1032],'Unexpected tutorial route: '+str(selected))
                    return selected
                state=self.dialogue_state();choice=None
                if state!=last_observed:
                    out.write(json.dumps({'qpc':time.perf_counter(),'kind':'observed_state','state':state})+'\n');out.flush();last_observed=state
                if state.get('npc_speaking'):
                    self.key(0x02);kind='skip_npc_speech'
                elif state['choices'] and (tuple(state['line_ids'])!=last or time.monotonic()-last_pick>1):
                    if len(state['choices'])==1:choice=0
                    else:
                        require(len(state['choices'])==4 and state['line_ids'][3] in [26,1027],'Unexpected Jack choices: '+str(state))
                        choice=3
                    signature=tuple(state['line_ids']);attempts[signature]=attempts.get(signature,0)+1;require(attempts[signature]<=3,'Dialogue input not accepted: '+str(state))
                    if signature!=last:selected.append(state['line_ids'][choice])
                    last=signature;last_pick=time.monotonic();self.key(0x02+choice);kind='pick_response'
                elif not state['active'] and not selected:
                    self.key(0x12);kind='talk'
                else:time.sleep(.1);continue
                out.write(json.dumps({'qpc':time.perf_counter(),'kind':kind,'state':state,'chosen_index':choice})+'\n');out.flush();time.sleep(.15)
        self.focus();ImageGrab.grab().save(self.session/'dialogue-timeout.png')
        raise RuntimeError('Tutorial dialogue/transition timed out')


def plugin_state(probe,symbols):
    p=probe.p;base=p.modules['subtitle-pause-fix.vtm'];syms=symbols['symbols'];rows=[]
    raw=p.read(base+syms['_radios'],32*symbols['stride'])
    for n in range(32):
        b=raw[n*symbols['stride']:(n+1)*symbols['stride']]
        entity,channel,source,mixer,sfx=struct.unpack_from('<5I',b)
        if not entity:continue
        index,serial,generation,activation=struct.unpack_from('<4I',b,20)
        epoch,off_time=struct.unpack_from('<2d',b,40)
        epoch_valid,off_position,off_rate,seen_on,armed=struct.unpack_from('<5i',b,56)
        rows.append(dict(entity=entity,channel=channel,source=source,mixer=mixer,sfx=sfx,index=index,serial=serial,
            generation=generation,activation=activation,epoch=epoch,off_time=off_time,epoch_valid=epoch_valid,
            off_position=off_position,off_rate=off_rate,seen_on=seen_on,armed=armed,initial_pending=struct.unpack_from('<i',b,100)[0],raw=b.hex()))
    return rows


def sample(probe,symbols):
    r=probe.snap();p=probe.p;e=p.modules['engine.dll']
    r['view_angles']=struct.unpack('<3f',p.read(e+0x314868,12))
    for entity in r['entities']:
        if entity['class']=='prop_radio':
            entity['active']=p.read(entity['entity']+0x734,1)[0]
            entity['origin']=struct.unpack('<3f',p.read(entity['entity']+0x404,12))
    r['plugin_radios']=plugin_state(probe,symbols);return r


def prepare(tx,game,maps):
    # All operations below are read-only game preservation. Persist the complete
    # snapshot once, before ANY game mutation or launch. Recovery during this
    # phase has no gameplay writes to undo. Normal durable journaling resumes.
    save=tx.save;tx.save=lambda:None
    try:
        for directory in ['Bin/loader','Unofficial_Patch/cfg','Vampire/cfg','Unofficial_Patch/save','Vampire/save','Unofficial_Patch/python','Vampire/python','Unofficial_Patch/maps/graphs','Vampire/maps/graphs']:
            for p in (game/directory).rglob('*'):
                if p.is_file():
                    rel=p.relative_to(game).as_posix();tx.preserve(rel)
                    if not directory.startswith('Bin/'):tx.allow_runtime(rel)
        for mod in ['','Vampire','Unofficial_Patch']:
            for p in (game/mod).glob('*'):
                if p.is_file() and p.suffix.lower() in ['.cfg','.log','.txt','.inf']:tx.allow_runtime(p.relative_to(game).as_posix())
        for mod in ['Vampire','Unofficial_Patch']:
            for source in (game/mod/'python').rglob('*.py'):
                for ext in ['.pyc','.pyo']:tx.allow_runtime(source.with_suffix(ext).relative_to(game).as_posix())
            for name in ['console.log','logs/console.log','maps/graphs/.loc']:tx.allow_runtime(mod+'/'+name)
            for name in maps:
                for n in range(1,4):tx.allow_runtime(f'{mod}/save/{name}.HL{n}')
                for ext in ['loc','ain']:tx.allow_runtime(f'{mod}/maps/graphs/{name}.{ext}')
        for suffix in ['',*['%02d'%n for n in range(10)]]:tx.allow_runtime('Unofficial_Patch/save/autosave'+suffix+'.sav')
        tx.allow_runtime('Unofficial_Patch/save/rc_startup_on.sav');tx.allow_runtime('console.log')
    finally:tx.save=save;tx.save()


def automatic_scenario(probe,symbols,opt,folder,boundary):
    def state():return sample(probe,symbols)
    def record(label,seconds=1,audible=None):
        rows=[];start=time.perf_counter()
        with (folder/(label+'.jsonl')).open('x') as out:
            while True:
                row=state();rows.append(row);out.write(json.dumps(row)+'\n');out.flush()
                if time.perf_counter()-start>=seconds:break
                time.sleep(.08)
        if audible is not None:advancing(rows,audible)
        boundary(label);print('PHASE',label,flush=True);return rows
    def wait_radio(previous=None):
        end=time.monotonic()+40
        while time.monotonic()<end:
            try:
                row=state();entity,channel=radio(row);player=next(e for e in row['entities'] if e['class']=='player')
                if not row['server_paused'] and not probe.console() and (previous is None or (player['entity'],player['serial'])!=previous):
                    if row['plugin_radios'] and row['plugin_radios'][0]['initial_pending'] in [0,2]:return row
            except (OSError,RuntimeError,AssertionError,StopIteration):pass
            time.sleep(.15)
        raise RuntimeError('Expected radio stream did not become ready')
    def capture(label):
        require(opt.capture is not None,'Process audio helper required');wave=folder/(label+'.wav')
        start=time.perf_counter();result=subprocess.run([str(opt.capture.resolve()),str(probe.owned['Id']),str(probe.owned['Ticks']),str(wave),'6'],capture_output=True,text=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        (folder/(label+'-capture.txt')).write_text(result.stdout+result.stderr);require(result.returncode==0,'Process PCM failed')
        # Continuous external trace covers every process PCM packet timestamp.
        record(label,1,True);print('AUDIO',label,'since',start,flush=True)
    def use(label,audible):
        before=state();probe.key(0x12);rows=record(label,2,audible)
        with (folder/'physical-use.jsonl').open('a') as out:out.write(json.dumps({'label':label,'before':before,'after':rows[-1]})+'\n')
    probe.tutorial_dialogue();wait_radio();record('apartment_initial_off',2,False)
    probe.aim_radio();use('apartment_first_use',True);capture('apartment_first_audio')
    use('apartment_second_use',False);use('apartment_third_use',True);capture('apartment_repeat_audio')
    probe.command('save rc_startup_on');time.sleep(.5);before=state();serial=next((e['entity'],e['serial']) for e in before['entities'] if e['class']=='player')
    probe.command('load rc_startup_on');wait_radio(serial);record('apartment_loaded_on',2,True);capture('apartment_loaded_audio')
    probe.command('map hw_redspot_1');wait_radio();record('redspot_initial_on',3,True)
    capture('redspot_initial_audio');probe.command('bind F11 pause');probe.key(0x57);time.sleep(.4)
    paused=record('redspot_paused',3);require(all(r['paused']==r['server_paused']==1 for r in paused),'Ordinary pause absent')
    require(max(radio(r)[1]['sample_position'] for r in paused)-min(radio(r)[1]['sample_position'] for r in paused)<=2048,'Paused decoder advanced')
    require(len({radio(r)[1]['caption_index'] for r in paused})==1,'Paused caption advanced')
    probe.key(0x57);record('redspot_resumed',2,True);capture('redspot_resumed_audio')
    probe.aim_radio();use('redspot_off',False);use('redspot_on',True);capture('redspot_repeat_audio');probe.command('unbind F11')


def main():
    a=argparse.ArgumentParser();a.add_argument('--config',type=Path,required=True);a.add_argument('--save',type=Path,required=True)
    a.add_argument('--plugin',type=Path,required=True);a.add_argument('--symbols',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--capture',type=Path);a.add_argument('--automatic',action='store_true',default=True);a.add_argument('--interactive-debug',dest='automatic',action='store_false')
    opt=a.parse_args();config=read_json(opt.config);game=Path(config['game_root']).resolve();symbols=read_json(opt.symbols)
    require(digest(opt.plugin)==symbols['sha256'],'Symbol addresses belong to a different binary')
    opt.output.mkdir(parents=True,exist_ok=False);windows(config,'Inspect',opt.output)
    require(not read_json(opt.output/'settings-current.json')['Processes'],'User game running')
    require(not(game/'Unofficial_Patch/save/rc_startup_on.sav').exists(),'Control save name occupied')
    tx=Transaction(game,opt.output/'transaction');folder=tx.start();probe=None;stop=threading.Event();thread=None
    try:
        windows(config,'Inspect',folder);atomic_json(folder/'settings.json',read_json(folder/'settings-current.json'));tx.watch_inventory()
        prepare(tx,game,['sp_genesisdevice_1','sp_theatre','sp_tutorial_1','sm_pawnshop_1','hw_redspot_1'])
        stem='rc_radio_transition';tx.write('Unofficial_Patch/save/'+stem+'.sav',opt.save.read_bytes())
        tx.write('Bin/loader/subtitle-pause-fix.vtm',opt.plugin.read_bytes())
        launch=['-game','Unofficial_Patch','-dev','-novid','-console','+developer','0','+load',stem]
        atomic_json(folder/'launch.json',{'GameRoot':str(game),'Arguments':launch,'Candidates':[{'Path':str(game/'Bin/loader/subtitle-pause-fix.vtm'),'Hash':symbols['sha256']}]})
        tx.launch_intent(game/'Vampire.exe',launch);windows(config,'Launch',folder,folder/'launch.json')
        owned=read_json(folder/'process.json');tx.owned_process(owned['Id'],owned['Ticks'])
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            try:probe=TransitionProbe(folder);sample(probe,symbols);break
            except (OSError,RuntimeError,AssertionError,KeyError):
                if probe:k.CloseHandle(probe.p.h);probe=None
                time.sleep(.3)
        require(probe is not None,'Owned observer unavailable')
        require(digest(probe.p.module_paths['subtitle-pause-fix.vtm'])==symbols['sha256'],'Loaded plugin differs')
        if probe.console():probe.key(0x29)
        def recorder():
            with (folder/'transition.jsonl').open('x') as out:
                while not stop.is_set():
                    try:r=sample(probe,symbols)
                    except Exception as error:r={'qpc':time.perf_counter(),'loading_error':repr(error)}
                    out.write(json.dumps(r)+'\n');out.flush();stop.wait(.04)
        thread=threading.Thread(target=recorder);thread.start()
        def boundary(name,extra=None):
            atomic_json(folder/(name+'.json'),{'state':sample(probe,symbols),'extra':extra})
            probe.focus();ImageGrab.grab().save(folder/(name+'.png'))
            atomic_json(opt.output/'state.json',{'phase':name,'evidence':str(folder),'owned':owned})
        time.sleep(1)
        # Wait for the nominated save to finish loading, with advancing world.
        end=time.monotonic()+45
        while time.monotonic()<end:
            row=probe.snap()
            if any(e['class']=='player' for e in row['entities']) and row['server_time']>4 and not probe.console():break
            if probe.console():probe.key(0x29)
            time.sleep(.25)
        else:raise RuntimeError('Tutorial save did not finish loading')
        boundary('ready');print('READY',str(folder),flush=True)
        if opt.automatic:
            automatic_scenario(probe,symbols,opt,folder,boundary)
            atomic_json(opt.output/'observation-result.json',{'status':'PASS','evidence':str(folder),'plugin_sha256':symbols['sha256'],'save_sha256':digest(opt.save),'scope':'Automatic tutorial transition, physical Use, apartment reload, Red Spot pause/repeat; PCM audit separate'})
            return
        last=0;deadline=time.monotonic()+600
        while time.monotonic()<deadline:
            control=opt.output/'control.json'
            if not control.exists():time.sleep(.05);continue
            action=read_json(control)
            if action['id']<=last:time.sleep(.05);continue
            last=action['id'];name=action['action'];before=sample(probe,symbols);extra=None
            if name in ['talk','use']:probe.key(0x12)
            elif name=='choice4':probe.key(0x05)
            elif name=='aim_radio':extra=probe.aim_radio()
            elif name=='approach_jack':extra=probe.approach_jack()
            elif name=='audio':
                require(opt.capture is not None,'Capture helper required')
                wave=folder/(action['label']+'.wav')
                capture=subprocess.run([str(opt.capture.resolve()),str(owned['Id']),str(owned['Ticks']),str(wave),str(action.get('seconds',6))],capture_output=True,text=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
                (folder/(action['label']+'-capture.txt')).write_text(capture.stdout+capture.stderr)
                require(capture.returncode==0,'Process PCM capture failed')
            elif name=='save_control':probe.command('save rc_startup_on')
            elif name=='reload_control':probe.command('load rc_startup_on')
            elif name=='redspot':probe.command('map hw_redspot_1')
            elif name=='bind_pause':probe.command('bind F11 pause')
            elif name=='pause':probe.key(0x57)
            elif name=='unbind_pause':probe.command('unbind F11')
            elif name=='finish':break
            elif name!='sample':raise RuntimeError('Unknown action')
            time.sleep(action.get('wait',1));label=f'{last:02d}_{name}'
            boundary(label,extra)
            with (folder/'actions.jsonl').open('a') as out:out.write(json.dumps({'action':action,'before':before,'after':sample(probe,symbols)})+'\n')
            print('ACTION',label,flush=True);deadline=time.monotonic()+600
        else:raise TimeoutError('Transition action controller timed out')
        atomic_json(opt.output/'observation-result.json',{'status':'RECORDED','evidence':str(folder),'plugin_sha256':symbols['sha256'],'save_sha256':digest(opt.save)})
    except Exception as error:
        if probe:
            try:
                probe.focus();time.sleep(.2);ImageGrab.grab().save(folder/'failure.png')
                atomic_json(folder/'failure-state.json',sample(probe,symbols))
            except Exception:pass
        atomic_json(opt.output/'result.json',{'status':'FAIL','error':repr(error),'evidence':str(folder)});raise
    finally:
        stop.set()
        if thread:thread.join(timeout=5)
        if probe:k.CloseHandle(probe.p.h)
        try:
            preserve_session(tx,config,folder);atomic_json(opt.output/'restoration.json',{'status':'PASS'})
        except Exception as error:
            atomic_json(opt.output/'restoration.json',{'status':'FAIL','error':repr(error)});raise
    print('RESTORED',flush=True)


if __name__=='__main__':main()
