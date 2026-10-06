"""Fresh named audit of retained Console observations, without dated failures."""
import json
import math
import runpy
import sys
from pathlib import Path
from infra.core import ROOT, Failure, atomic_json, read_json, require


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
    modified=source.read_text().replace("'load rc_console'",repr('load '+launch['Save']))
    modified=modified.replace('time.sleep(25);d=Driver(session)','time.sleep(25);d=Driver(session);_verify_loaded(d.p)')
    runner=folder/'console_fresh_recipe.py';runner.write_text(modified,encoding='utf-8')
    sys.path.insert(0,str(source.parent));sys.argv=[str(runner),str(folder)]
    from infra.gameplay import loaded_inputs
    identity=read_json(folder/'identity.json')
    runpy.run_path(str(runner),run_name='__main__',init_globals={'_verify_loaded':lambda process:atomic_json(folder/'loaded-inputs.json',loaded_inputs(process,identity))})
    evidence=evaluate(folder);atomic_json(folder/'observations.json',evidence)
    return {'status':'PASS','scope':'Independent named native audit; no requirement to reproduce earlier failed runs'}


if __name__=='__main__':
    folder=Path(sys.argv[1])
    try:result=collect(folder)
    except Exception as error:result={'status':'FAIL','reason':repr(error)}
    atomic_json(folder/'collector-result.json',result)
    print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['status']=='PASS' else 1)
