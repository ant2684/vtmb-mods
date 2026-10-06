"""Fresh named audit of retained Console observations, without dated failures."""
import json
import math
import runpy
import sys
import time
import traceback
from pathlib import Path
from infra.core import ROOT, Blocked, Failure, atomic_json, read_json, require


def supported_recipe(source,save):
    """Fail closed if the retained recipe's explicit phase boundaries change."""
    require(isinstance(save,str) and __import__('re').fullmatch(r'rc_[a-z0-9_]+',save),'Unsupported task save name')
    replacements={"'load rc_console'":repr('load '+save),
        'time.sleep(25);d=Driver(session)':'time.sleep(25);d=_prepare_driver(session,Driver)',
        " for closing in ('x','tilde'):":" _start_behavior(d)\n for closing in ('x','tilde'):"}
    for old,new in replacements.items():
        require(source.count(old)==1,'Retained Console recipe boundary missing/ambiguous: '+old)
        source=source.replace(old,new,1)
    return source


def foreground_receipt(folder,state):
    """Read current window ownership only; never retry or reacquire foreground."""
    owned=read_json(folder/'process.json');driver=state.get('driver')
    receipt={'owned_pid':owned['Id'],'owned_start_ticks':owned['Ticks'],
             'requested_hwnd':getattr(driver,'hwnd',None)}
    try:
        module=sys.modules['driver'];hwnd=module.u.GetForegroundWindow();pid=module.W.DWORD()
        thread=module.u.GetWindowThreadProcessId(hwnd,module.C.byref(pid)) if hwnd else 0
        receipt.update(foreground_hwnd=hwnd,foreground_pid=pid.value if thread else None,
                       owned_foreground=bool(driver and hwnd==driver.hwnd and pid.value==driver.p.pid))
    except Exception as error:receipt['readback_error']=repr(error)
    return receipt


def preserve_first_error(folder,error,state):
    path=folder/'console-first-error.json'
    if path.exists():return  # A later inspection must not rewrite the first FAIL.
    row={'status':'FAIL','error':repr(error),'traceback':traceback.format_exc(),
         'phase':'behavior' if state['behavior_started'] else 'preparation',
         'behavior_started':state['behavior_started'],'wall_seconds':time.time()}
    try:row['foreground']=foreground_receipt(folder,state)
    except Exception as diagnostic:row['foreground']={'readback_error':repr(diagnostic)}
    try:atomic_json(path,row)
    except Exception as diagnostic:error.add_note('First Console error receipt unavailable: '+repr(diagnostic))


def preparation_error(error,state):
    # These precondition/OS guards precede any Console behavioral workflow.
    # After the explicit boundary all original errors retain their first FAIL.
    if not state['behavior_started'] and not isinstance(error,Failure) and isinstance(error,(AssertionError,OSError,RuntimeError,KeyError)):
        return Blocked('Preparation: Console workflow did not start: '+repr(error))
    return error


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def evaluate(folder):
    identity=read_json(folder/'identity.json');controls=rows(folder/'controls.jsonl');inputs=rows(folder/'input.jsonl')
    observations=[]
    def group(label):
        found=[r for r in controls if r['label']==label]
        require(len(found)>=8 and all(r['audio'] for r in found),'Missing native audio/world samples: '+label)
        return found
    def frozen(label):
        sample=group(label)
        require(all(r['paused']==r['server_paused']==1 for r in sample),'Pause ownership lost: '+label)
        require(len({r['client_time'] for r in sample})==1 and len({tuple((x['mixer'],x['position'],x['caption']) for x in r['audio']) for r in sample})==1,'World/audio not frozen: '+label)
        return sample
    def running(label):
        sample=group(label)
        require(sample[-1]['client_time']>sample[0]['client_time']+.2 and sample[-1]['audio'][0]['position']>sample[0]['audio'][0]['position'],'World/audio not resumed: '+label)
        require(all(r['paused']==r['server_paused']==0 for r in sample),'Resume flags wrong: '+label)
        return sample
    def record(check,before,after):
        observations.append({'check':check,'expected':True,'observed':True,'before':before,'after':after,'elapsed_seconds':max(0,after['wall']-before['wall']),'source':'native-process-read'})
    for closing in ['x','tilde']:
        a=frozen(closing+'_open');b=running(closing+'_resumed')
        require(a[0]['console']['visible'] and not b[-1]['console']['visible'],'Native console visibility transition absent')
        record('console_'+closing,a[0],b[-1])
    a=frozen('ordinary_before');b=frozen('ordinary_after');running('ordinary_resumed')
    record('ordinary_pause',a[0],b[-1])
    a=frozen('menu_restored');b=running('menu_resumed')
    require(all(r['menu']['visible'] and r['menu_pause_depth']==1 for r in a),'Prior menu not restored')
    record('prior_menu',a[0],b[-1])
    a=frozen('script_preserved');b=running('script_audio_resumed')
    require(all(r['pause_depth']==1 and r['menu_pause_depth']==0 and not r['console']['visible'] for r in a),'Script pause not independently retained')
    record('script_pause',a[0],b[-1])
    metrics=None;first_before=None;first_after=None
    for label in ['after_x','after_tilde','script_resumed','after_reload']:
        mouse=[r for r in inputs if r['label']==label+'_mouse'];moves=[r for r in inputs if r['label']==label+'_move']
        require(len(mouse)==len(moves)==2,'Missing independent input records: '+label)
        signed=[];receipts=[];camera=[]
        for r in moves:
            angle=math.radians(r['before']['angles'][1]);signed.append(sum((r['after']['origin'][i]-r['before']['origin'][i])*v for i,v in enumerate([math.cos(angle),math.sin(angle)])))
            name=r['command'][1:];receipts.append(bool(r['held']['keys'][name][2]&1))
            require(not r['after']['keys'][name][2]&1,'Movement release missing')
        for r in mouse:camera.append((r['after']['angles'][1]-r['before']['angles'][1]+180)%360-180)
        require(moves[0]['command']=='+back' and moves[1]['command']=='+forward' and signed[0]<-2 and signed[1]>2 and all(receipts),'Signed first movement/native receipt failed')
        require(camera[0]*camera[1]<0 and min(map(abs,camera))>.5,'Camera direction failed')
        wait,=[r for r in inputs if r['label']=='input_ready_wait' and r['probe']==label]
        elapsed=wait['after']['wall']-wait['before']['wall']
        require(4.9<=elapsed<=5.1,'Measured external readiness wait outside declared validity')
        a,b=moves[0]['before'],moves[-1]['after']
        require(all(b[n]==0 for n in ['paused','server_paused','menu_pause_depth']) and b['mouse_active']==1,'Input ownership did not return')
        if metrics is None:
            metrics={'native_back_held':receipts[0],'native_forward_held':receipts[1],'signed_back':signed[0],'signed_forward':signed[1],
                     'camera_left':min(camera),'camera_right':max(camera),'world_time_delta':b['client_time']-a['client_time'],'external_wait_seconds':elapsed}
            first_before,first_after=a,b
    record('first_input',first_before,first_after)
    a=next(r for r in inputs if r['label']=='console_command' and r['command'].startswith('load rc_'))
    require(a['before']['player_handle']!=a['after']['player_handle'],'Fresh native reload missing')
    running('reload_audio');record('reload',a['before'],a['after'])
    return {**identity,'resolved_resources':identity['resources'],'first_result_preserved':True,'observations':observations,'metrics':metrics}


def collect(folder):
    source=ROOT/'mods/console/tests/gameplay/console_clean.py'
    launch=read_json(folder/'launch.json')
    modified=supported_recipe(source.read_text(),launch['Save'])
    runner=folder/'console_fresh_recipe.py';runner.write_text(modified,encoding='utf-8')
    from infra.gameplay import loaded_inputs
    identity=read_json(folder/'identity.json');state={'behavior_started':False,'driver':None}
    def prepare(session,factory):
        driver=factory(session);state['driver']=driver
        atomic_json(folder/'loaded-inputs.json',loaded_inputs(driver.p,identity))
        require(all(isinstance(driver.bindings.get(name),str) and len(driver.bindings[name])==1 and driver.bindings[name].isascii() and driver.bindings[name].isalnum() for name in ['+back','+forward']),'Preparation: Console requires supported single-character forward/back bindings')
        return driver
    def start(driver):
        driver.focus()  # No retry: preserve the first foreground failure.
        state['behavior_started']=True
        atomic_json(folder/'console-phase.json',{'phase':'behavior','wall_seconds':time.time()})
    original_argv=sys.argv;original_path=sys.path[:]
    sys.path.insert(0,str(source.parent));sys.argv=[str(runner),str(folder)]
    try:
        runpy.run_path(str(runner),run_name='__main__',init_globals={'_prepare_driver':prepare,'_start_behavior':start})
    except Exception as error:
        preserve_first_error(folder,error,state)
        classified=preparation_error(error,state)
        if classified is error:raise
        raise classified from error
    finally:
        sys.argv=original_argv;sys.path[:]=original_path
    evidence=evaluate(folder);atomic_json(folder/'observations.json',evidence)
    return {'status':'PASS','scope':'Independent named native audit; no requirement to reproduce earlier failed runs'}


if __name__=='__main__':
    folder=Path(sys.argv[1])
    try:result=collect(folder)
    except Blocked as error:result={'status':'BLOCKED','reason':str(error)}
    except Exception as error:result={'status':'FAIL','reason':repr(error)}
    atomic_json(folder/'collector-result.json',result)
    print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['status']=='PASS' else 75 if result['status']=='BLOCKED' else 1)
