import json,sys,time,traceback
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'mods/history/tests')]
from drive import Driver,W,u,C
from gameplay import start,sheet,gender,base,purchase,select_history
from infra.history_ui import observe
from gender_regression import allocation
from infra.history_observations import PURCHASES

folder=Path(sys.argv[1]);d=Driver(folder)
def start_observed():
    rect=W.RECT();u.GetWindowRect(d.hwnd,C.byref(rect))
    if (rect.left,rect.top,rect.right,rect.bottom)!=(0,0,2560,1440):
        raise RuntimeError('Adapt input coordinates to current geometry; never change video settings')
    deadline=time.time()+45
    while not d.console():
        if time.time()>deadline:raise RuntimeError('Startup console not ready')
        time.sleep(.2)
    time.sleep(3);d.click(1444,123)
    if d.console():raise RuntimeError('Startup console remained open')
    time.sleep(2);d.record('actual_menu',True)
    d.click(1280,615)
    deadline=time.time()+45
    while not d.snap()['players']:
        if time.time()>deadline:
            d.record('creation_not_started',True)
            raise RuntimeError('New Game did not enter creation')
        time.sleep(.3)
    d.p.refresh();time.sleep(1);d.key(0x32);time.sleep(1)
def record(name,picture=False):
    s=d.snap(True);s['ui']=observe(d.p)
    (folder/(name+'.json')).write_text(json.dumps(s,indent=2))
    if picture:d.record(name+'_image',True)
    p=s['players'][0];g=p['groups'][0]
    print(json.dumps({'label':name,'xp':g['values'][34],'base_xp':g['secondary'][34],
                     'history':p['history'],'remaining':s['ui'].get('remaining'),
                     'spent':s['ui'].get('spent'),'attrs':g['values'][1:10]}),flush=True)
    return s
try:
    start_observed();gender(d,False);sheet(d);neutral=record('initial',True)
    d.click(2260,1328);a=record('after_auto',True)
    assert a['ui']['remaining']==[0]*7,'Auto-Spend did not execute'
    gender(d,True);record('after_gender')
    sheet(d);after=record('after_sheet',True)
    if len(sys.argv)>2 and sys.argv[2]=='full':
        assert allocation(after)==allocation(neutral) and after['players'][0]['history']==-1
        assert after['ui']['remaining']==neutral['ui']['remaining'] and after['ui']['spent']==0
        for n,(category,kind,index,xy) in enumerate(PURCHASES):
            before=observe(d.p);purchase(d,kind,xy,'full_pool_'+str(n));after_ui=observe(d.p)
            expected=before['remaining'][:];expected[list(after_ui['categories']).index(category)]-=1
            assert after_ui['remaining']==expected,(category,before,after_ui)
        funded=record('full_pool');assert funded['ui']['remaining']==[0]*7 and funded['ui']['spent']==10
        base(d);sheet(d);returned=record('base_sheet')
        assert allocation(returned)==allocation(funded) and returned['ui']['remaining']==[0]*7
        def reset_stats(label):
            d.click(2260,1328)
            if d.p.u(d.p.modules['client.dll']+0x5fb1f8):d.key(0x31)
            s=record(label,True)
            assert allocation(s)==allocation(neutral) and s['ui']['remaining']==neutral['ui']['remaining'] and s['ui']['spent']==0
            return s
        reset_stats('stock_reset')
        d.click(2260,1328);again=record('repeat_auto');assert again['ui']['remaining']==[0]*7
        select_history(d,10);sheet(d);h=record('history_after_auto')
        assert h['players'][0]['history']==78 and h['players'][0]['groups'][0]['effective'][1]==2
        assert h['ui']['remaining']==neutral['ui']['remaining']
        purchase(d,0,(551,309),'history_purchase')
        gender(d,False);sheet(d);m=record('manual_reverse_gender')
        assert allocation(m)==allocation(neutral) and m['ui']['remaining']==neutral['ui']['remaining'] and m['players'][0]['history']==-1
        purchase(d,0,(506,309),'manual_fresh_purchase')
        reset_stats('stock_reset_again')
        d.click(2260,1328);accepted_build=record('final_auto')
        assert accepted_build['ui']['remaining']==[0]*7
        base(d);sheet(d);assert allocation(d.snap())==allocation(accepted_build)
        d.click(2118,1189);d.click(2120,1387)
        deadline=time.time()+90
        while time.time()<deadline:
            s=d.snap()
            if s['players'] and s['players'][0]['groups'][0]['values'][34]==0:break
            time.sleep(.3)
        else:raise RuntimeError('Accept not observed')
        final=record('accepted')
        assert allocation(final)==allocation(accepted_build) and not final['ui']['creation_mode']
        (folder/'full-result.json').write_text(json.dumps({'result':'PASS','scope':'Auto/gender full pool, repeated auto, stock Reset Stats twice, actual bonus History manual/reverse reset, Base/Sheet and Accept','plugin':json.loads((folder/'identity.json').read_text())['plugin']}))
    else:
        try:purchase(d,0,(506,309),'purchase_after_gender');record('after_purchase')
        except Exception as e:print('purchase failure:',repr(e),flush=True)
except Exception:
    traceback.print_exc();raise
