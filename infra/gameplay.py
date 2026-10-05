"""Fresh scenario contracts and fail-closed external evidence audit.

Collectors run only through an explicitly configured command and transaction.
The historical recipes remain available, but their dated PASS certificates are
never consumed by this fresh-run interface.
"""
import json
import sys
import time
from pathlib import Path
from infra.core import ROOT, Blocked, atomic_json, catalog, digest, need, read_json, require, run
from infra.release import members
from infra.session import Transaction

SCENARIOS = [
    {'id':'console.supported','mod':'console','timeout':240,'save':'console','expected':'X/tilde preserve owned ordinary/menu/script pauses; after measured five-second external wait first signed movement/camera succeeds; reload remains usable','checks':['console_x','console_tilde','ordinary_pause','prior_menu','script_pause','first_input','reload']},
    {'id':'console.immediate','mod':'console','timeout':120,'save':'console','expected':'First movement/camera event following native observed close is received without readiness wait; record actual delay and first failure','checks':['close_observed','first_input']},
    {'id':'protean.lifecycle','mod':'protean','timeout':300,'save':'warehouse','expected':'P5 plus native Frenzy owns one Shadow; repeated request has no extra bonus; either state ends first; nominated archival load/map clear stale state','checks':['single_shadow','no_bonus_growth','protean_ends_first','frenzy_ends_first','active_load','active_map','cleanup']},
    {'id':'protean.filter','mod':'protean','timeout':240,'save':'warehouse','expected':'Saved-active P4 filter survives two reloads; off restores mat_fullbright=0; independent RedVision remains intact','checks':['filter_reload_1','filter_reload_2','filter_off','redvision_reload']},
    {'id':'protean.fourhit','mod':'protean','timeout':240,'save':'claws','expected':'Resolve actual weapon/model sequences; four distinct hit windows terminate; interrupt/restart and edition-specific block work','checks':['four_hits','terminates','interrupt_restart','block','resolved_resource']},
    {'id':'frenzy.library','mod':'frenzy','timeout':150,'save':'library','expected':'Exact delivered Library BSP is selected; native frenzyplayer creates owned Shadow in the formerly forbidden area; cleanup follows','checks':['permission','native_frenzy','cleanup','resolved_resource']},
    {'id':'frenzy.griffith','mod':'frenzy','timeout':240,'save':'griffith','expected':'Exact Griffith BSP and native living Werewolf; damaging approach <160 XY, no original-player ground support, ordinary/P5 contexts, end/load/map cleanup','checks':['normal_contact','warform_contact','no_body_support','scope_forwarding','end','load','map','cleanup','resolved_resource']},
    {'id':'subtitle.radio','mod':'subtitle','timeout':720,'save':'radio','expected':'Pause/on/off/repeat/TV transitions/saved-on/load and an unaccelerated real loop preserve correlated PCM/decoder/caption coordinates','checks':['pause','first_on','repeat_on','off_epoch','tv_radio','radio_tv','saved_on','load_return','real_loop','audio_caption_correlation']},
    {'id':'background.cinematics','mod':'background','timeout':240,'save':'radio','expected':'Two actual native cutscenes omit fill/border while text, placement, wrapping and ordinary dialogue remain; save/map retain patch','checks':['scene_a','scene_b','same_text_bounds','ordinary_dialogue','load','map']},
    {'id':'history.transitions','mod':'history','timeout':300,'save':None,'expected':'Non-None/None purchases to gender reset removes allocation/bonus; complete fresh pool is spendable, extras rejected; Base/Sheet/Accept retain new purchases','checks':['non_none_gender','none_gender','reverse_gender','fresh_pool','exhausted_reject','base_sheet','accept','repeat_history_once']},
    {'id':'history.bounded_resets','mod':'history','timeout':180,'save':None,'expected':'Bounded reset sequence records entity-slot growth without claiming unlimited endurance; every reset retains correct allocation and fresh pool','checks':['allocation_reset','pool_reset','entity_budget']},
]


def audit(scenario, evidence, identity):
    """A fresh certificate binds each native before/after record to its inputs."""
    require(evidence.get('session')==identity['session'],'Evidence from another session')
    require(evidence.get('scenario')==scenario['id'] and evidence.get('scenario_version')==1,'Wrong scenario/version')
    require(evidence.get('artifacts')==identity['artifacts'],'Wrong/stale artifact identity')
    require(evidence.get('modules')==identity['modules'],'Wrong native module identity')
    require(evidence.get('save_sha256')==identity['save_sha256'],'Wrong nominated save')
    require(evidence.get('first_result_preserved') is True,'First result not retained')
    require(evidence.get('resolved_resources')==identity['resources'],'Actual resource selection unproven')
    observations=evidence.get('observations',[])
    require(len({r['check'] for r in observations})==len(observations),'Duplicate check records')
    by={r['check']:r for r in observations}
    require(set(by)==set(scenario['checks']),'Missing or unrecognized checks')
    for name in scenario['checks']:
        row=by[name]
        require(row.get('expected') is True and row.get('observed') is True,'Normative requirement must be satisfied: '+name)
        require(isinstance(row.get('before'),dict) and bool(row['before']) and isinstance(row.get('after'),dict) and bool(row['after']),'Native before/after observations absent: '+name)
        require(isinstance(row.get('elapsed_seconds'),(int,float)) and 0<=row['elapsed_seconds']<=scenario['timeout'],'Unbounded observation: '+name)
        require(row.get('source') in ['native-process-read','native-console-readback','offline-native-getter','process-wasapi-plus-native'],'Unproven observation source: '+name)
    # Requirement-specific metrics prevent a generic passed=True replacing proof.
    metrics=evidence.get('metrics',{})
    if scenario['id'].startswith('console.'):
        require(metrics.get('native_back_held') is True and metrics.get('native_forward_held') is True,'OS input alone is insufficient')
        require(metrics.get('signed_back',0)<0<metrics.get('signed_forward',0),'Signed movement missing')
        require(metrics.get('camera_left',0)<0<metrics.get('camera_right',0),'Both camera directions required')
        require(metrics.get('world_time_delta',0)>0,'World did not resume')
        last=by['first_input']['after']
        require(last.get('mouse_active')==1 and all(last.get(n)==0 for n in ['paused','server_paused','menu_pause_depth']),'Native resumed input/world ownership missing')
        if scenario['id']=='console.immediate':
            before,after=by['close_observed']['before'],by['close_observed']['after']
            require(isinstance(before.get('console'),dict) and before['console'].get('visible')==1 and isinstance(after.get('console'),dict) and after['console'].get('visible')==0,'Native console close transition missing')
        if scenario['id']=='console.immediate':require(0<=metrics.get('first_input_after_close_seconds',999)<=0.25,'Immediate test delayed first event; report measured delay')
        else:require(4.9<=metrics.get('external_wait_seconds',0)<=5.1,'Supported-scope readiness wait differs')
    if scenario['id']=='protean.fourhit':
        hits=metrics.get('hit_windows',[])
        require(len(hits)==4 and len({x['event'] for x in hits})==4,'Not four distinct native hit events')
        sequences=metrics.get('resolved_sequences',[])
        require(len(sequences)==4 and all(x['damage']>0 and x['weapon']==metrics.get('weapon') and x['sequence']==sequences[i] for i,x in enumerate(hits)),'Hit window/weapon/sequence not correlated')
        require(all(hits[i]['time']<hits[i+1]['time'] for i in range(3)),'Hit windows not ordered')
        require(metrics.get('fifth_hit') is False and metrics.get('new_restart_first_sequence')==sequences[0],'Chain does not terminate/restart')
    if scenario['id']=='frenzy.griffith':
        require(0<metrics.get('closest_active_xy',999)<160 and metrics.get('native_damage',0)>0,'No active damaging contact in correction scope')
        require(metrics.get('ground_handle')!=metrics.get('original_player_handle') and metrics.get('original_player_handle') is not None,'Original player used as ground')
    if scenario['id']=='frenzy.library':
        require(by['permission']['after'].get('nofrenzyarea')==0,'Library permission not observed')
        native=by['native_frenzy']['after']
        require(native.get('command')=='frenzyplayer' and native.get('owned_shadow_count')==1,'Native Library Frenzy not established')
        require(native.get('shadow_handle') and native.get('player_handle') and native['shadow_handle']!=native['player_handle'],'Independent owned Shadow missing')
        require(by['cleanup']['after'].get('owned_shadow_count')==0,'Library Shadow cleanup incomplete')
        library={p:h for p,h in identity['resources'].items() if 'library' in p.lower() and p.endswith('.bsp')}
        require(len(library)==1 and by['resolved_resource']['after'].get('resources')==library,'Exact selected Library BSP unproven')
    if scenario['id']=='history.bounded_resets':
        slots=metrics.get('entity_slots',[])
        require(2<=len(slots)<=8 and all(isinstance(x,int) and 0<=x<1800 for x in slots),'Bounded safe entity budget not recorded')
    if scenario['id']=='history.transitions':
        for name in ['non_none_gender','none_gender','reverse_gender']:
            before,after=by[name]['before'],by[name]['after']
            require(before.get('purchased_points',0)>0,'Transition must start with actual purchases')
            require(after.get('history')==-1 and after.get('purchased_points')==0 and after.get('history_bonus')==0 and after.get('pool')==[3,6,1],'Gender reset preserves allocation or duplicates pool')
        require(by['non_none_gender']['before'].get('history',0)>0 and by['non_none_gender']['before'].get('history_bonus',0)>0,'Actual bonus History required')
        require(metrics.get('new_purchases')==[3,6,1] and metrics.get('rejected_exhausted_categories')==7,'Fresh pool/exhausted categories not proven')
        require(by['base_sheet']['before'].get('allocation')==by['base_sheet']['after'].get('allocation') and by['base_sheet']['after'].get('allocation'),'Base/Sheet lost new allocation')
        require(by['accept']['before'].get('allocation')==by['accept']['after'].get('allocation') and by['accept']['after'].get('creation_funding')==0,'Accept lost allocation or retained creation funding')
        require(metrics.get('history_bonus_applications')==1,'Repeated History accumulated bonus')
    if scenario['id']=='protean.lifecycle':
        require(metrics.get('native_frenzy_command')=='frenzyplayer' and metrics.get('max_owned_shadows')==1,'Wrong native Frenzy route or duplicate Shadow')
        require(metrics.get('feats_before_repeat')==metrics.get('feats_after_repeat') and metrics.get('feats_before_repeat') is not None,'Repeated bonus growth')
        for key in ['protean_ends_first','frenzy_ends_first']:
            after=by[key]['after']
            require(after.get('protean_active')==(key=='frenzy_ends_first') and after.get('frenzy_active')==(key=='protean_ends_first'),'Wrong lifecycle order')
        require(by['cleanup']['after'].get('shadow_count')==0,'Shadow cleanup incomplete')
    if scenario['id']=='protean.filter':
        require(metrics.get('mat_fullbright_after_reload')==[1,1] and metrics.get('mat_fullbright_off')==0,'Filter ConVar transition wrong')
        require(metrics.get('normal_brightness',0)>0 and all(x>1.5*metrics['normal_brightness'] for x in metrics.get('active_brightness',[])) and len(metrics.get('active_brightness',[]))==3,'Filter brightness missing')
        require(metrics.get('redvision_mat_fullbright')==0 and metrics.get('redvision_preserved') is True,'Independent RedVision damaged')
    if scenario['id']=='background.cinematics':
        require(metrics.get('positive_fade_scenes')==2 and metrics.get('fill_calls')==0 and metrics.get('border_calls')==0,'Native cinematic draw still present')
        require(metrics.get('text_before')==metrics.get('text_after') and metrics.get('text_after'),'Caption text changed/missing')
        require(metrics.get('bounds_before')==metrics.get('bounds_after') and metrics.get('bounds_after'),'Caption placement/wrapping changed')
    if scenario['id']=='subtitle.radio':
        require(metrics.get('loop_samples')==18801792 and metrics.get('time_or_seek_manipulation') is False,'Real recorded native loop not exercised')
        require(metrics.get('process_pcm_sha256') and metrics.get('source_audio_sha256') and metrics.get('correlation_score',0)>=0.7,'Independent process PCM correlation absent')
    return {'result':'PASS','session':identity['session'],'scenario':scenario['id'],'artifacts':identity['artifacts'],'scope':scenario['expected'],'first_result_preserved':True}


def windows(config,action,folder,source=None):
    command=[config.get('powershell','pwsh'),'-NoProfile','-File',ROOT/'infra/windows.ps1','-Action',action,'-GameRoot',need(config,'game_root'),'-LaunchUser',need(config,'launch_user'),'-OutputFile',folder/('process.json' if action=='Launch' else 'settings-current.json')]
    if source:command+=['-InputFile',source]
    return run(command,timeout=45)


def execute(name,config,run_id,historical=False,candidate=None):
    scenario=next(s for s in SCENARIOS if s['id']==name)
    if historical:
        raise Blocked('Historical certificate is not a new result. Use the retained mods/'+scenario['mod']+'/tests audit with the original external evidence; fresh gameplay uses this scenario contract.')
    command=config.get('gameplay_commands',{}).get(name)
    if not command and name=='console.immediate':
        command=['{python}','-B','-m','infra.console_immediate','{session}']
    if not isinstance(command,list) or not command:
        raise Blocked('Configure an inspected native collector command for '+name+' in gameplay_commands. Contract: docs/gameplay.md. Retained recipes are inputs, not automatic PASS adapters.')
    save=Path(config.get('saves',{}).get(scenario['save'],'')) if scenario['save'] else None
    if save is not None and not save.is_file():
        raise Blocked('Nominate archival save for '+str(scenario['save'])+'; original is never substituted')
    from infra.native import exact
    native_result=exact(scenario['mod'],config,candidate)
    game=Path(need(config,'game_root')).resolve()
    import tempfile
    with tempfile.TemporaryDirectory(prefix='vtmb-preflight-') as preflight:
        windows(config,'Inspect',Path(preflight))
        if read_json(Path(preflight)/'settings-current.json')['Processes']:
            raise Blocked('User game is running; no installation transaction is started')
    transaction=Transaction(game,need(config,'state_root'))
    folder=transaction.start()
    restored=False
    try:
        windows(config,'Inspect',folder)
        settings=read_json(folder/'settings-current.json')
        require(not settings['Processes'],'User game running; refuse mutation')
        atomic_json(folder/'settings.json',settings)
        transaction.watch_inventory()
        for directory in ['Bin/loader','Unofficial_Patch/cfg','Vampire/cfg','Unofficial_Patch/save','Vampire/save','Unofficial_Patch/python','Unofficial_Patch/resource']:
            for file in (game/directory).rglob('*'):
                if file.is_file():transaction.preserve(file.relative_to(game).as_posix())
        artifacts={};resources={}
        for member,data in members(Path(need(config,'releases'))/catalog()['mods'][scenario['mod']]['archive']).items():
            if member=='README.txt':continue
            if candidate and member=='Bin/loader/'+catalog()['mods'][scenario['mod']]['filename']:
                data=Path(candidate).read_bytes()
                require(__import__('infra.core',fromlist=['sha']).sha(data)==native_result['sha256'],'Candidate changed after exact tests')
            transaction.write(member,data);artifacts[member]=digest(game/member)
            if member.endswith(('.bsp','.mdl')):resources[member]=artifacts[member]
        if name=='protean.fourhit':
            edition=need(config,'model_archive')
            require(edition in catalog()['archives'] and 'Four-hit Combos' in edition,'Select one exact accepted four-hit edition')
            for member,data in members(Path(config['releases'])/edition).items():
                if member!='README.txt':transaction.write(member,data);resources[member]=digest(game/member);artifacts[member]=resources[member]
        # Only predeclared engine outputs can be restored/deleted automatically.
        for relative in config.get('runtime_outputs',[]):transaction.allow_runtime(relative)
        for file in (game/'Unofficial_Patch/cfg').glob('*.cfg'):transaction.allow_runtime(file.relative_to(game).as_posix())
        stem='rc_'+transaction.data['id'][:12]
        args=['-game','Unofficial_Patch','-dev','-novid','-console']
        if save:
            relative='Unofficial_Patch/save/'+stem+'.sav'
            transaction.write(relative,save.read_bytes());args+=['+load',stem]
        identity={'session':run_id+'_'+name,'scenario_version':1,'scenario':name,'artifacts':artifacts,'resources':resources,'modules':{n:digest(game/n) for n in catalog()['native_modules']},'save_sha256':digest(save) if save else None}
        atomic_json(folder/'identity.json',identity)
        atomic_json(folder/'launch.json',{'GameRoot':str(game),'Arguments':args,'Candidates':[{'Path':str(game/n),'Hash':h} for n,h in artifacts.items()],'Save':stem,'SaveHash':identity['save_sha256'],'PluginHash':native_result['sha256']})
        transaction.launch_intent(game/'Vampire.exe',args)
        windows(config,'Launch',folder,folder/'launch.json')
        owned=read_json(folder/'process.json');transaction.owned_process(owned['Id'],owned['Ticks'])
        expanded=[str(x).replace('{session}',str(folder)).replace('{repo}',str(ROOT)).replace('{python}',sys.executable) for x in command]
        try:
            run(expanded,timeout=scenario['timeout'],env={'VTMB_GAME_ROOT':str(game),'VTMB_SESSION':str(folder),'VTMB_IDENTITY':str(folder/'identity.json'),'PYTHONPATH':str(ROOT)})
        except __import__('infra.core',fromlist=['Failure']).Failure:
            if name=='console.immediate' and (folder/'collector-result.json').exists():
                receipt=read_json(folder/'collector-result.json')
                if receipt.get('status')=='BLOCKED':raise Blocked(receipt['reason'])
            raise
        require(all(digest(game/n)==h for n,h in artifacts.items()),'Installed resource/binary changed during test')
        if candidate:require(digest(candidate)==native_result['sha256'],'Candidate changed during gameplay')
        result=audit(scenario,read_json(folder/'observations.json'),identity)
        atomic_json(folder/'fresh-result.json',result)
        return result
    finally:
        if transaction.data['owned_process']:
            windows(config,'Stop',folder,folder/'process.json')
        if transaction.data['launch_intent'] and not transaction.data['owned_process']:
            raise Blocked('Interrupted launch before PID record: manual ownership resolution required; journal/backups retained')
        windows(config,'Inspect',folder)
        if read_json(folder/'settings-current.json')['Processes']:
            raise Blocked('Another game is running; no file restoration until it is closed by its owner')
        transaction.restore(process_stopped=True,runtime_safe=bool(transaction.data['owned_process']),finalize=False)
        if (folder/'settings.json').exists():
            windows(config,'RestoreSettings',folder,folder/'settings.json')
            windows(config,'Inspect',folder)
            current=read_json(folder/'settings-current.json')
            original=read_json(folder/'settings.json')
            require(current['Video']==original['Video'] and current['Shortcuts']==original['Shortcuts'] and not current['Processes'],'Real-user settings/process restoration differs')
        atomic_json(folder/'preserved.json',{'Result':'PASS','NoGame':True,'Journal':str(transaction.journal)})
        transaction.finish()
