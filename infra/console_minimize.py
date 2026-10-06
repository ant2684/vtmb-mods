"""Fresh console control observations; external input, read-only native state."""
import json
import runpy
import sys
import time
from pathlib import Path
from infra.core import ROOT, Blocked, atomic_json, read_json, require
from infra.console_supported import evaluate as evaluate_supported
from infra.console_supported import preparation_error, preserve_first_error, supported_recipe


def audit_controls(evidence, initial_only=False):
    samples = evidence.get('control_samples', [])
    remaining = evidence.get('scenario') == 'console.minimize_remaining'
    labels = ['delayed_menu_open','after_reload'] if remaining else ['opened', 'former_button_click', 'title_menu_action', 'cached_reopen'] + ([] if initial_only else ['after_reload'])
    require([r['label'] for r in samples] == labels, 'Missing ordered minimize workflows')
    for row in samples:
        state = row['state']
        require(state['console']['visible'] == 1 and state['minimize']['visible'] == 0, 'Console minimize button remains available or console disappeared')
        menu = state['title_menu']
        if menu is not None:
            items = [i for i in menu['items'] if i['name'] == 'Minimize']
            require(len(items) == 1 and items[0]['enabled'] == 0, 'Cached/native Minimize menu entry remains available')
    if remaining:
        row = evidence['delayed_menu_action']
        closed,waited,opened = row['closed'],row['waited'],samples[0]['state']
        require(row['prior_menu']['menu']['visible']==1 and closed['menu']['visible']==0 and closed['console']['visible']==0, 'Native menu exit absent')
        require(4.9 <= waited['wall']-closed['wall'] <= 5.1 and waited['client_time']>closed['client_time'], 'Measured menu readiness wait wrong')
        require(row['opening_key_count']==1 and 0 <= row['key_down_wall']-waited['wall'] < .2, 'First delayed opening action not preserved')
        require(opened['console']['visible']==1 and opened['server_paused']==1, 'Delayed first opening failed')
    else:
        before, after = samples[0]['state'], samples[1]['state']
        require(before['console']['address'] == after['console']['address'] and after['server_paused'] == 1 and before['menu_pause_depth'] == after['menu_pause_depth'], 'Former minimize click changed console pause ownership')
        click = evidence.get('former_button_click', {})
        x1,y1,x2,y2 = before['minimize']['bounds']
        require(x1 <= click.get('client_x', -1) < x2 and y1 <= click.get('client_y', -1) < y2, 'Former button click coordinates unproven')
        cached = samples[2]['state']['title_menu']
        reopened = samples[3]['state']['title_menu']
        if cached is not None:
            require(reopened is not None and cached['address'] == reopened['address'], 'Existing title menu was not reused')
    observation = next(r for r in evidence['observations'] if r['check'] == 'minimize_controls')
    require(observation['before'] == samples[0]['state'] and observation['after'] == samples[-1]['state'], 'Control summary differs from raw native observations')


def evaluate(folder, remaining=False, initial_only=False):
    evidence = evaluate_supported(folder,remaining=remaining,initial_only=initial_only)
    controls = read_json(folder/'minimize-controls.json')
    evidence.update(controls)
    samples = controls['control_samples']
    evidence['observations'].append({'check': 'minimize_controls', 'expected': True, 'observed': True,
        'before': samples[0]['state'], 'after': samples[-1]['state'],
        'elapsed_seconds': samples[-1]['state']['wall']-samples[0]['state']['wall'], 'source': 'native-process-read'})
    # Every recorded opening, including ordinary/menu/script workflows, must hide it.
    for row in [json.loads(line) for line in (folder/'input.jsonl').read_text().splitlines() if line]:
        for key in ['before','after','held']:
            state = row.get(key)
            if state and state['console']['visible']:
                require(state['minimize']['visible'] == 0, 'Minimize reappeared during a recorded workflow')
    audit_controls(evidence,initial_only=initial_only)
    if remaining:
        row = controls['delayed_menu_action']
        evidence['observations'].append({'check': 'menu_first_delayed_open', 'expected': True, 'observed': True,
            'before': row['closed'], 'after': samples[0]['state'],
            'elapsed_seconds': samples[0]['state']['wall']-row['closed']['wall'], 'source': 'native-process-read'})
    return evidence


def audit_completion(first, remaining):
    """Audit actual completed workflows, retaining the first run's FAIL scope."""
    identities = [read_json(p/'identity.json') for p in [first,remaining]]
    for key in ['artifacts','modules','save_sha256','resources','background_mods']:
        require(identities[0][key]==identities[1][key], 'Completion combines different native inputs: '+key)
    require(identities[0]['scenario']=='console.minimize' and identities[1]['scenario']=='console.minimize_remaining', 'Wrong bounded completion scenarios')
    require(read_json(first/'scenario-result.json')['status']=='FAIL', 'First failure disposition changed')
    require(read_json(remaining/'scenario-result.json')['status']=='PASS', 'Remaining workflows did not pass')
    require(all(read_json(p/'preservation-result.json')['status']=='PASS' for p in [first,remaining]), 'Restoration not confirmed')
    evidence = [evaluate(first,initial_only=True),evaluate(remaining,remaining=True)]
    for folder,part in zip([first,remaining],evidence):
        owned = read_json(folder/'process.json')['Id']
        for row in part['observations']:
            require(row['before'].get('pid')==owned and row['after'].get('pid')==owned, 'Cross-process workflow evidence')
        loaded = read_json(folder/'loaded-inputs.json')
        require(all(loaded[n]['sha256']==h for n,h in identities[0]['artifacts'].items()), 'Actually loaded candidate differs')
    return {'status':'PASS', 'scope':'Completed distinct workflows on identical clean bytes; five-second input/menu readiness scope only',
        'first_run_status':'FAIL (retained)', 'first_failure':read_json(first/'console-first-error.json')['error'],
        'sessions':[str(first),str(remaining)], 'artifacts':identities[0]['artifacts'],
        'checks':[[r['check'] for r in e['observations']] for e in evidence],
        'metrics':[e['metrics'] for e in evidence],
        'limitations':['First tilde opening about 1.4 seconds after menu exit failed; native keydown received but console activation absent; exact client-filter cause unresolved. Immediate input is not certified.']}


def collect(folder):
    source = ROOT/'mods/console/tests/gameplay/console_clean.py'
    launch = read_json(folder/'launch.json')
    modified = supported_recipe(source.read_text(), launch['Save'])
    remaining = read_json(folder/'identity.json')['scenario']=='console.minimize_remaining'
    if remaining:
        begin = modified.index(' _start_behavior(d)\n')
        end = modified.index(" d.phase='script';",begin)
        modified = modified[:begin]+' _start_behavior(d)\n'+modified[end:]
    old = "d.phase='reload';d.text_command('load " + launch['Save'] + "',4);"
    require(modified.count(old) == 1, 'Reload capture boundary changed')
    modified = modified.replace(old, old + '_capture_reload(d);', 1)
    runner = folder/'console_minimize_recipe.py'
    runner.write_text(modified, encoding='utf-8')
    state = {'behavior_started': False, 'driver': None}
    controls = {'control_samples': []}

    def capture(label, driver):
        controls['control_samples'].append({'label': label, 'state': driver.snap()})
        atomic_json(folder/'minimize-controls.json', controls)

    def prepare(session, factory):
        # Loaded lazily: portable audit/rejection tests require no Windows process.
        class ControlDriver(factory):
            def snap(self):
                r = super().snap()
                p = self.p; dialog = r['console']['address']
                r['minimize'] = self.panel(p.u(dialog+0xb4))
                menu = p.u(dialog+0xcc)
                r['title_menu'] = None
                if menu:
                    vp = p.u(menu+4); vt = p.u(vp)
                    require(p.read(p.u(vt+0x5c),4) == bytes.fromhex('8b4104c3'), 'Unsupported native child count getter')
                    count = p.u(vp+4); array = p.u(vp+0xc)
                    require(count <= 128, 'Unbounded title menu child array')
                    items = []
                    for index in range(count):
                        child_vp = p.u(array+index*4); panel = p.u(child_vp+0x1c)
                        if not panel: continue
                        v = p.u(panel)
                        require(p.read(p.u(v+4),3) == bytes.fromhex('8bc1c3'), 'Unsupported native client panel getter')
                        require(p.read(p.u(v+0x48),3) == bytes.fromhex('8b412c'), 'Unsupported native panel name getter')
                        require(p.read(p.u(v+0xbc),4) == bytes.fromhex('8a4119c3'), 'Unsupported native enabled getter')
                        name = p.u(panel+0x2c)
                        items.append({'name': p.read(name,80).split(b'\0',1)[0].decode('cp1252') if name else '',
                                      'enabled': p.read(panel+0x19,1)[0], **self.panel(panel)})
                    r['title_menu'] = {'items': items, **self.panel(menu)}
                return r

            def click_at(self,x,y,right=False):
                from driver import W, u, INPUT, U, MI
                self.focus(); point = W.POINT(x,y)
                require(bool(u.ClientToScreen(self.hwnd,__import__('ctypes').byref(point))), 'Client coordinate translation failed')
                vx,vy,vw,vh = (u.GetSystemMetrics(i) for i in (76,77,78,79))
                self.send(INPUT(0,U(mi=MI(int((point.x-vx)*65535/(vw-1)),int((point.y-vy)*65535/(vh-1)),0,0xc001,0,0))))
                self.delay(.03)
                try:
                    self.send(INPUT(0,U(mi=MI(0,0,0,8 if right else 2,0,0)))); self.delay(.05)
                finally:
                    self.send(INPUT(0,U(mi=MI(0,0,0,16 if right else 4,0,0))),False)
                self.delay(.2)

        driver = ControlDriver(session); state['driver'] = driver
        from infra.gameplay import loaded_inputs
        atomic_json(folder/'loaded-inputs.json', loaded_inputs(driver.p,read_json(folder/'identity.json')))
        require(all(name in driver.bindings for name in ['+back','+forward']), 'Movement bindings missing')
        return driver

    def start(driver):
        driver.focus(); state['behavior_started'] = True
        atomic_json(folder/'console-phase.json', {'phase': 'behavior', 'wall_seconds': time.time()})
        driver.phase = 'minimize'; driver.toggle(True); capture('opened',driver)
        r = driver.snap(); require(r['minimize']['visible'] == 0, 'Minimize button was not hidden')
        x1,y1,x2,y2 = r['minimize']['bounds']
        require(8 <= x2-x1 <= 100 and 8 <= y2-y1 <= 100, 'Former minimize bounds unavailable')
        controls['former_button_click'] = {'client_x': (x1+x2)//2, 'client_y': (y1+y2)//2}
        driver.click_at(**{'x': controls['former_button_click']['client_x'], 'y': controls['former_button_click']['client_y']})
        capture('former_button_click',driver)
        require(driver.snap()['console']['visible'], 'Former minimize position hid the console')
        x1,y1,x2,y2 = driver.snap()['console']['bounds']
        driver.click_at((x1+x2)//2,y1+9,right=True); capture('title_menu_action',driver)
        if driver.snap()['title_menu'] and driver.snap()['title_menu']['visible']:
            driver.key(0x1b); driver.delay(.2)
        if driver.snap()['console']['visible']: driver.click_x()
        driver.toggle(True); capture('cached_reopen',driver); driver.click_x()

    def start_remaining(driver):
        driver.focus(); state['behavior_started'] = True
        driver.phase='remaining_menu'; driver.key(0x1b); driver.delay(.3)
        require(driver.snap()['menu']['visible']==1, 'Prior menu not opened')
        driver.toggle(True); driver.click_x(); prior=driver.snap()
        require(prior['menu']['visible']==1, 'Console did not restore prior menu')
        driver.key(0x1b); closed=driver.snap(); driver.delay(5); waited=driver.snap()
        driver.phase='menu_delayed_first'; driver.toggle(True); capture('delayed_menu_open',driver)
        actions=[json.loads(x) for x in (folder/'input.jsonl').read_text().splitlines() if x]
        downs=[r for r in actions if r['label']=='physical_key_down' and r.get('phase')=='menu_delayed_first' and r.get('vk')==0xc0]
        controls['delayed_menu_action']={'prior_menu':prior,'closed':closed,'waited':waited,
            'opening_key_count':len(downs),'key_down_wall':downs[0]['after']['wall'] if downs else None}
        atomic_json(folder/'minimize-controls.json',controls); driver.click_x()

    original_argv, original_path = sys.argv, sys.path[:]
    sys.path.insert(0,str(source.parent)); sys.argv = [str(runner),str(folder)]
    try:
        runpy.run_path(str(runner),run_name='__main__',init_globals={'_prepare_driver': prepare, '_start_behavior': start_remaining if remaining else start,
            '_capture_reload': lambda d: (d.toggle(True),capture('after_reload',d),d.click_x())})
    except Exception as error:
        preserve_first_error(folder,error,state)
        classified = preparation_error(error,state)
        if classified is error: raise
        raise classified from error
    finally:
        sys.argv, sys.path[:] = original_argv, original_path
    evidence = evaluate(folder,remaining=remaining); atomic_json(folder/'observations.json',evidence)
    return {'status': 'PASS', 'scope': 'Fresh native minimize controls and distinct supported console transitions; external five-second input wait'}


if __name__ == '__main__':
    folder = Path(sys.argv[1])
    try: result = collect(folder)
    except Blocked as error: result = {'status': 'BLOCKED', 'reason': str(error)}
    except Exception as error: result = {'status': 'FAIL', 'reason': repr(error)}
    atomic_json(folder/'collector-result.json',result)
    print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['status']=='PASS' else 75 if result['status']=='BLOCKED' else 1)
