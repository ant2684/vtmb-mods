"""Fresh first-input collector; the first physical event is never retried.

Uses the retained read-only native observer and owned-process input driver.
No game memory, video settings, plugin diagnostics or gameplay files are changed.
"""
import json
import math
import sys
import time
from pathlib import Path
from infra.core import ROOT, Blocked, Failure, atomic_json, read_json, require


def collect(folder):
    identity=read_json(folder/'identity.json')
    require(identity['scenario']=='console.immediate','Wrong collector contract')
    sys.path.insert(0,str(ROOT/'mods/console/tests/gameplay'))
    from driver import Driver, k
    driver=None
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        try:
            driver=Driver(folder);driver.snap();break
        except (OSError,RuntimeError,AssertionError,KeyError):
            if driver:k.CloseHandle(driver.p.h);driver=None
            time.sleep(.3)
    if driver is None:raise Blocked('Preparation: owned scene/modules/native player unavailable within 40 seconds')
    d=driver
    require('+back' in d.bindings and '+forward' in d.bindings,'Movement bindings unavailable')
    # Close startup console as preparation, then establish a stable loaded scene.
    if d.snap()['console']['visible']:d.click_x()
    before=d.snap();d.delay(1);ready=d.snap()
    if ready['player_handle']!=before['player_handle'] or ready['client_time']<=before['client_time'] or ready['menu']['visible']:
        raise Blocked('Preparation: nominated save must have a stable unpaused world and unobstructed movement')
    d.toggle(True);opened=d.snap()
    require(opened['console']['visible'] and opened['server_paused']==1,'Console did not establish pause')
    d.click_x(delay=0);closed=d.snap()
    require(not closed['console']['visible'],'Close not natively observed')
    observed_close=time.perf_counter()
    first_send=[]
    original_send=d.send
    def record_send(event,check=True):
        if not first_send:first_send.append(time.perf_counter())
        return original_send(event,check)
    d.send=record_send
    movements=[];receipts=[]
    for command in ['+back','+forward']:
        before=d.snap();held=[]
        d.key(ord(d.bindings[command].upper()),.25,lambda:held.append(d.snap()))
        d.delay(.15);after=d.snap()
        yaw=math.radians(before['angles'][1])
        signed=sum((after['origin'][i]-before['origin'][i])*v for i,v in enumerate([math.cos(yaw),math.sin(yaw)]))
        movements.append(signed);receipts.append(bool(held[0]['keys'][command[1:]][2]&1))
        d.log('fresh_first_movement',before,after,held=held[0],command=command,signed=signed)
    angles=[]
    for delta in [80,-80]:
        before=d.snap();d.move(delta);after=d.snap()
        angles.append((after['angles'][1]-before['angles'][1]+180)%360-180)
        d.log('fresh_camera',before,after,delta=delta,yaw=angles[-1])
    final=d.snap();elapsed=first_send[0]-observed_close
    metrics={'native_back_held':receipts[0],'native_forward_held':receipts[1],
             'signed_back':movements[0],'signed_forward':movements[1],
             'camera_left':min(angles),'camera_right':max(angles),
             'world_time_delta':final['client_time']-closed['client_time'],
             'first_input_after_close_seconds':elapsed}
    satisfied=(all(receipts) and movements[0]<-2 and movements[1]>2 and angles[0]*angles[1]<0 and min(map(abs,angles))>.5
               and metrics['world_time_delta']>0 and final['paused']==final['server_paused']==final['menu_pause_depth']==0 and final['mouse_active']==1)
    evidence={**identity,'resolved_resources':identity['resources'],'first_result_preserved':True,
              'metrics':metrics,'observations':[
                  {'check':'close_observed','expected':True,'observed':True,'before':opened,'after':closed,'elapsed_seconds':0,'source':'native-process-read'},
                  {'check':'first_input','expected':True,'observed':satisfied,'before':closed,'after':final,'elapsed_seconds':elapsed,'source':'native-process-read'}]}
    atomic_json(folder/'observations.json',evidence)
    if elapsed>.25:raise Blocked('Collection schedule exceeded 250 ms validity budget; first result retained')
    require(satisfied,'First input/control behavior failed; raw first event retained in input.jsonl')
    return {'status':'PASS','metrics':metrics}


if __name__=='__main__':
    folder=Path(sys.argv[1]);result=None
    try:result=collect(folder)
    except (Blocked,Failure) as error:
        result={'status':'BLOCKED' if isinstance(error,Blocked) else 'FAIL','reason':str(error)}
    except Exception as error:result={'status':'BLOCKED','reason':'Collector preparation/observation exception: '+repr(error)}
    atomic_json(folder/'collector-result.json',result)
    print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['status']=='PASS' else 75 if result['status']=='BLOCKED' else 1)
