"""In-engine unsaved probe. Compatible with Bloodlines Python 2.1."""
import __main__,sys,time,math
LOG='__LOG__'
ACTIVE_SAVE='__ACTIVE_SAVE__'
mode='__MODE__'
started=0
feed_checks=0
def native_state():
    try:
        f=open(LOG.replace('probe.log','gate.txt'),'r');s=f.read();f.close();return s
    except:return ''
def log(x):
    f=open(LOG,'a');f.write(repr(x)+'\n');f.close()
def command(name):setattr(__main__.ccmd,name,'')
def snapshot(label):
    p=__main__.FindPlayer()
    log((label,p.base_protean,p.active_protean,p.GetModelName(),p.sequence,p.GetOrigin(),p.bloodpool,p.strength,p.brawl))
def start():
    global started
    sys.stderr=open(LOG.replace('probe.log','python-errors.log'),'a',0)
    log(('METHODS',dir(__main__.FindPlayer())))
    try:prepare()
    except:log(('ERROR',str(sys.exc_info()[1])))
def prepare():
    p=__main__.FindPlayer()
    if mode.startswith('native-hunger'):later(.3,'native_hunger_start()');return
    if mode=='filter-restore':later(.5,'filter_loaded()');return
    if mode.startswith('frenzy-maps'):
        stage=0
        if mode.endswith('griffith'):stage=1
        later(.3,'map_ready('+str(stage)+')');return
    if mode=='latest-midload':later(.5,'midload_begin()');return
    if mode=='latest-interface':later(.3,'interface_start()');return
    if mode.startswith('latest'):later(.3,'latest_start()');return
    if mode in ['restore-active','restore-legacy']:later(.15,'restore_active_start()');return
    p.Bloodgain(15)
    desired=5
    if mode=='filter-save':desired=4
    if mode.startswith('stealth') or mode.startswith('claws-actions') or mode=='inventory-2':desired=2
    log(('PREPARE',p.base_protean,p.active_protean))
    if p.active_protean: command('p5_end')
    elif p.base_protean<desired:command('p5_buy')
    elif p.base_protean>desired:command('p5_sell')
    elif mode.startswith('feeding') and p.brawl<5:command('p5_feed_brawl')
    elif mode.startswith('feeding') and p.strength<5:command('p5_feed_strength')
    else:
        snapshot('READY')
        if mode=='save-original-baseline':later(.5,'save_active_start()')
        elif mode in ['morph-original-baseline','morph-original-crouch-baseline','morph-original-female-baseline']:later(1.0,'original_start()')
        elif mode=='morph-visual':later(1.0,'morph_start()')
        elif mode=='native-edges':later(.8,'edges_start()')
        elif mode=='idle-races':later(1.0,'idle_setup()')
        elif mode=='actions':later(1.0,'actions_start()')
        elif mode=='native-dependencies-off':later(.5,'dependencies_off()')
        elif mode=='filter-save':command('p5_cast');later(2.,'filter_initial()')
        elif mode.startswith('claws-actions'):later(1.0,'claws_start()')
        elif mode.startswith('stealth'):later(1.0,'stealth_start()')
        elif mode.startswith('frenzy'):later(1.0,'frenzy_setup()')
        elif mode.startswith('transitions'):later(1.0,'transitions_setup()')
        elif mode=='save-active':later(.5,'save_active_start()')
        elif mode=='inventory-2':later(.5,'inventory_start()')
        elif mode=='feeding-expiry':__main__.cvar.vdiscipline_use_new='0';__main__.cvar.vdiscipline_allow_renewables='0';log(('EXPIRY_TIMED_MODE',__main__.cvar.vdiscipline_use_new,__main__.cvar.vdiscipline_allow_renewables));command('p5_cast');later(.2,'expiry_raise()')
        elif mode.startswith('feeding'):later(1.0,'feed_setup()')
        else:__main__.ScheduleTask(1.0,"__import__('p5_probe').cast()")
        return
    __main__.ScheduleTask(.3,"__import__('p5_probe').prepare()")
def cast():
    snapshot('BEFORE_CAST');command('p5_cast')
    __main__.ScheduleTask(.1,"__import__('p5_probe').snapshot('CAST_100MS')")
    __main__.ScheduleTask(2.5,"__import__('p5_probe').snapshot('CAST_SETTLED')")
    if mode in ['feeding','feeding-middle']:__main__.ScheduleTask(5.0,"__import__('p5_probe').stop_feed()")
    else:__main__.ScheduleTask(3.0,"__import__('p5_probe').end()")
def end():
    snapshot('BEFORE_END');command('p5_end')
    __main__.ScheduleTask(.1,"__import__('p5_probe').snapshot('END_100MS')")
    __main__.ScheduleTask(2.5,"__import__('p5_probe').finish()")
def finish():snapshot('DONE')
def feed_setup():
    try:
        p=__main__.FindPlayer();n=__main__.FindEntitiesByName('thug_station_bathroom')[0]
        p.SetOrigin((-1765.331665,-1464.379028,-255.96875));p.SetAngles((0,90,0))
        n.SetOrigin((-1764.554688,-1404.183105,-255.90625));n.SetAngles((0,90,0));n.SetRelationship('player D_NU 10')
        p.Bloodloss(8)
        log(('VICTIM',n.GetModelName(),n.GetOrigin(),n.health,n.bloodpool))
        __main__.ScheduleTask(.6,"__import__('p5_probe').feed_begin()")
    except:log(('ERROR',str(sys.exc_info()[1])))
def feed_begin():
    # Body SetAngles does not rotate the client view. Stage the victim in the
    # actual settled direction; the old setang console command is unsupported.
    p=__main__.FindPlayer();n=__main__.FindEntitiesByName('thug_station_bathroom')[0]
    yaw=p.GetAngles()[1];xyz=p.GetOrigin();r=yaw*math.pi/180.0
    n.SetOrigin((xyz[0]+60*math.cos(r),xyz[1]+60*math.sin(r),xyz[2]+.1));n.SetAngles((0,yaw,0))
    if mode=='feeding-entry':
        command('p5_cast');later(.1,"mark('ENTRY_FEED_HUMAN')");later(.3,'entry_feed_request()');return
    entry_feed_request()

def entry_feed_request():
    __main__.ccmd.feedStart=''
    __main__.ScheduleTask(1.2,"__import__('p5_probe').command('feedStop')")
    snapshot('FEED_REQUEST')
    __main__.ScheduleTask(.1,"__import__('p5_probe').wait_feed()")
def wait_feed():
    global feed_checks
    feed_checks=feed_checks+1
    s=native_state()
    if s.find('feed_loop')>=0 or s.find('_back_bite')>=0:
        if mode in ['feeding-middle','feeding-release'] and (__main__.FindPlayer().bloodpool<8 or s.find('feed_loop')<0):
            later(.1,'wait_feed()');return
        log(('FEED_CONFIRMED',s))
        if mode=='feeding-entry':
            mark('CAST_100MS');later(5.0,'stop_feed()')
        elif mode=='feeding-expiry':later(.1,'expiry_wait()')
        elif mode=='feeding-release':command('feedStart');later(.2,"command('feedStop')");later(.1,'release_wait()')
        else:cast()
        return
    if feed_checks>100:log(('ERROR','No native feeding scene',s));return
    __main__.ScheduleTask(.1,"__import__('p5_probe').wait_feed()")
def stop_feed():
    snapshot('FEED_PROGRESS');command('feedStart')
    __main__.ScheduleTask(.2,"__import__('p5_probe').command('feedStop')")
    __main__.ScheduleTask(.5,"__import__('p5_probe').wait_feed_end()")
def wait_feed_end():
    if native_state().endswith('|0xffffffff'):end();return
    __main__.ScheduleTask(.2,"__import__('p5_probe').wait_feed_end()")

def later(delay,expression):
    __main__.ScheduleTask(delay,"__import__('p5_probe').guard("+repr(expression)+")")
def guard(expression):
    try:eval(expression,globals())
    except:log(('ERROR',expression,str(sys.exc_info()[1])))
def native_detail():
    for name in ['native-state.txt','native-state-fallback.txt']:
        try:
            f=open(LOG.replace('probe.log',name),'r');s=f.read();f.close();return eval(s)
        except:pass
    return {}
native_mark_serial=0
def mark(label):
    global native_mark_serial
    snapshot(label);native_mark_serial=native_mark_serial+1;request=str(native_mark_serial)
    # Ask the external reader to begin a new sample after this request. Holding
    # the engine thread here observes this exact frame, without replaying the
    # action, advancing its simulation, or reusing a stale matching-tier sample.
    f=open(LOG.replace('probe.log','snapshot-request.txt'),'w');f.write(request);f.close()
    deadline=time.time()+2.0
    while time.time()<deadline:
        d=native_detail()
        if d.get('snapshot_request')==request:
            if d.get('protean')!=__main__.FindPlayer().active_protean:raise RuntimeError('Inconsistent current-player snapshot at '+label)
            log(('NATIVE',label,d));return
        time.sleep(.005)
    raise RuntimeError('Fresh native snapshot timeout at '+label)

action_round=0
action_names=['forward','attack','jump','duck','use','feed']
def actions_start():
    p=__main__.FindPlayer();p.GiveItem('item_w_katana');p.GiveItem('item_w_knife');command('p5_sword');command('p5_camera')
    later(.8,'actions_full_idle()')
def actions_full_idle():
    command('p5_cast');later(.1,"mark('FULL_IDLE_ON_100MS')");later(.5,"mark('FULL_IDLE_ON_BODY')");later(2.3,"mark('FULL_IDLE_ON_DONE')");later(2.5,'actions_full_idle_end()')
def actions_full_idle_end():
    command('p5_end');later(.1,"mark('FULL_IDLE_OFF_100MS')");later(.5,"mark('FULL_IDLE_OFF_BODY')");later(2.3,"mark('FULL_IDLE_OFF_DONE')");later(2.6,'actions_held()')
def actions_held():
    mark('INVENTORY_BEFORE');command('p5_forward');later(.15,'actions_held_cast()')
def actions_held_cast():
    mark('HELD_BEFORE');command('p5_cast');later(.1,"mark('HELD_ON_100MS')")
    later(.15,"command('snapshot')");later(.45,'actions_held_end()')
def actions_held_end():
    mark('HELD_END_BEFORE');command('p5_end');later(.1,"mark('HELD_OFF_100MS')")
    later(.15,"command('snapshot')");later(.35,"command('p5_stopforward')");later(.8,'actions_idle()')
actions_idle_candidate=None
def actions_idle():
    global actions_idle_candidate
    p=__main__.FindPlayer()
    if p.active_protean:raise RuntimeError('Previous form did not end')
    d=native_detail();s=d.get('sequence_name','').lower()
    if s.find('attack')>=0 or s.find('feeding')>=0 or s.find('jump')>=0 or s.find('walk')>=0 or s.find('run')>=0 or s.find('hop')>=0 or s.find('fall')>=0 or s.find('land')>=0:
        actions_idle_candidate=None;later(.1,'actions_idle()');return
    xyz=d.get('origin');stamp=d.get('observer_time',0)
    if xyz is None or not stamp:later(.1,'actions_idle()');return
    if actions_idle_candidate is None:
        actions_idle_candidate=(stamp,xyz);later(.15,'actions_idle()');return
    old,origin=actions_idle_candidate
    if stamp<=old:later(.1,'actions_idle()');return
    if ((xyz[0]-origin[0])**2+(xyz[1]-origin[1])**2+(xyz[2]-origin[2])**2)>.0625:
        actions_idle_candidate=(stamp,xyz);later(.15,'actions_idle()');return
    actions_idle_candidate=None
    mark('IDLE_BEFORE_'+str(action_round));command('p5_cast')
    later(.1,"mark('IDLE_ON_100MS_'+str(action_round))");later(.3,'actions_press_on()')
def actions_press_on():
    command('p5_'+action_names[action_round]);later(.1,"mark('INTERRUPT_ON_'+str(action_round))")
    later(.2,"command('p5_stop'+action_names[action_round])");later(.8,'actions_idle_end()')
actions_end_origin=None

def actions_idle_end():
    global actions_end_origin
    seq=native_state().split('|')[0].lower();xyz=__main__.FindPlayer().GetOrigin()
    busy=seq.find('attack')>=0 or seq.find('feeding')>=0 or seq.find('jump')>=0 or seq.find('walk')>=0 or seq.find('run')>=0 or seq.find('hop')>=0 or seq.find('fall')>=0 or seq.find('land')>=0
    if busy:
        actions_end_origin=None;later(.1,'actions_idle_end()');return
    if actions_end_origin is None or ((xyz[0]-actions_end_origin[0])**2+(xyz[1]-actions_end_origin[1])**2+(xyz[2]-actions_end_origin[2])**2)>.0625:
        actions_end_origin=xyz;later(.1,'actions_idle_end()');return
    actions_end_origin=None;mark('IDLE_OFF_BEFORE_'+str(action_round));command('p5_end');later(.1,"mark('IDLE_OFF_100MS_'+str(action_round))");later(.3,'actions_press_off()')
def actions_press_off():
    command('p5_'+action_names[action_round]);later(.1,"mark('INTERRUPT_OFF_'+str(action_round))")
    later(.2,"command('p5_stop'+action_names[action_round])");later(.8,'actions_next()')
def actions_next():
    global action_round
    action_round=action_round+1
    if action_round>=len(action_names):finish()
    else:later(.2,'actions_idle()')

stealth_round=0
stealth_targets=[]
stealth_checks=0
def stealth_start():
    global stealth_targets
    stealth_targets=__main__.FindEntitiesByName('thug_station_bathroom')[:1]
    for n in __main__.FindEntitiesByClass('npc_VHumanCombatant'):
        if n not in stealth_targets and n.IsAlive() and n.health>0 and n.GetModelName().lower().find('/gangmember_male_')>=0:stealth_targets.append(n)
    log(('STEALTH_TARGETS',len(stealth_targets)))
    if len(stealth_targets)<4:raise RuntimeError('Four live map combatants required')
    if mode=='stealth-tiger':command('p5_melee')
    command('p5_male');later(.8,'stealth_setup()')
def stealth_setup():
    global stealth_checks
    stealth_checks=0
    p=__main__.FindPlayer();p.Bloodgain(15)
    command('ai_disable')
    for j in range(stealth_round,4):stealth_targets[j].SetOrigin((-765.0+100*j,-404.0,-255.90625))
    n=stealth_targets[stealth_round]
    if stealth_round%2:n.SetModel('models/character/npc/common/prostitute/prostitute_1/prostitute_1.mdl')
    else:n.SetModel('models/character/npc/common/gangmember_male_2/gangmember_male_2.mdl')
    n.SetOrigin((-1764.554688,-1376.183105,-255.90625));n.SetAngles((0,90,0))
    p.SetOrigin((-1765.331665,-1464.379028,-255.96875));p.SetAngles((0,90,0))
    if mode=='stealth-tiger':p.GiveItem('item_w_chang_claw');command('p5_tiger')
    elif not p.active_protean:command('p5_cast')
    command('p5_camera');later(.8,'stealth_ready()')
def stealth_ready():
    global stealth_checks
    stealth_checks=stealth_checks+1
    p=__main__.FindPlayer()
    weapon='item_w_claws'
    if mode=='stealth-tiger':weapon='item_w_chang_claw'
    if not p.HasWeaponEquipped(weapon):
        if stealth_checks>20:raise RuntimeError('Claws not equipped')
        later(.2,'stealth_ready()');return
    if native_state().split('|')[0].lower().find('crouch')<0:
        command('p5_duck');later(.1,"command('p5_unduck')");later(.4,'stealth_ready()');return
    # SetAngles changes body orientation, not client view. Place the native
    # victim along the actual view direction; no mouse or view injection.
    yaw=p.GetAngles()[1];xyz=p.GetOrigin();r=yaw*math.pi/180.0
    n=stealth_targets[stealth_round];n.SetOrigin((xyz[0]+88*math.cos(r),xyz[1]+88*math.sin(r),xyz[2]));n.SetAngles((0,yaw,0))
    log(('STEALTH_READY',stealth_round,p.IsMale(),stealth_targets[stealth_round].IsMale(),native_state()))
    command('p5_forward');later(.35,"command('p5_use')");later(.48,"command('p5_unuse')");later(.49,"command('p5_stopforward')");later(.4,'stealth_wait()')
def stealth_wait():
    global stealth_checks
    stealth_checks=stealth_checks+1
    if native_state().find('stealth_success_attacker')>=0:
        log(('STEALTH_ENTER',stealth_round,native_state()));command('ai_disable')
        later(.7,'stealth_photo()')
        if mode in ('stealth-visual','stealth-tiger'):
            later(.12,'stealth_photo()');later(.28,'stealth_photo()');later(.44,'stealth_photo()')
        later(.2,'stealth_wait_end()');return
    if stealth_checks>50:raise RuntimeError('Paired claws kill did not start: '+native_state())
    later(.1,'stealth_wait()')
def stealth_photo():
    __main__.ccmd.snapshot=''
def stealth_wait_end():
    if native_state().endswith('|0xffffffff'):
        log(('STEALTH_RETURN',stealth_round,native_state()));snapshot('STEALTH_MOVE_BEFORE_'+str(stealth_round))
        command('p5_forward');later(.22,'stealth_after_move()');return
    later(.1,'stealth_wait_end()')
def stealth_after_move():
    global stealth_round
    command('p5_stopforward');snapshot('STEALTH_MOVE_AFTER_'+str(stealth_round));command('p5_end')
    stealth_round=stealth_round+1
    if stealth_round>=4:later(.5,'finish()');return
    if stealth_round==2:command('p5_female');later(1.0,'stealth_setup()')
    else:later(.7,'stealth_setup()')


def release_wait():
    s=native_state()
    if s.find('release')>=0:
        log(('RELEASE_CONFIRMED',s));cast();return
    if s.endswith('|0xffffffff'):raise RuntimeError('Release finished before activation')
    later(.03,'release_wait()')

expiry_checks=0
expiry_deadline=0.0
expiry_deferred_seen=0
def expiry_wait():
    global expiry_checks,expiry_deferred_seen
    expiry_checks=expiry_checks+1
    p=__main__.FindPlayer();d=native_detail()
    # Discipline and pairing must come from the same observer sample.
    # Reading live power with the older gate file races native pair release.
    if d.get('protean') is None:later(.05,'expiry_wait()');return
    s=d['sequence_name']+'|'+d['partner']
    if d['protean']<5:
        if not s.endswith('|0xffffffff'):raise RuntimeError('Stock expiry deferral changed')
        if d.get('state',0)==30 or p.GetModelName().lower().find('animalism_beastform')>=0:
            later(.1,'expiry_wait()');return
        mark('EXPIRED_AFTER_FEEDING');snapshot('FEED_PROGRESS')
        if not expiry_deferred_seen:raise RuntimeError('Native timer boundary was not observed during feeding')
        if not s.endswith('|0xffffffff'):raise RuntimeError('Stock expiry deferral changed')
        later(.2,'end()');return
    if not expiry_deferred_seen and d.get('game_time',0)>=expiry_deadline and not s.endswith('|0xffffffff'):
        expiry_deferred_seen=1;mark('NATIVE_TIMER_DEFERRED')
    later(.05,'expiry_wait()')


frenzy_round=0
if mode=='frenzy-frenzy-first':frenzy_round=1
frenzy_checks=0
frenzy_targets=[]
frenzy_home=None
def frenzy_setup():
    global frenzy_checks,frenzy_targets,frenzy_home
    frenzy_checks=0
    p=__main__.FindPlayer();p.Bloodgain(15);command('p5_camera')
    if int(native_detail().get('player_flags','0'),16)&0x8000:command('notarget')
    __main__.FindEntityByName('world').SetNoFrenzyArea(0)
    if frenzy_home is None:frenzy_home=p.GetOrigin()
    else:p.SetOrigin(frenzy_home)
    xyz=p.GetOrigin()
    if not (int(native_detail().get('player_flags','0'),16)&0x4000):command('god')
    d=__main__.FindEntityByName('bum_male')
    if d:d.ScriptHide()
    home=p.GetOrigin();targets=[]
    for n in __main__.FindEntitiesByClass('npc_VHumanCombatant'):
        if n.GetName().find('fk_target_')==0:n.SetName('fk_previous_'+str(frenzy_round)+'_'+n.GetName())
        if n.GetName().find('fk_previous_')==0:continue
        if n.IsAlive() and n.health>0 and n.GetModelName().lower().find('/gangmember_male_2/')>=0:
            xyz=n.GetOrigin();targets.append(((xyz[0]-home[0])**2+(xyz[1]-home[1])**2+(xyz[2]-home[2])**2,len(targets),n))
    targets.sort()
    if len(targets)<2:raise RuntimeError('Two live native Frenzy targets required')
    frenzy_targets=[targets[0][2],targets[1][2]]
    for j in range(2):
        n=frenzy_targets[j];n.SetName('fk_target_'+str(j))
        n.SetOrigin((home[0]+55+j*60,home[1]+20,home[2]));n.SetAngles((0,math.atan2(-20,-55-j*60)*180/math.pi,0));n.SetRelationship('player D_HT 10')
    later(.3,'frenzy_ready_human()')

def frenzy_start():
    global frenzy_checks
    d=native_detail();targets=d.get('targets',[])
    if d.get('state',0)==30:later(.1,'frenzy_start()');return
    ready=len(targets)==2 and d.get('ai_flags',1)==0
    for n in targets:
        ready=ready and n['targetable']==1 and n['alive']==1 and n['life']==0 and n['health']>0 and n['solid'] in [1,2,3,4,5,6] and not (n['effects']&0x20) and not(n['spawn_flags']&0x8000) and not n['think_disabled'] and n['enemy']==d.get('player_handle','')
    if not ready:
        frenzy_checks=frenzy_checks+1
        if frenzy_checks>100:raise RuntimeError('Native enemy readiness gate failed: '+repr(d))
        later(.1,'frenzy_start()');return
    frenzy_checks=0
    mark('FRENZY_BEFORE_'+str(frenzy_round));command('p5_frenzy');later(.15,'frenzy_confirm()')

def frenzy_confirm():
    d=native_detail();mark('FRENZY_BOTH_'+str(frenzy_round));frenzy_model_mark('FRENZY_MODEL_BOTH')
    if not d.get('frenzy',0) or d.get('controller','0xffffffff')=='0xffffffff':raise RuntimeError('Native Frenzy failed to acquire its controller')
    if frenzy_round==0:
        command('p5_end');later(.1,"mark('FRENZY_PROTEAN_END_FIRST')");later(.12,"frenzy_model_mark('FRENZY_MODEL_RETURN')");later(.15,"command('snapshot')");later(.45,"command('snapshot')")
    later(.5,'frenzy_wait()')

def frenzy_wait():
    global frenzy_round,frenzy_checks
    frenzy_checks=frenzy_checks+1;d=native_detail()
    if not d.get('frenzy',0) and d.get('controller','0xffffffff')=='0xffffffff':
        if frenzy_round == 1 and d.get('item_classes',{}).get(d.get('weapon','')) != 'item_w_claws':
            if frenzy_checks>325:raise RuntimeError('Remaining P5 did not restore selected Claws')
            later(.1,'frenzy_wait()');return
        mark('FRENZY_RETURN_'+str(frenzy_round))
        later(.2,'frenzy_release_before_finish()')
        return
    if frenzy_checks>325:raise RuntimeError('Native Frenzy did not finish within 65 seconds')
    later(.2,'frenzy_wait()')


cfg_seen=0
def cfg_callback():
    global cfg_seen
    cfg_seen=1;log(('CFG_CALLBACK',1))

def transitions_setup():
    transitions_cfg_check()

def transitions_cfg_check():
    p=__main__.FindPlayer();p.GiveItem('item_w_katana');p.GiveItem('item_w_knife');command('p5_sword');later(.5,'transitions_cast_load()')

def transitions_cast_load():
    command('p5_cast');later(3.0,'transitions_load()')

def transitions_load():
    mark('BEFORE_RELOAD');command('p5_reload')

def loaded_callback():
    later(3.0,'transitions_loaded()')

def transitions_loaded():
    mark('AFTER_RELOAD');p=__main__.FindPlayer()
    log(('LOADED_MAP',__main__.FindEntitiesByClass('worldspawn')[0].GetModelName()))
    if p.active_protean or p.base_protean!=2:raise RuntimeError('Owned inactive seed not loaded')
    transitions_prepare_map()

def transitions_prepare_map():
    p=__main__.FindPlayer()
    if p.base_protean<5:command('p5_buy');later(.3,'transitions_prepare_map()');return
    p.Bloodgain(15);command('p5_cast');later(3.0,'transitions_map()')

def transitions_map():
    mark('BEFORE_MAP');__main__.ChangeMap(0,'warehouselandmark','santamonicateleport')

def mapped_callback():
    later(3.0,'transitions_mapped()')

def transitions_mapped():
    mark('AFTER_MAP');log(('CHANGED_MAP',__main__.FindEntitiesByClass('worldspawn')[0].GetModelName()))
    command('p5_end');later(2.5,'finish()')


def saved_callback():
    later(.3,'transitions_saved()')

def transitions_saved():
    mark('AFTER_ACTIVE_RELOAD');command('p5_forward');later(.2,'transitions_saved_moved()')

def transitions_saved_moved():
    command('p5_stopforward');mark('AFTER_ACTIVE_RELOAD_MOVED');command('p5_reload')


def expiry_raise():
    global expiry_deadline
    p=__main__.FindPlayer()
    if p.active_protean<5:command('p5_cast');later(.2,'expiry_raise()');return
    d=native_detail()
    if d.get('discipline_begin') is None or d.get('protean')!=5:later(.1,'expiry_raise()');return
    mark('EXPIRY_ARMED')
    expiry_deadline=d['discipline_begin'][11]+d['discipline_durations'][11]
    remaining=expiry_deadline-d['game_time']
    log(('EXPIRY_NATIVE_REMAINING',remaining))
    later(max(.1,remaining-5.0),'expiry_feed_setup()')

def expiry_feed_setup():
    __main__.FindPlayer().Bloodgain(15);feed_setup()


def frenzy_ready_human():
    global frenzy_checks
    d=native_detail();targets=d.get('targets',[])
    if len(targets)==2 and all_native_enemies(targets,d.get('player_handle','')):
        command('p5_cast');later(.4,'frenzy_start()');return
    frenzy_checks=frenzy_checks+1
    if frenzy_checks>100:raise RuntimeError('Human-form native enemy acquisition failed')
    later(.1,'frenzy_ready_human()')

def all_native_enemies(targets,player):
    for n in targets:
        if n['enemy']!=player:return 0
    return 1


def save_active_start():
    command('p5_cast');later(.3,'save_scene_observe()')

def save_scene_observe():
    mark('SAVE_SCENE')
    if mode=='save-original-baseline':command('p5_save_active')
    later(2.5,'save_active_now()')

def save_active_now():
    mark('SAVE_ACTIVE');command('p5_save_active');finish()

def restore_active_start():
    if native_detail().get('wolf') is None:later(.1,'restore_active_start()');return
    mark('RESTORED_ACTIVE');command('p5_forward');later(.25,'restore_active_moved()')

def restore_active_moved():
    command('p5_stopforward');mark('RESTORED_ACTIVE_MOVED');command('p5_end');later(.1,"mark('RESTORED_ENDED')");later(2.5,'finish()')


def frenzy_release_before_next():
    if native_state().endswith('|0xffffffff'):
        later(.5,'frenzy_setup()');return
    command('feedStart');later(.15,"command('feedStop')");later(.5,'frenzy_wait_release()')

def frenzy_wait_release():
    if native_state().endswith('|0xffffffff'):later(.5,'frenzy_setup()');return
    later(.2,'frenzy_wait_release()')


def frenzy_release_before_finish():
    if native_state().endswith('|0xffffffff'):
        command('p5_end');later(2.5,'finish()');return
    command('feedStart');later(.15,"command('feedStop')");later(.5,'frenzy_finish_wait_release()')

def frenzy_finish_wait_release():
    if native_state().endswith('|0xffffffff'):
        command('p5_end');later(2.5,'finish()');return
    later(.2,'frenzy_finish_wait_release()')


def inventory_start():
    p=__main__.FindPlayer();p.GiveItem('item_w_katana');p.GiveItem('item_w_knife');command('p5_sword');later(.8,'inventory_cast()')

def inventory_cast():
    mark('INVENTORY_BEFORE');command('p5_cast');later(.2,"mark('INVENTORY_CLAWS')");later(2.0,'inventory_end()')

def inventory_end():
    command('p5_end');later(.2,"mark('INVENTORY_RETURN')");later(2.5,'finish()')


morph_round=0

def morph_start():
    command('p5_camera');later(.5,'morph_begin()')

def morph_begin():
    global morph_round
    log(('MORPH_VARIANT',morph_round,__main__.FindPlayer().IsMale()));mark('MORPH_BEFORE_'+str(morph_round));command('snapshot')
    if morph_round%2:command('p5_end')
    else:command('p5_cast')
    for delay in [.1,.45,.9,1.5,2.3]:
        later(delay,"morph_frame('MORPH_"+str(morph_round)+"_"+str(delay)+"')")
    later(2.7,'morph_next()')

def morph_next():
    global morph_round
    morph_round=morph_round+1
    if morph_round in [2,6]:
        command('p5_duck');later(.7,'morph_begin()')
    elif morph_round==4:
        command('p5_stopduck');later(.2,"command('p5_duck')");later(.35,"command('p5_stopduck')");command('p5_female');later(1.0,'morph_begin()')
    elif morph_round>=8:
        command('p5_stopduck');later(.7,'finish()')
    else:later(.5,'morph_begin()')


def morph_frame(label):
    mark(label);command('snapshot')


# Baseline investigation only: no lifecycle module, original resource inputs.
def original_start():
    command('p5_camera')
    if mode=='morph-original-crouch-baseline':
        command('p5_duck');later(.1,"command('p5_stopduck')");later(.8,'original_enter()')
    elif mode=='morph-original-female-baseline':command('p5_female');later(.8,'original_enter()')
    else:later(.5,'original_enter()')

def original_enter():
    mark('ORIGINAL_BEFORE');command('snapshot');command('p5_cast')
    for delay in [.1,.35,.65,1.,1.5,2.,2.4,3.]:
        later(delay,"original_frame('ORIGINAL_ON_"+str(delay)+"')")
    later(3.5,'original_return()')

def original_return():
    if mode=='morph-original-crouch-baseline':mark('ORIGINAL_BEFORE_RETURN')
    command('p5_end')
    for delay in [.1,.35,.65,1.,1.5,2.,2.4,3.]:
        later(delay,"original_frame('ORIGINAL_OFF_"+str(delay)+"')")
    later(3.5,'finish()')

def original_frame(label):
    mark(label);command('snapshot')


# Deliberately drive the installed idle scheduler at the difficult boundaries.
def idle_setup():
    import vamputil
    p=__main__.FindPlayer();g=__main__.G
    g.Anims_Disabled=1;g.No_Idle=0;g.InCombat=0;g.Pos_One=p.GetOrigin()
    vamputil.randint=lambda a,b:2
    log(('IDLE_POINTER',str(type(p._entity_ptr_)),p._entity_ptr_==__main__.FindPlayer()._entity_ptr_))
    __main__.ScheduleTask(.9,"__import__('vamputil')._proteanIdleExit(17)")
    command('p5_camera');vamputil.AThingOfSomeKind();later(.3,'idle_cast()')

def idle_fire():
    import vamputil
    g=__main__.G;g.Pos_One=__main__.FindPlayer().GetOrigin();g.InCombat=0;g.No_Idle=0
    vamputil.AThingOfSomeKind()

def idle_cast():
    mark('IDLE_HUMAN_BEFORE');command('p5_cast')
    later(.45,"mark('IDLE_ON_BODY')");later(.6,'idle_fire()');later(.8,"command('Alert_Front_outof')")
    later(1.2,"mark('IDLE_ON_SURVIVED')");later(2.4,"mark('IDLE_ON_DONE')");later(2.6,'idle_return_arm()')

def idle_return_arm():
    idle_fire();later(.2,'idle_return()')

def idle_return():
    mark('IDLE_OLD_ALERT');command('p5_end')
    later(.45,"mark('IDLE_OFF_BODY')");later(.6,'idle_fire()');later(1.2,"mark('IDLE_OFF_SURVIVED')")
    later(2.4,"mark('IDLE_OFF_DONE')");later(3.3,"mark('IDLE_AFTER_OLD_EXIT')");later(3.6,'idle_reentry_arm()')

def idle_reentry_arm():
    command('p5_cast');later(2.5,'idle_reentry_queue()')

def idle_reentry_queue():
    idle_fire();later(.2,"command('p5_end')");later(.5,"command('p5_cast')")
    later(1.,"mark('IDLE_REENTRY_ACTIVE')");later(3.3,"mark('IDLE_REENTRY_AFTER_EXIT')");later(3.5,'idle_valid_exit()')

def idle_valid_exit():
    import vamputil
    command('Alert_Front_into');__main__.ScheduleTask(3.0,'__main__.ccmd.Alert_Front_outof=""')
    later(.2,"mark('IDLE_VALID_INTO')");later(3.0,'idle_wait_valid_exit()')

def idle_finish():
    command('p5_end');later(2.5,'finish()')


def edges_start():
    command('p5_camera');command('p5_cast');later(.3,'edges_cancel()')

def edges_cancel():
    command('p5_end');later(.1,"mark('CANCEL_EARLY')");later(3.,"mark('CANCEL_LATE')");later(3.2,'edges_female()')

def edges_female():
    command('p5_female');later(.6,"command('p5_cast')");later(.9,'edges_attack()')

def edges_attack():
    command('p5_attack');later(.1,"mark('FEMALE_INTERRUPT_ON')");later(.2,"command('p5_stopattack')");later(1.2,'edges_return()')

def edges_return():
    command('p5_end');later(.3,'edges_jump()')

def edges_jump():
    command('p5_jump');later(.1,"mark('FEMALE_INTERRUPT_OFF')");later(.2,"command('p5_stopjump')");later(2.,'finish()')


idle_exit_checks=0
def idle_wait_valid_exit():
    global idle_exit_checks
    idle_exit_checks=idle_exit_checks+1
    if native_detail().get('sequence_name','').lower().find('outof')>=0:
        mark('IDLE_VALID_OUTOF');later(.4,'idle_finish()');return
    if idle_exit_checks>20:raise RuntimeError('Valid idle exit did not reach native animation')
    later(.05,'idle_wait_valid_exit()')


save_wait_checks=0
def save_active_wait():
    global save_wait_checks
    import nt
    save_wait_checks=save_wait_checks+1
    try:
        if nt.stat(ACTIVE_SAVE)[6]>0:
            mark('SAVE_FILE_CREATED');finish();return
    except:pass
    if save_wait_checks==25:
        mark('SAVE_EARLY_REJECTED');command('p5_save_active')
    if save_wait_checks>60:raise RuntimeError('Owned active save was not created')
    later(.1,'save_active_wait()')


def frenzy_model_mark(label):
    actors=__main__.FindEntitiesByClass('npc_VFrenzyShadow')
    if not actors:raise RuntimeError('Native Shadow missing at model check')
    log((label,frenzy_round,actors[0].GetModelName(),actors[0].GetOrigin()))



def latest_start():
    if native_detail().get('wolf') is None:later(.1,'latest_start()');return
    mark('LATEST_LOADED');command('p5_camera');command('p5_end');__main__.FindPlayer().Bloodgain(15)
    if mode=='latest-walk':setattr(__main__.ccmd,'+speed','')
    later(3.,'latest_cast()')

def latest_cast():
    mark('LATEST_BEFORE')
    if mode=='latest-ui':command('vm_discipline')
    else:command('p5_cast')
    for t in [.1,.45,.9,1.5,2.5]:later(t,"mark('LATEST_ON_"+str(t)+"')")
    later(.45,"command('snapshot')");later(3.,'latest_end()')

def latest_end():
    mark('LATEST_BEFORE_END');command('p5_end')
    for t in [.1,.45,.9,1.5,2.5]:later(t,"mark('LATEST_OFF_"+str(t)+"')")
    later(.45,"command('snapshot')")
    if mode=='latest-walk':later(3.,'latest_walk_interrupt()')
    else:later(3.,'finish()')


def latest_walk_interrupt():
    command('p5_cast');later(.45,"mark('WALK_INTERRUPT_BEFORE')");later(.5,"command('p5_forward')");later(.6,"mark('WALK_INTERRUPT_AFTER')");later(.75,"mark('WALK_MOVE_PROGRESS')");later(.8,"command('p5_stopforward')");later(1.2,'latest_attack_interrupt()')

def latest_attack_interrupt():
    d=native_detail()
    if d.get('sequence_name') not in ['claws_idle','claws_crouch']:later(.1,'latest_attack_interrupt()');return
    mark('WALK_ATTACK_READY');command('p5_end');later(.45,"mark('WALK_ATTACK_BEFORE')");later(.5,"command('p5_attack')");later(.6,"mark('WALK_ATTACK_AFTER')");later(.8,"command('p5_stopattack')");later(2.,'finish()')


def interface_start():
    if native_detail().get('wolf') is None:later(.1,'interface_start()');return
    if not native_detail().get('buttons',0)&0x4000000:later(.1,'interface_start()');return
    mark('INTERFACE_BEFORE');later(3.,'interface_camera()')

def interface_cast():
    mark('INTERFACE_LATCHED');command('p5_cast')
    for t in [.1,.45,.9,1.5,2.5]:later(t,"mark('LATEST_ON_"+str(t)+"')")
    later(.45,"command('snapshot')");later(3.,'latest_end()')


def midload_begin():
    if native_detail().get('state') is None:later(.1,'midload_begin()');return
    command('p5_cast');later(.15,"mark('MID_BEFORE_LOAD_0')");later(.3,"command('p5_otherload')")

def midload_loaded(which):
    snapshot('MID_LOADED_AS_IS_'+str(which));command('p5_cast')
    for t in [.15,.45,.9,2.5]:later(t,"mark('MID_ON_"+str(which)+"_"+str(t)+"')")
    later(3.,'midload_return('+str(which)+')')

def midload_return(which):
    command('p5_end')
    for t in [.15,.45,.9,2.5]:later(t,"mark('MID_OFF_"+str(which)+"_"+str(t)+"')")
    if which==1:later(3.,'midload_second()')
    else:later(3.,'finish()')

def midload_second():
    command('p5_cast');later(.15,"mark('MID_BEFORE_LOAD_1')");later(.3,"command('p5_firstload')")


def interface_camera():
    # The saved bathroom corner collapses the chase camera into the body.
    # Stage only this owned visual fixture in the adjacent open hall.
    p=__main__.FindPlayer();p.SetOrigin((-1765.331665,-1464.379028,-255.96875));p.SetAngles((0,90,0))
    mark('INTERFACE_VISUAL_STAGED');command('p5_camera');later(.6,'interface_cast()')

# Appended to the canonical lifecycle probe; native Python2.1 only.
_canonical_frenzy_setup = frenzy_setup
_canonical_loaded_callback = loaded_callback
_canonical_mapped_callback = mapped_callback
coexist_round=0
coexist_checks=0
coexist_targets=[]

def frenzy_setup():
    command('p5_cast');later(.3,"mark('COEXIST_MORPH_ON_BODY')");later(2.5,'coexist_morph_end()')

def coexist_morph_end():
    if __main__.FindPlayer().active_protean!=5:raise RuntimeError('Protean entry failed')
    mark('COEXIST_MORPH_ON_DONE');command('p5_end');later(.3,"mark('COEXIST_MORPH_OFF_BODY')");later(2.5,'coexist_targets_setup()')

def coexist_targets_setup():
    global coexist_targets,coexist_checks
    p=__main__.FindPlayer()
    if p.active_protean:raise RuntimeError('Protean did not return before melee')
    command('p5_sword');p.GiveItem('item_w_katana');command('p5_sword');p.Bloodgain(100)
    __main__.FindEntityByName('world').SetNoFrenzyArea(0)
    flags=int(native_detail().get('player_flags','0'),16)
    if flags&0x8000:command('notarget')
    if not flags&0x4000:command('god')
    bum=__main__.FindEntityByName('bum_male')
    if bum:bum.ScriptHide()
    home=p.GetOrigin();candidates=[]
    for n in __main__.FindEntitiesByClass('npc_VHumanCombatant'):
        if n.IsAlive() and n.health>0 and n.GetModelName().lower().find('/gangmember_male_2/')>=0:
            xyz=n.GetOrigin();candidates.append(((xyz[0]-home[0])**2+(xyz[1]-home[1])**2+(xyz[2]-home[2])**2,len(candidates),n))
    candidates.sort()
    if len(candidates)<2:raise RuntimeError('Two live native targets required')
    coexist_targets=[candidates[0][2],candidates[1][2]]
    for item in candidates[2:]:item[2].ScriptHide()
    for j in range(2):
        n=coexist_targets[j];n.SetName('fk_target_'+str(j));dx=-(215+j*60)
        n.SetOrigin((home[0]+dx,home[1]+20,home[2]));n.SetAngles((0,math.atan2(-20,-dx)*180/math.pi,0));n.SetRelationship('player D_HT 10')
    coexist_checks=0;later(.3,'coexist_ready()')

def coexist_ready():
    global coexist_checks
    d=native_detail();coexist_checks=coexist_checks+1
    if d.get('item_classes',{}).get(d.get('weapon',''))!='item_w_katana' or len(d.get('targets',[]))!=2 or not all_native_enemies(d['targets'],d.get('player_handle','')):
        if coexist_checks==20:mark('COEXIST_GATE_DEBUG')
        if coexist_checks>150:raise RuntimeError('Native enemy readiness failed')
        later(.1,'coexist_ready()');return
    p=__main__.FindPlayer();p.Bloodgain(100);mark('COEXIST_BEFORE_'+str(coexist_round));log(('COEXIST_BLOOD',p.bloodpool))
    command('p5_frenzy');coexist_checks=0;later(.2,'coexist_confirm()')

def coexist_confirm():
    global coexist_checks
    d=native_detail();coexist_checks=coexist_checks+1
    if not d.get('frenzy',0) or d.get('controller','0xffffffff')=='0xffffffff':
        if coexist_checks>20:raise RuntimeError('Frenzy did not start')
        later(.1,'coexist_confirm()');return
    mark('COEXIST_ACTIVE_'+str(coexist_round))
    if coexist_round==1:later(1.5,'coexist_load_active()')
    else:
        later(6,'coexist_remove_threats()');coexist_checks=0;later(.2,'coexist_wait_end()')

def coexist_remove_threats():
    for n in coexist_targets:n.ScriptHide()

def coexist_wait_end():
    global coexist_checks
    d=native_detail();coexist_checks=coexist_checks+1
    if not d.get('frenzy',0) and d.get('controller','0xffffffff')=='0xffffffff' and d.get('item_classes',{}).get(d.get('inventory',[''])[0])=='item_w_fists':
        mark('COEXIST_END');command('p5_coexist_reload');return
    if coexist_checks>350:raise RuntimeError('Natural Frenzy cleanup timeout')
    later(.2,'coexist_wait_end()')

def loaded_callback():
    later(2,'coexist_loaded()')

def coexist_loaded():
    global coexist_round
    d=native_detail();mark('COEXIST_LOADED')
    if d.get('frenzy',0) or d.get('controller','0xffffffff')!='0xffffffff':raise RuntimeError('Reload left an owned controller')
    coexist_round=1;coexist_targets_setup()

def coexist_load_active():
    mark('COEXIST_BEFORE_MAP_ACTIVE')
    # Use the shipped warehouse landmark/relay route; no direct changelevel.
    __main__.ChangeMap(0,'warehouselandmark','santamonicateleport')

def mapped_callback():
    later(2,'coexist_mapped()')

def coexist_mapped():
    d=native_detail();mark('COEXIST_MAPPED')
    if d.get('frenzy',0) or d.get('controller','0xffffffff')!='0xffffffff':raise RuntimeError('Map transition left a controller')
    log(('COEXIST_MAP',__main__.FindEntitiesByClass('worldspawn')[0].GetModelName()));finish()

if mode != "frenzy-melee":
    frenzy_setup = _canonical_frenzy_setup
    loaded_callback = _canonical_loaded_callback
    mapped_callback = _canonical_mapped_callback

# Fresh delivered BSPs: no SetNoFrenzyArea setter is used in this scenario.
map_checks=0
map_stage=0
def map_ready(stage):
    global map_checks,map_stage
    map_stage=stage;d=native_detail()
    map_checks=map_checks+1
    if map_checks>60:raise RuntimeError('Fresh-map world readiness did not settle')
    if not d.has_key('world_nofrenzy') or d['world_nofrenzy']<0:later(.2,'map_ready('+str(stage)+')');return
    world=__main__.FindEntitiesByClass('worldspawn')[0].GetModelName()
    expected='la_library_1'
    if stage:expected='sp_observatory_2'
    if world.find(expected)<0:raise RuntimeError('Wrong fresh world: '+world)
    if d['world_nofrenzy']!=0:raise RuntimeError('Delivered BSP still forbids Frenzy')
    if d.get('frenzy') or d.get('shadow_actors'):raise RuntimeError('Fresh map retained Frenzy ownership')
    log(('MAP_PERMISSION',stage,world,d['world_nofrenzy']))
    p=__main__.FindPlayer();p.Bloodgain(15)
    if p.base_protean<5:command('p5_buy');later(.3,'map_ready('+str(stage)+')');return
    map_checks=0;mark('MAP_BEFORE_'+str(stage));command('p5_cast');later(3.,'map_frenzy('+str(stage)+')')
def map_frenzy(stage):
    if stage:
        w=__main__.FindEntityByName('werewolf')
        if not w or not w.IsAlive():raise RuntimeError('No live native werewolf')
        __main__.FindEntityByName('cutscene_end').Trigger()
        later(2.,'map_approach()');return
    n=__main__.FindEntityByName('guard1');n.ScriptUnhide();xyz=n.GetOrigin()
    __main__.FindPlayer().SetOrigin((xyz[0]+100,xyz[1],xyz[2]));n.SetRelationship('player D_HT 10')
    later(.6,'map_library_begin()')
def map_library_begin():
    command('p5_frenzy');later(.3,'map_seen(0)')
def map_approach():
    w=__main__.FindEntityByName('werewolf');xyz=w.GetOrigin();p=__main__.FindPlayer()
    p.SetOrigin((xyz[0]+240,xyz[1],xyz[2]));w.SetRelationship('player D_HT 10')
    mark('MAP_APPROACH');command('p5_frenzy');later(.3,'map_seen(1)')
def map_seen(stage):
    global map_checks
    d=native_detail();map_checks=map_checks+1
    if d.get('frenzy',0)>0 and len(d.get('shadow_actors',[]))==1:
        mark('MAP_FRENZY_'+str(stage))
        log(('MAP_FILTER',stage,__main__.cvar.feedvision))
        if not stage:finish();return
        map_checks=0;later(.2,'map_contact()');return
    if map_checks>50:raise RuntimeError('Native Frenzy did not start on fresh map')
    later(.1,'map_seen('+str(stage)+')')
def map_contact():
    global map_checks
    d=native_detail();p=__main__.FindPlayer();w=__main__.FindEntityByName('werewolf')
    log(('MAP_CONTACT',d,p.health,w.health,p.IsAlive(),w.IsAlive()))
    map_checks=map_checks+1
    if map_checks<75:later(.2,'map_contact()');return
    w.ScriptHide();map_checks=0;later(.2,'map_end()')
def map_end():
    global map_checks
    d=native_detail();map_checks=map_checks+1
    if not d.get('frenzy',0) and not d.get('shadow_actors') and d.get('controller')=='0xffffffff':
        mark('MAP_END');finish();return
    if map_checks>500:raise RuntimeError('Frenzy did not clean up after contact')
    later(.2,'map_end()')

def filter_state(label):
    p=__main__.FindPlayer()
    log(('FILTER_STATE',label,p.active_protean,int(__main__.cvar.mat_fullbright),int(__main__.cvar.feedvision)))
    mark('FILTER_'+label);command('snapshot')
def filter_initial():
    # A queued reload would be serialized into this save and reload it forever.
    filter_state('INITIAL');command('p5_filter_save');finish()
def filter_loaded():
    filter_state('LOADED');command('p5_end');later(1.,'filter_red()')
def filter_red():
    __main__.cvar.feedvision='10';later(.8,'filter_red_save()')
def filter_red_save():
    filter_state('RED_INITIAL');finish()

claw_routes=__CLAW_ROUTES__
def dependencies_off():
    import vamputil
    log(('NATIVE_OFF_READY',getattr(vamputil,'_proteanNativeReady',0)))
    if getattr(vamputil,'_proteanNativeReady',0):raise RuntimeError('Disabled inventory published native morph readiness')
    command('p5_cast');later(3.,'dependencies_off_active()')
def dependencies_off_active():
    import vamputil
    if getattr(vamputil,'_proteanNativeReady',0):raise RuntimeError('Dependent readiness became active')
    mark('OFF_ACTIVE');command('p5_end');later(3.,'finish()')
claw_cases=[(0,[]),(512,['moveleft']),(1024,['moveright']),(8,['forward']),(16,['back']),(520,['forward','moveleft']),(1032,['forward','moveright'])]
claw_case=0
claw_link=0
claw_sent=0
claw_checks=0
def claws_start():
    if mode.endswith('female'):command('p5_female')
    else:command('p5_male')
    command('p5_camera')
    later(.6,'claws_cast()')
def claws_cast():
    command('p5_cast');later(1.,'claws_reset()')
def claws_reset():
    global claw_link,claw_sent,claw_checks
    p=__main__.FindPlayer();p.SetOrigin((53.9539451599,-86.8017578125,-39.96875))
    d=native_detail();seq=d.get('sequence_name','').lower()
    if seq=='claws_crouch':command('p5_duck');later(.08,"command('p5_unduck')");later(.5,'claws_reset()');return
    if seq not in ['claws_idle','claws_ready','claws_fidget']:later(.1,'claws_reset()');return
    claw_link=0;claw_sent=0;claw_checks=0
    if claw_case>=len(claw_cases):later(.4,'claws_air()');return
    for name in claw_cases[claw_case][1]:command('p5_'+name)
    later(.1,'claws_click()');later(.14,'claws_chain()')
def claws_click():
    command('p5_attack');later(.045,"command('p5_stopattack')")
def claws_chain():
    global claw_link,claw_sent,claw_checks,claw_case
    d=native_detail();claw_checks=claw_checks+1;chain=claw_routes[claw_cases[claw_case][0]]
    seq=d.get('sequence_name','');cycle=d.get('cycle',0)
    if claw_checks>240:raise RuntimeError('Claws chain timeout: '+repr((claw_case,claw_link,d)))
    if seq==chain[claw_link][0]:
        if not claw_sent:
            log(('CLAW_LINK',claw_case,claw_link,seq));claw_sent=1
            for name in claw_cases[claw_case][1]:command('p5_stop'+name)
        if claw_link<len(chain)-1 and cycle>=chain[claw_link][1]-.03 and claw_sent==1:
            claws_click();claw_sent=2
    if claw_link<len(chain)-1 and seq==chain[claw_link+1][0]:
        claw_link=claw_link+1;claw_sent=0
    if claw_link==len(chain)-1 and claw_sent and seq in ['claws_idle','claws_ready','claws_fidget']:
        log(('CLAW_CHAIN',claw_case));claw_case=claw_case+1;later(.3,'claws_reset()');return
    later(.025,'claws_chain()')
def claws_air():
    command('p5_jump');later(.1,'claws_click()');later(.12,'claws_air_seen()');later(.2,"command('p5_stopjump')")
def claws_air_seen():
    d=native_detail()
    if d.get('sequence_name','').lower()=='claws_air':mark('CLAW_AIR');later(2.,'claws_block()');return
    later(.025,'claws_air_seen()')
def claws_block():
    command('p5_attack2');later(.4,"mark('CLAW_BLOCK')");later(.7,"command('p5_stopattack2')");later(1.,'claws_block_end()')
def claws_block_end():
    mark('CLAW_RELEASE');command('p5_end');later(.4,'claws_sneak_fresh()')
def claws_sneak_fresh():
    command('p5_cast');later(.6,'claws_sneak_crouch()')
def claws_sneak_crouch():
    command('p5_duck');later(.08,"command('p5_unduck')");later(.5,'claws_sneak()')
claw_direction=0
claw_directions=[['forward'],['forward','moveleft'],['moveleft'],['back','moveleft'],['back'],['back','moveright'],['moveright'],['forward','moveright']]
def claws_sneak():
    if claw_direction>=8:finish();return
    for name in claw_directions[claw_direction]:command('p5_'+name)
    later(.2,'claws_sneak_end()')
def claws_sneak_end():
    global claw_direction
    mark('CLAW_SNEAK_'+str(claw_direction))
    for name in claw_directions[claw_direction]:command('p5_stop'+name)
    claw_direction=claw_direction+1;later(.35,'claws_sneak()')

# Embedded Python 2.1 test-only timeline. Appended to game_probe.py by the runner.
native_targets=[]
native_checks=0
native_expected='item_w_claws'

def native_hunger_start():
    import vamputil
    log(('STOCK_SUPPORT_ABSENT',int(hasattr(vamputil,'_proteanNativeReady')),int(hasattr(vamputil,'_queueProteanIdleExit'))))
    if hasattr(vamputil,'_proteanNativeReady') or hasattr(vamputil,'_queueProteanIdleExit'):raise RuntimeError('Modified production Python remains installed')
    if not native_detail().get('ai_flags',1):command('ai_disable')
    p=__main__.FindPlayer();__main__.G.No_Idle=1
    if p.active_protean:command('p5_end')
    e=__main__.FindEntityByName('events_player_plus')
    if not e:raise RuntimeError('Plus event fixture missing')
    if mode.find('outputs')>=0:e.EnableOutputs()
    else:e.DisableOutputs()
    later(.8,'native_hunger_prepare()')

def native_hunger_prepare():
    global native_checks,native_expected
    native_checks=native_checks+1
    if native_checks>60:raise RuntimeError('Native hunger preparation timeout')
    p=__main__.FindPlayer()
    if p.active_protean:command('p5_end');later(.2,'native_hunger_prepare()');return
    wanted=0
    if mode.find('warform')>=0:wanted=5
    if mode.find('claws2')>=0:wanted=2
    if wanted and p.base_protean<wanted:command('p5_buy');later(.2,'native_hunger_prepare()');return
    if wanted and p.base_protean>wanted:command('p5_sell');later(.2,'native_hunger_prepare()');return
    p.Bloodgain(15);p.HumanityAdd(10);p.HumanityAdd(-7)
    __main__.FindEntityByName('world').SetNoFrenzyArea(0)
    flags=int(native_detail().get('player_flags','0'),16)
    if flags&32768:command('notarget')
    if not flags&16384:command('god')
    if wanted:command('p5_cast')
    else:command('p5_unarmed')
    if mode.find('katana')>=0:p.GiveItem('item_w_katana');native_expected='item_w_katana'
    elif mode.find('tiger')>=0:p.GiveItem('item_w_chang_claw');native_expected='item_w_chang_claw'
    later(2.5,'native_hunger_targets()')

def native_hunger_targets():
    global native_targets,native_checks
    p=__main__.FindPlayer();home=p.GetOrigin();d=native_detail()
    if not d.get('view_angles'):raise RuntimeError('Actual view unavailable for target placement')
    angles=(0,d['view_angles'][1],0)
    native_targets=[__main__.FindEntityByName(n) for n in ['NPC_Sabbat1','NPC_Sabbat2']]
    if not native_targets[0] or not native_targets[1]:raise RuntimeError('Pinned native enemy pair missing')
    for name in ['ExplodeDoor_1_Event','Seq_Sabbat_Landing']:
        e=__main__.FindEntityByName(name)
        if e:e.Kill()
    for cls in ['npc_VHumanCombatant','npc_VVampire','npc_VVampireBoss','npc_VPedestrian']:
        for n in __main__.FindEntitiesByClass(cls):
            if n not in native_targets:n.ScriptHide()
    for j in range(2):
        n=native_targets[j];n.ScriptUnhide();n.SetName('fk_target_'+str(j));n.SetRelationship('player D_NU 10')
        r=angles[1]*math.pi/180;x,y=[(140,-50),(160,50)][j]
        n.SetOrigin((home[0]+x*math.cos(r)-y*math.sin(r),home[1]+x*math.sin(r)+y*math.cos(r),home[2]+.1));n.SetAngles((0,angles[1]+180,0))
    if native_expected=='item_w_katana':command('p5_sword')
    elif native_expected=='item_w_chang_claw':command('p5_tiger')
    elif p.active_protean:command('p5_claws')
    native_checks=0;later(.6,'native_hunger_ready()')

def native_hunger_ready():
    global native_checks
    native_checks=native_checks+1;p=__main__.FindPlayer();d=native_detail()
    if native_expected!='item_w_claws' and not p.HasWeaponEquipped(native_expected):
        if native_checks>20:raise RuntimeError('Selected native weapon was not equipped')
        if native_expected=='item_w_katana':command('p5_sword')
        else:command('p5_tiger')
        later(.2,'native_hunger_ready()');return
    if mode.find('warform')>=0 and (p.active_protean!=5 or not p.HasWeaponEquipped('item_w_claws')):raise RuntimeError('Warform claws not ready')
    if mode.find('claws2')>=0 and (p.active_protean!=2 or not p.HasWeaponEquipped('item_w_claws')):raise RuntimeError('P2 claws not ready')
    r=d['view_angles'][1]*math.pi/180;home=p.GetOrigin()
    for n in native_targets:
        xyz=n.GetOrigin();dx=xyz[0]-home[0];dy=xyz[1]-home[1]
        forward=dx*math.cos(r)+dy*math.sin(r);side=-dx*math.sin(r)+dy*math.cos(r)
        log(('NATIVE_TARGET_VIEW',forward,side))
        if forward<100 or abs(side)>70:raise RuntimeError('Enemy not in front of actual view')
    mark('NATIVE_HUNGER_BEFORE')
    if d.get('ai_flags',0):command('ai_disable')
    p.Bloodloss(p.bloodpool+1)
    for n in native_targets:n.SetRelationship('player D_HT 10')
    mark('NATIVE_HUNGER_ZERO');native_checks=0;later(.1,'native_hunger_wait()')

def native_hunger_wait():
    global native_checks
    native_checks=native_checks+1;d=native_detail();shadows=d.get('shadow_actors',[])
    if d.get('frenzy',0) and len(shadows)==1 and shadows[0].get('weapon_class')==native_expected:
        mark('NATIVE_HUNGER_ENTER')
        if not d.get('ai_flags',1):command('ai_disable')
        later(.5,'native_hunger_settled()');return
    if native_checks>150:raise RuntimeError('Natural Frenzy did not equip expected Shadow weapon: '+native_expected+' '+repr(d))
    later(.1,'native_hunger_wait()')

def native_hunger_settled():
    mark('NATIVE_HUNGER_SETTLED')
    later(.05,'native_hunger_repeat_callback()')

def native_hunger_repeat_callback():
    import vamputil
    if not native_detail().get('frenzy',0):raise RuntimeError('Frenzy ended before duplicate-effect control')
    vamputil.OnFrenzyBegin();vamputil.OnFrenzyBegin()
    later(.3,'native_hunger_after_callback()')

def native_hunger_after_callback():
    mark('NATIVE_HUNGER_AFTER_CALLBACK')
    if native_detail().get('ai_flags',0):command('ai_disable')
    later(.8,'native_hunger_release()')

def native_hunger_release():
    global native_checks
    for n in native_targets:
        try:n.SetRelationship('player D_NU 10');n.ScriptHide()
        except:pass
    __main__.FindPlayer().Bloodgain(15);native_checks=0
    later(.2,'native_hunger_end()')

def native_hunger_end():
    global native_checks
    native_checks=native_checks+1;d=native_detail()
    if not d.get('frenzy',0) and d.get('controller','0xffffffff')=='0xffffffff':
        mark('NATIVE_HUNGER_RETURN');command('p5_forward');later(.2,"command('p5_stopforward')");later(.3,'native_hunger_finish()');return
    if native_checks>220:raise RuntimeError('Natural Frenzy failed to release its controller')
    later(.2,'native_hunger_end()')

def native_hunger_finish():
    mark('NATIVE_HUNGER_MOVED');command('p5_end');later(2.5,'finish()')
