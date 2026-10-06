"""Fresh scenario contracts and fail-closed external evidence audit.

Collectors run only through an explicitly configured command and transaction.
The historical recipes remain available, but their dated PASS certificates are
never consumed by this fresh-run interface.
"""
import json
import os
import sys
import time
from pathlib import Path
from infra.core import ROOT, Blocked, atomic_json, catalog, digest, need, read_json, require, run
from infra.release import members
from infra.session import Transaction

SCENARIOS = [
    {'id':'console.supported','version':2,'mod':'console','timeout':240,'save':'console','expected':'X/tilde preserve owned ordinary/menu/script pauses; after measured five-second external wait first signed movement/camera succeeds; reload remains usable','checks':['console_x','console_tilde','ordinary_pause','prior_menu','script_pause','first_input','reload']},
    {'id':'console.immediate','mod':'console','timeout':120,'save':'console','expected':'First movement/camera event following native observed close is received without readiness wait; record actual delay and first failure','checks':['close_observed','first_input']},
    {'id':'protean.lifecycle','mod':'protean','timeout':300,'save':'warehouse','expected':'P5 plus native Frenzy owns one Shadow; repeated request has no extra bonus; either state ends first; nominated archival load/map clear stale state','checks':['single_shadow','no_bonus_growth','protean_ends_first','frenzy_ends_first','active_load','active_map','cleanup']},
    {'id':'protean.filter','mod':'protean','timeout':240,'save':'warehouse','expected':'Saved-active P4 filter survives two reloads; off restores mat_fullbright=0; independent RedVision remains intact','checks':['filter_reload_1','filter_reload_2','filter_off','redvision_reload']},
    {'id':'protean.fourhit','mod':'protean','timeout':240,'save':'claws','expected':'Resolve actual weapon/model sequences; four distinct hit windows terminate; interrupt/restart and edition-specific block work','checks':['four_hits','terminates','interrupt_restart','block','resolved_resource']},
    {'id':'frenzy.library','mod':'frenzy','timeout':150,'save':'library','expected':'Exact delivered Library BSP is selected; native frenzyplayer creates owned Shadow in the formerly forbidden area; cleanup follows','checks':['permission','native_frenzy','cleanup','resolved_resource']},
    {'id':'frenzy.griffith','mod':'frenzy','timeout':240,'save':'griffith','expected':'Exact Griffith BSP and native living Werewolf; damaging approach <160 XY, no original-player ground support, ordinary/P5 contexts, end/load/map cleanup','checks':['normal_contact','warform_contact','no_body_support','scope_forwarding','end','load','map','cleanup','resolved_resource']},
    {'id':'subtitle.radio','mod':'subtitle','timeout':720,'save':'radio','expected':'Pause/on/off/repeat/TV transitions/saved-on/load and an unaccelerated real loop preserve correlated PCM/decoder/caption coordinates','checks':['pause','first_on','repeat_on','off_epoch','tv_radio','radio_tv','saved_on','load_return','real_loop','audio_caption_correlation']},
    {'id':'background.cinematics','mod':'background','timeout':240,'save':'radio','expected':'Two actual native cutscenes omit fill/border while text, placement, wrapping and ordinary dialogue remain; save/map retain patch','checks':['scene_a','scene_b','same_text_bounds','ordinary_dialogue','load','map']},
    {'id':'history.transitions','version':2,'mod':'history','timeout':300,'save':None,'expected':'Non-None/None purchases to gender reset removes allocation/bonus; complete fresh pool is spendable, extras rejected; Base/Sheet/Accept retain new purchases','checks':['non_none_gender','none_gender','reverse_gender','fresh_pool','exhausted_reject','base_sheet','accept','repeat_history_once']},
    {'id':'history.bounded_resets','version':3,'mod':'history','timeout':240,'save':None,'expected':'Two forward/reverse resets record entity slots, clear allocation and grant a complete new spendable pool; ten purchases and seven rejected extras, without an XP=9000 or unlimited-endurance expectation','checks':['allocation_reset','pool_reset','entity_budget']},
]


def audit(scenario, evidence, identity):
    """A fresh certificate binds each native before/after record to its inputs."""
    require(evidence.get('session')==identity['session'],'Evidence from another session')
    require(evidence.get('scenario')==scenario['id'] and evidence.get('scenario_version')==scenario.get('version',1),'Wrong scenario/version')
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
        require(isinstance(metrics.get('ground_handle'),int) and metrics.get('ground_handle')!=metrics.get('original_player_handle') and isinstance(metrics.get('original_player_handle'),int),'Ground handle absent or original player used as ground')
        for key,protean in [('normal_contact',False),('warform_contact',True)]:
            state=by[key]['after']
            require(state.get('protean_active') is protean and state.get('native_damage',0)>0 and 0<state.get('closest_active_xy',999)<160,'Both ordinary/P5 damaging contacts required')
        for key in ['end','load','map']:
            before,after=by[key]['before'],by[key]['after']
            require(before.get('frenzy_active') is True and before.get('owned_shadow_count')==1,'Active context missing before '+key)
            require(after.get('frenzy_active') is False and after.get('owned_shadow_count')==0,'Stale Frenzy/Shadow after '+key)
        require(by['scope_forwarding']['after'].get('unrelated_calls_forwarded') is True,'Unrelated scope forwarding unproven')
        require(by['cleanup']['after'].get('owned_shadow_count')==0,'Final Shadow cleanup unproven')
        resource=catalog()['scenario_resources']['frenzy.griffith']
        griffith={resource:identity['resources'][resource]} if resource in identity['resources'] else {}
        require(len(griffith)==1 and by['resolved_resource']['after'].get('resources')==griffith,'Exact selected Griffith BSP unproven')
    if scenario['id']=='frenzy.library':
        require(by['permission']['after'].get('nofrenzyarea')==0,'Library permission not observed')
        native=by['native_frenzy']['after']
        require(native.get('command')=='frenzyplayer' and native.get('owned_shadow_count')==1,'Native Library Frenzy not established')
        require(native.get('shadow_handle') and native.get('player_handle') and native['shadow_handle']!=native['player_handle'],'Independent owned Shadow missing')
        require(by['cleanup']['after'].get('owned_shadow_count')==0,'Library Shadow cleanup incomplete')
        resource=catalog()['scenario_resources']['frenzy.library']
        library={resource:identity['resources'][resource]} if resource in identity['resources'] else {}
        require(len(library)==1 and by['resolved_resource']['after'].get('resources')==library,'Exact selected Library BSP unproven')
    if scenario['id']=='history.bounded_resets':
        slots=metrics.get('entity_slots',[])
        require(metrics.get('declared_resets')==len(slots)==2 and metrics.get('scanned_handle_table_slots')==8192 and all(isinstance(x,int) and 0<=x<8192 for x in slots),'Two-reset observations of the 8192-entry handle table missing; this is not allocator capacity')
        state=by['allocation_reset']['after']
        require(state.get('allocation')==state.get('neutral_allocation') and state.get('allocation'),'Allocation differs from native neutral baseline')
        state=by['pool_reset']['after']
        require(state.get('funding',0)>0 and metrics.get('new_purchases')==[3,6,1] and metrics.get('rejected_exhausted_categories')==7,'Complete new spendable pool or rejection of extras unproven')
        from infra.history_observations import validate_pool,allocation
        proof=validate_pool(state.get('native_pool_proof',{}))
        require(allocation(proof['purchases'][0]['before'])==state['allocation'],'Fresh pool starts from a different reset state')
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
        from infra.history_observations import validate_pool,allocation
        for key in ['non_none_gender','none_gender','reverse_gender']:
            state=by[key]['after'];proof=validate_pool(state.get('native_pool_proof',{}))
            require(allocation(proof['purchases'][0]['before'])==state['allocation'],'Pool belongs to a different reset transition')
    if scenario['id']=='protean.lifecycle':
        require(metrics.get('native_frenzy_command')=='frenzyplayer' and metrics.get('max_owned_shadows')==1,'Wrong native Frenzy route or duplicate Shadow')
        require(metrics.get('feats_before_repeat')==metrics.get('feats_after_repeat') and metrics.get('feats_before_repeat') is not None,'Repeated bonus growth')
        for key in ['protean_ends_first','frenzy_ends_first']:
            after=by[key]['after']
            require(after.get('protean_active')==(key=='frenzy_ends_first') and after.get('frenzy_active')==(key=='protean_ends_first'),'Wrong lifecycle order')
        require(by['cleanup']['after'].get('shadow_count')==0,'Shadow cleanup incomplete')
        for key in ['active_load','active_map']:
            before,after=by[key]['before'],by[key]['after']
            require(before.get('frenzy_active') is True and before.get('owned_shadow_count')==1,'Active native state missing before '+key)
            require(after.get('frenzy_active') is False and after.get('owned_shadow_count')==0,'Stale native state after '+key)
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
    if not command and name=='console.supported':
        command=['{python}','-B','-m','infra.console_supported','{session}']
    if not command and name=='history.bounded_resets':
        command=['{python}','-B','-m','infra.history_bounded','{session}']
    if not command and name=='history.transitions':
        command=['{python}','-B','-m','infra.history_transitions','{session}']
    if not isinstance(command,list) or not command:
        raise Blocked('Configure an inspected native collector command for '+name+' in gameplay_commands. Contract: docs/gameplay.md. Retained recipes are inputs, not automatic PASS adapters.')
    save=Path(config.get('saves',{}).get(scenario['save'],'')) if scenario['save'] else None
    if save is not None and not save.is_file():
        raise Blocked('Nominate archival save for '+str(scenario['save'])+'; original is never substituted')
    from infra.native import exact
    native_result=exact(scenario['mod'],config,candidate)
    collector_env={'VTMB_GAME_ROOT':str(need(config,'game_root')),'PYTHONPATH':os.pathsep.join(filter(None,[str(ROOT),config.get('dependencies','')]))}
    if scenario['mod']=='history':
        try:run([sys.executable,'-B','-c','import unicorn, pefile, capstone, PIL'],env=collector_env)
        except __import__('infra.core',fromlist=['Failure']).Failure as error:raise Blocked('Collector dependencies unavailable before launch: '+str(error))
    game=Path(need(config,'game_root')).resolve()
    if name=='console.supported':
        import re
        cfg=game/'Unofficial_Patch/cfg/config.cfg'
        if cfg.exists() and re.search(r'bind "F11"',cfg.read_text(encoding='cp1252'),re.I):
            raise Blocked('Preparation: Console supported recipe requires an unused F11 binding; preserve personal binding and adapt collector')
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
        if name=='console.supported':
            transaction.write('Unofficial_Patch/cfg/console_task_overlap.cfg',(ROOT/'mods/console/tests/gameplay/console_task_overlap.cfg').read_bytes())
        for directory in ['Bin/loader','Unofficial_Patch/cfg','Vampire/cfg','Unofficial_Patch/save','Vampire/save','Unofficial_Patch/python','Vampire/python','Unofficial_Patch/resource']:
            for file in (game/directory).rglob('*'):
                if file.is_file():transaction.preserve(file.relative_to(game).as_posix())
        for relative in catalog()['native_modules']:transaction.preserve(relative)
        for directory in ['', 'Unofficial_Patch','Vampire']:
            for file in (game/directory).glob('*'):
                if file.is_file() and file.suffix.lower() in ['.cfg','.log','.txt','.exe','.inf']:
                    transaction.preserve(file.relative_to(game).as_posix())
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
        # Python 2 creates these standard caches itself during engine startup.
        # Derive and journal each possible destination from a preserved input.
        for directory in ['Unofficial_Patch/python','Vampire/python']:
            for source in (game/directory).rglob('*.py'):
                for extension in ['.pyc','.pyo']:
                    transaction.allow_runtime(source.with_suffix(extension).relative_to(game).as_posix())
        for file in (game/'Unofficial_Patch/cfg').glob('*.cfg'):transaction.allow_runtime(file.relative_to(game).as_posix())
        stem='rc_'+transaction.data['id'][:12]
        args=['-game','Unofficial_Patch','-dev','-novid','-console']
        if save:
            relative='Unofficial_Patch/save/'+stem+'.sav'
            transaction.write(relative,save.read_bytes());args+=['+load',stem]
        background={p.relative_to(game).as_posix():digest(p) for p in (game/'Bin/loader').glob('*.vtm') if p.relative_to(game).as_posix() not in artifacts}
        identity={'session':run_id+'_'+name,'scenario_version':scenario.get('version',1),'scenario':name,'artifacts':artifacts,'resources':resources,'modules':{n:digest(game/n) for n in catalog()['native_modules']},'background_mods':background,'save_sha256':digest(save) if save else None}
        atomic_json(folder/'identity.json',identity)
        atomic_json(folder/'launch.json',{'GameRoot':str(game),'Arguments':args,'Candidates':[{'Path':str(game/n),'Hash':h} for n,h in artifacts.items()],'Save':stem,'SaveHash':identity['save_sha256'],'PluginHash':native_result['sha256']})
        transaction.launch_intent(game/'Vampire.exe',args)
        windows(config,'Launch',folder,folder/'launch.json')
        owned=read_json(folder/'process.json');transaction.owned_process(owned['Id'],owned['Ticks'])
        expanded=[str(x).replace('{session}',str(folder)).replace('{repo}',str(ROOT)).replace('{python}',sys.executable) for x in command]
        try:
            run(expanded,timeout=scenario['timeout'],env={**collector_env,'VTMB_SESSION':str(folder),'VTMB_IDENTITY':str(folder/'identity.json')},process_tree=True)
        except __import__('infra.core',fromlist=['Failure']).Failure:
            if (folder/'collector-result.json').exists():
                receipt=read_json(folder/'collector-result.json')
                if receipt.get('status')=='BLOCKED':raise Blocked(receipt['reason'])
            raise
        require(all(digest(game/n)==h for n,h in artifacts.items()),'Installed resource/binary changed during test')
        require(all(digest(game/n)==h for n,h in identity['modules'].items()),'Native module changed during test')
        require(all(digest(game/n)==h for n,h in background.items()),'Background mod changed during test')
        if candidate:require(digest(candidate)==native_result['sha256'],'Candidate changed during gameplay')
        result=audit(scenario,read_json(folder/'observations.json'),identity)
        atomic_json(folder/'fresh-result.json',result)
        atomic_json(folder/'scenario-result.json',{'status':'PASS','observed':result})
        return result
    except Exception as error:
        primary={'status':'BLOCKED' if isinstance(error,Blocked) else 'FAIL','reason':type(error).__name__+': '+str(error)}
        atomic_json(folder/'scenario-result.json',primary)
        error.scenario_result=primary
        raise
    finally:
        primary_error=sys.exc_info()[1]
        try:
            preserve_session(transaction,config,folder)
            preservation={'status':'PASS','journal':str(transaction.journal)}
        except Exception as error:
            preservation={'status':'BLOCKED' if isinstance(error,Blocked) else 'FAIL','reason':type(error).__name__+': '+str(error),'journal':str(transaction.journal)}
            atomic_json(folder/'preservation-result.json',preservation)
            if primary_error is not None:
                primary_error.preservation_result=preservation
            else:
                error.scenario_result=read_json(folder/'scenario-result.json')
                error.preservation_result=preservation
                raise
        else:
            atomic_json(folder/'preservation-result.json',preservation)
            if primary_error is not None:primary_error.preservation_result=preservation
            elif 'result' in locals():result['preservation_result']=preservation


def preserve_session(transaction,config,folder):
    if transaction.data['owned_process']:
        verify_process_record(transaction,folder)
        windows(config,'Stop',folder,folder/'process.json')
    if transaction.data['launch_intent'] and not transaction.data['owned_process']:
        raise Blocked('Interrupted launch before PID record: manual ownership resolution required; journal/backups retained')
    windows(config,'Inspect',folder)
    if read_json(folder/'settings-current.json')['Processes']:
        raise Blocked('Another game is running; no file restoration until it is closed by its owner')
    # Only this live controller can attribute the just-stopped runtime output.
    # A later recover command uses these recorded hashes instead of a stale PID.
    transaction.seal_runtime()
    atomic_json(folder/'settings-after-stop.json',read_json(folder/'settings-current.json'))
    transaction.restore(process_stopped=True,finalize=False)
    if (folder/'settings.json').exists():
        import shutil
        archive=folder/'after-tests/settings-before-restoration.json';archive.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(folder/'settings-current.json',archive)
        windows(config,'RestoreSettings',folder,folder/'settings.json')
        windows(config,'Inspect',folder)
        current=read_json(folder/'settings-current.json')
        original=read_json(folder/'settings.json')
        require(current['Video']==original['Video'] and current['Shortcuts']==original['Shortcuts'] and not current['Processes'],'Real-user settings/process restoration differs')
    atomic_json(folder/'preserved.json',{'Result':'PASS','NoGame':True,'Journal':str(transaction.journal)})
    transaction.finish()


def verify_process_record(transaction,folder):
    owned=transaction.data['owned_process']
    process=read_json(folder/'process.json')
    require(process==owned,'Process record changed; refuse process control until ownership is reconciled')
    require(Path(transaction.data['launch_intent']['executable']).resolve()==transaction.game/'Vampire.exe','Owned launch belongs to another executable')


def loaded_inputs(process,identity):
    """Resolve actually loaded modules from the owned PID, not planned copies."""
    observed={}
    for relative,expected in {**identity['modules'],**identity['artifacts']}.items():
        if not relative.endswith(('.dll','.vtm')):continue
        basename=Path(relative).name.lower()
        actual=process.module_paths.get(basename)
        require(actual is not None and digest(actual)==expected,'Loaded native input differs or absent: '+basename)
        observed[relative]={'path':actual,'sha256':digest(actual),'base':process.modules[basename]}
    return observed
