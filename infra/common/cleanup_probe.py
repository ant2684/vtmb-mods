# Task-only native Python 2.1 API fixture. Never enters a gameplay package.
import __main__,sys,time,math
OUT='probe.txt' # Session.ps1 sets the verified external session destination.
gp_ticks=0

def gp_tick():
    global gp_ticks
    record('gp_health_tick')
    gp_ticks=gp_ticks+1
    if gp_ticks<110:__main__.ScheduleTask(0.2,"__import__('cleanup_probe').gp_tick()")
def log(label,value):
    f=open(OUT,'a');f.write(repr((time.time(),label,value))+'\n');f.close()
def describe(e):
    r={}
    for key in ('base_protean','active_protean','base_auspex','active_auspex','strength','stamina','wits','base_strength','base_stamina','base_wits','health','bloodpool','humanity'):
        try:r[key]=getattr(e,key)
        except:pass
    for key in ('GetName','GetModelName','GetOrigin','IsAlive'):
        try:r[key]=getattr(e,key)()
        except:pass
    for key in ('Close_Combat_Brawl','Soak_Lethal'):
        try:r[key]=e.CalcFeat(key)
        except:pass
    return r
def record(label):
    p=__main__.FindPlayer();r={'player':describe(p),'world':__main__.FindEntitiesByClass('worldspawn')[0].GetModelName(),'shadow':[],'wolf':[]}
    for key in ('mat_fullbright','feedvision'):
        try:r[key]=getattr(__main__.cvar,key)
        except:pass
    for e in __main__.FindEntitiesByClass('npc_VFrenzyShadow'):r['shadow'].append(describe(e))
    for e in __main__.FindEntitiesByClass('npc_VWerewolf'):r['wolf'].append(describe(e))
    log(label,r)
def action(label):
    try:
        p=__main__.FindPlayer()
        if label=='prepare':
            __main__.ccmd.rc_end=''
            # SetNoFrenzyArea belongs to events_world, not worldspawn.
            __main__.FindEntityByName('world').SetNoFrenzyArea(0)
            while p.base_protean<5:p.BumpStat('Protean',1)
            p.Bloodgain(15)
        elif label=='rank4':
            for i in range(p.base_protean-4):__main__.ccmd.rc_sell=''
            p.Bloodgain(15)
        elif label=='redvision':
            __main__.ccmd.rc_end=''
            __main__.cvar.feedvision='10'
        elif label=='redvision_off':__main__.cvar.feedvision='0'
        elif label=='cast':p.Bloodgain(15);__main__.ccmd.rc_cast=''
        elif label=='frenzy':__main__.ccmd.rc_frenzy=''
        elif label=='repeat':__main__.ccmd.rc_frenzy='';__main__.ccmd.rc_frenzy=''
        elif label=='end':__main__.ccmd.rc_end=''
        elif label=='warehouse_targets':
            p.SetOrigin((707.2733,1949.6235,-319.96875))
            distractor=__main__.FindEntityByName('bum_male')
            if distractor:distractor.ScriptHide()
            targets=[]
            for e in __main__.FindEntitiesByClass('npc_VHumanCombatant'):
                try:
                    if e.GetName().find('fk_target_')==0:e.SetName('fk_previous_'+e.GetName())
                    if e.GetName().find('fk_previous_')==0:continue
                    if e.IsAlive() and e.health>0 and e.GetModelName().lower().find('/gangmember_male_2/')>=0:
                        xyz=e.GetOrigin();targets.append(((xyz[0]-707.2733)**2+(xyz[1]-1949.6235)**2+(xyz[2]+319.96875)**2,len(targets),e))
                except:pass
            if len(targets)<2:raise RuntimeError('Two native live warehouse targets unavailable')
            targets.sort()
            for i in (0,1):
                e=targets[i][2];e.SetName('fk_target_%d'%i)
                e.SetOrigin((492.2733-i*60,1969.6235,-319.96875));e.SetAngles((0,math.atan2(-20,215+i*60)*180/math.pi,0));e.SetRelationship('player D_HT 10')
                log('prepared_native_target',describe(e))
        elif label=='gp_prepare':
            w=__main__.FindEntityByName('werewolf')
            if not w:raise RuntimeError('Native werewolf absent')
            if not w.IsAlive():raise RuntimeError('Native werewolf is dead')
            log('native_werewolf',describe(w))
        elif label=='gp_start_encounter':
            # Reuse the map's normal scene-completion relay and its outputs.
            __main__.FindEntityByName('cutscene_end').Trigger()
        elif label=='gp_track':
            gp_tick()
        elif label=='gp_stop_combat':
            # Contact is already recorded; suspend only this unsaved test actor
            # while waiting for ordinary native Frenzy completion.
            __main__.FindEntityByName('werewolf').ScriptHide()
        elif label=='gp_approach':
            w=__main__.FindEntityByName('werewolf');xyz=w.GetOrigin()
            p.SetOrigin((xyz[0]+240,xyz[1],xyz[2]));w.SetRelationship('player D_HT 10')
        elif label=='map':__main__.ChangeMap(0,'warehouselandmark','santamonicateleport')
        elif label=='gp_map':__main__.ccmd.rc_map=''
        elif label!='record':raise RuntimeError('Unknown action')
        __main__.ScheduleTask(0.2,"__import__('cleanup_probe').record('%s')"%label)
    except:
        log('ERROR',(label,str(sys.exc_info()[0]),str(sys.exc_info()[1])))
