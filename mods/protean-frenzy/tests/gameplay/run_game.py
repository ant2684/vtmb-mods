"""Owned-process direct-engine scenario with verified full file restoration.

No OS input injection; the engine executes a cfg and Python task timeline.
"""
import sys,time,subprocess,datetime,json,struct,hashlib,shutil,traceback,re,ctypes as C
from pathlib import Path
HERE=Path(__file__).resolve().parent
from local_runtime import path,CONFIG,COMMON
GAME=path('game')
import transaction as gr
sys.path.insert(0,str(COMMON))
from process_reader import Process,k
from sequence_observer import native_sequence
from native_health_observer import native_health
from effect_observer import actor_effects

def live_player(actors,pointer):
    """Only publish the player that survived full-handle revalidation."""
    return next((a for a in actors if a['cls']=='player' and a['ptr']==pointer),None)

def dump(p,x):p.write_text(json.dumps(x,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Transaction(gr.Transaction):
    def begin(self):
        self.created_log_roots=[rel for rel in ['logs','Vampire/logs','Unofficial_Patch/logs'] if not (GAME/rel).exists()]
        super().begin()
        # UP's stock new-game Vampire/Hunter switch copies files outside cfg,
        # python and items; haven initialization also rewrites its username.
        text=(GAME/'Unofficial_Patch/python/vamputil.py').read_text()
        destinations=re.findall(r'dst = .*?fileutil\.moddir \+ "([^"]+)"',text)
        extra={'Unofficial_Patch/vdata/hackterminals/haven_pc.txt'}
        extra.update('Unofficial_Patch/'+p.replace('\\\\','/').lstrip('/') for p in destinations)
        for rel in sorted(extra):
            p=self.inside_game(GAME/rel);self.single.append(rel)
            if p.exists() and rel not in self.records:
                dst=self.session/'backup'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
                self.records[rel]=dict(sha256=sha(p),mtime_ns=p.stat().st_mtime_ns)
        for tree in ['Bin/loader','Unofficial_Patch/vdata/items','Unofficial_Patch/particles','Unofficial_Patch/screenshots','Vampire/screenshots','screenshots','logs','Vampire/logs','Unofficial_Patch/logs']:
            self.trees.append(tree)
            self.directories[tree]=[str(p.relative_to(GAME)) for p in (GAME/tree).rglob('*') if p.is_dir()]
            for p in (GAME/tree).rglob('*'):
                if not p.is_file():continue
                rel=str(p.relative_to(GAME));dst=self.session/'backup'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
                self.records[rel]=dict(sha256=sha(p),mtime_ns=p.stat().st_mtime_ns)
        rel='p5_owned_python_errors.txt';p=GAME/rel;self.single.append(rel)
        if p.exists():
            dst=self.session/'backup'/rel;shutil.copy2(p,dst);self.records[rel]=dict(sha256=sha(p),mtime_ns=p.stat().st_mtime_ns)
        for sex in ['male','female']:
            rel='Unofficial_Patch/models/character/shared/'+sex+'/claws.mdl';p=GAME/rel;self.single.append(rel);dst=self.session/'backup'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
            self.records[rel]=dict(sha256=sha(p),mtime_ns=p.stat().st_mtime_ns)
        for name in ['la_library_1.bsp','sp_observatory_2.bsp']:
            rel='Unofficial_Patch/maps/'+name;p=GAME/rel;self.single.append(rel)
            if p.exists():
                dst=self.session/'backup'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
                self.records[rel]=dict(sha256=sha(p),mtime_ns=p.stat().st_mtime_ns)
        for root in ['Unofficial_Patch/screenshots','Vampire/screenshots','screenshots']:
            for j in range(4):
                rel=root+'/protean_lifecycle_owned_'+str(j)+'.jpg';p=GAME/rel;self.single.append(rel)
                if p.exists():
                    dst=self.session/'backup'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
                    self.records[rel]=dict(sha256=sha(p),mtime_ns=p.stat().st_mtime_ns)
        dump(self.session/'transaction.json',dict(game=str(GAME),trees=self.trees,single=self.single,files=self.records,directories=self.directories,created_log_roots=self.created_log_roots))
    def restore(self):
        super().restore()
        manifest=json.loads((self.session/'transaction.json').read_text())
        for rel in manifest.get('created_log_roots',[]):
            p=self.inside_game(GAME/rel)
            if p.exists() and not any(p.iterdir()):p.rmdir()

def run():
    mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
    required_space=(2 if mode=='morph-visual' else .5)*1024**3
    assert shutil.disk_usage(HERE).free>required_space,'Insufficient workspace space; no game launched'
    root=HERE/'sessions';root.mkdir(exist_ok=True)
    session=root/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+mode);session.mkdir()
    assert not gr.running_games(),'Existing user game; cannot launch or attach'
    lock=GAME/'.vtmb-regression.lock';assert not lock.exists(),'Existing test lock'
    dump(lock,dict(task='protean-lifecycle',session=str(session)))
    gr.PINS={};tx=Transaction(GAME,session);proc=None;reader=None;rows=[];result=dict(mode=mode,passed=False,session=str(session))
    try:
        (HERE/'native-events.log').write_text('',encoding='ascii')
        tx.begin()
        stock=path('original_resource_root')/'Unofficial_Patch/python/vamputil.py'
        assert sha(stock)=='6a98c7da7b2e3aba816091f363763109fb6420ae9d2ef3fd82767162439dbd3a'
        shutil.copy2(stock,GAME/'Unofficial_Patch/python/vamputil.py')
        result['stock_python_sha256']=sha(stock)
        if mode in ('save-active','save-original-baseline'):
            for rel in tx.created_log_roots:tx.inside_game(GAME/rel).mkdir(parents=True,exist_ok=True)
        if mode in ('morph-original-baseline','morph-original-crouch-baseline','morph-original-female-baseline','save-original-baseline'):
            # Reconstruct the preceding setup inside the full owned transaction.
            (GAME/'Bin/loader/protean-lifecycle.vtm').unlink()
            original=path('original_resource_root')
            originals={'Unofficial_Patch/python/vamputil.py':'6a98c7da7b2e3aba816091f363763109fb6420ae9d2ef3fd82767162439dbd3a',
                       'Unofficial_Patch/vdata/items/item_w_claws.txt':'d0e322de5b9c70a6cadcc68def0bda31d600cbb8aa74cd575e40e9b28303a58d'}
            for relative,digest in originals.items():
                assert sha(original/relative)==digest
                shutil.copy2(original/relative,GAME/relative)
            result['original_inputs']=originals
        if mode!='baseline' and not mode.endswith('-baseline'):
            for previous in ['protean-improved.vtm','protean-lifecycle.vtm','claws-flow.vtm','claws-stealth-position.vtm','frenzy-melee-katana-test.vtm','griffith-frenzy-werewolf-fix.vtm']:
                old=GAME/'Bin/loader'/previous
                if old.exists():old.unlink()
            payload=HERE/'candidate/Payload'
            result['payload_sha256']={}
            for source in payload.rglob('*'):
                if source.is_file() and source.name!='README.txt':
                    assert source.suffix.lower() not in ['.lib','.pdb','.exe'], 'Build debris in payload'
                    target=GAME/source.relative_to(payload);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
                    result['payload_sha256'][source.relative_to(payload).as_posix()]=sha(target)
        seed_key='feeding_seed' if mode.startswith(('feeding','stealth','frenzy','transitions')) else 'claws_seed'
        seed=path(seed_key);assert sha(seed)==CONFIG[seed_key+'_sha256']
        if mode.startswith('native-hunger'):
            seed=path('native_frenzy_seed');assert sha(seed)==CONFIG['native_frenzy_seed_sha256']
        elif mode in ('latest-interface','latest-midload'):
            seed=path('interface_seed');assert sha(seed)==CONFIG['interface_seed_sha256']
        elif mode.startswith('latest'):
            seed=path('latest_seed');assert sha(seed)==CONFIG['latest_seed_sha256']
        elif mode.startswith('frenzy') or mode in ('save-active','save-original-baseline'):
            seed=path('frenzy_seed');assert sha(seed)==CONFIG['frenzy_seed_sha256'] and b'sm_warehouse_1' in seed.read_bytes()
        elif mode in ('restore-active','restore-legacy'):
            key='legacy_active_seed' if mode=='restore-legacy' else 'active_seed'
            seed=path(key);assert sha(seed)==CONFIG[key+'_sha256']
        elif mode=='filter-restore':
            key='filter_seed'
            seed=path(key);assert sha(seed)==CONFIG[key+'_sha256']
        else:assert b'ClawsTest' in seed.read_bytes()
        if mode=='latest-midload':
            alternate=path('alternate_seed');assert sha(alternate)==CONFIG['alternate_seed_sha256']
            alt=GAME/'Unofficial_Patch/save/ProteanLifecycleOtherOwned.sav';assert not alt.exists();shutil.copy2(alternate,alt)
        save=GAME/'Unofficial_Patch/save/ProteanLifecycleOwned.sav';assert not save.exists();shutil.copy2(seed,save)
        helper=(HERE/'game_probe.py').read_text().replace('__LOG__',str(session/'probe.log').replace('\\','/')).replace('__MODE__',mode).replace('__ACTIVE_SAVE__',str(GAME/'Unofficial_Patch/save/ProteanLifecycleActiveOwned.sav').replace('\\','/'))
        if mode.startswith('claws-actions'):
            from mdl import seqs,i,f,cs
            model=(HERE/'candidate/Payload/Unofficial_Patch/models/character/shared/male/claws.mdl').read_bytes();ss=seqs(model);routes={}
            for name,q in ss.items():
                if not name.startswith('pfi_frenzy_') and i(model,q+4) and cs(model,q+i(model,q+4))=='ACT_MELEE_ATTACK_CLAWS' and i(model,q+16)>0:
                    chain=[];cur=name
                    while cur:
                        z=ss[cur];chain.append((cur,f(model,z+752)));cur=cs(model,z+i(model,z+744)) if i(model,z+744)>0 else None
                    routes[i(model,q+724)]=chain
            assert len(routes)==7;helper=helper.replace('__CLAW_ROUTES__',repr(routes))
        else:helper=helper.replace('__CLAW_ROUTES__','{}')
        (GAME/'Unofficial_Patch/python/p5_probe.py').write_text(helper,encoding='ascii')
        shutil.copy2(HERE/('interface-bootstrap.vtm' if mode=='latest-interface' else 'midload-bootstrap.vtm' if mode=='latest-midload' else 'transition-bootstrap.vtm' if mode.startswith('transitions') or mode=='frenzy-melee' else 'probe-bootstrap.vtm'),GAME/'Bin/loader/zz-protean-owned-bootstrap.vtm')
        if mode in ('frenzy-maps-library','frenzy-maps-griffith'):
            shutil.copy2(HERE/(mode+'-bootstrap.vtm'),GAME/'Bin/loader/zz-protean-owned-bootstrap.vtm')
        if mode=='latest-interface':assert sha(GAME/'Vampire/cl_dlls/client.dll')=='e88beae0dd03af06493c71c5e8d87a6993b54e590cb6ad37cd3513c588582870'
        commands=['alias p5_coexist_reload "load ProteanLifecycleOwned"','sv_cheats 1','developer 0','alias p5_frenzy "frenzyplayer"','alias p5_end "vdiscipline_endall"','alias p5_buy "vstats get protean 1"','alias p5_sell "vstats sell protean"','alias p5_cast "vdiscipline_int protean"','alias p5_feed_brawl "vstats get brawl 5"','alias p5_feed_strength "vstats get strength 5"','alias p5_male "vgender_int Male"','alias p5_female "vgender_int Female"','alias p5_sword "use item_w_katana"','alias p5_unuse "-use"','alias p5_unduck "-duck"','alias p5_camera "thirdperson; r_drawparticles 1; cam_idealdist 160; cam_targetangle -10; cam_yaw 270"']
        if mode=='latest-midload':commands.extend(['alias p5_otherload "load ProteanLifecycleOtherOwned"','alias p5_firstload "load ProteanLifecycleOwned"'])
        if mode=='stealth-tiger':commands.extend(['alias p5_tiger "use item_w_chang_claw"','alias p5_melee "vstats get melee 5"'])
        if mode.startswith('claws-actions'):commands.extend(['alias p5_attack2 "+wpn_secondaryatk"','alias p5_stopattack2 "-wpn_secondaryatk"'])
        if mode=='filter-save':
            assert not (GAME/'Unofficial_Patch/save/ProteanFilterOwned.sav').exists()
            commands.append('alias p5_filter_save "save ProteanFilterOwned"')
        commands.extend(['alias p5_unarmed "use item_w_fists"','alias p5_claws "use item_w_claws"','alias p5_tiger "use item_w_chang_claw"'])
        for verb in ['forward','back','moveleft','moveright','attack','jump','duck','use','feed']:
            commands.extend(['alias p5_'+verb+' "+'+verb+'"','alias p5_stop'+verb+' "-'+verb+'"'])
        if mode.startswith('transitions') or mode in ('save-active','save-original-baseline'):
            commands.extend(['alias p5_save_active "save ProteanLifecycleActiveOwned"','alias p5_load_active "load ProteanLifecycleActiveOwned"','alias p5_reload "load ProteanLifecycleOwned"','alias p5_map "changelevel sm_hub_1"'])
            assert not (GAME/'Unofficial_Patch/save/ProteanLifecycleActiveOwned.sav').exists()
            for name,call in [('p5_callback.cfg','cfg_callback()'),('p5_loaded.cfg','loaded_callback()'),('p5_mapped.cfg','mapped_callback()')]:
                (GAME/'Unofficial_Patch/cfg'/name).write_text("__import__('p5_probe')."+call+'\n',encoding='ascii')
        cfg='\n'.join(commands+['hideconsole',''])
        (GAME/'Unofficial_Patch/cfg/p5_owned.cfg').write_text(cfg,encoding='ascii')
        cmd=[str(GAME/'Vampire.exe'),'-game','Unofficial_Patch','-dev','-novid','+load','ProteanLifecycleOwned','+exec','p5_owned.cfg']
        if mode in ('frenzy-maps-library','frenzy-maps-griffith'):
            cmd[5:7]=['+map','la_library_1' if mode.endswith('library') else 'sp_observatory_2']

        dump(session/'launch.json',dict(command=cmd,game=str(GAME)));proc=subprocess.Popen(cmd,cwd=GAME)
        dump(session/'owned.json',dict(pid=proc.pid));print('OWNED',proc.pid,session,flush=True)
        launch_started=time.monotonic()
        deadline=time.monotonic()+(150 if mode.startswith('frenzy-maps') else 170 if mode.startswith('claws-actions') or mode in ('feeding-expiry','latest-midload') or mode.startswith('frenzy') or mode.startswith('transitions') else 90 if mode.startswith('stealth') or mode in ('actions','morph-visual') or mode.startswith('feeding') else 45);bound=None;done=None;seq_names={};class_cache={}
        checked_compat=False
        while time.monotonic()<deadline:
            try:snapshot_request=(session/'snapshot-request.txt').read_text()
            except FileNotFoundError:snapshot_request=''
            if proc.poll() is not None:raise RuntimeError('Game exited: '+str(proc.returncode))
            if reader is None:
                try:
                    reader=Process(proc.pid)
                    if 'vampire.dll' not in reader.modules or (mode in ('filter-save','filter-restore') and 'client.dll' not in reader.modules):k.CloseHandle(reader.h);reader=None
                except (OSError,RuntimeError):reader=None
            if reader:
                try:
                    base=reader.modules['vampire.dll'];table=reader.u(base+0x566458)
                    if table:
                        entries=reader.read(table,8192*12);actors=[];bound=None
                        for j in range(8192):
                            ent=struct.unpack_from('<I',entries,j*12+4)[0]
                            if not ent:continue
                            try:
                                handle=j|(struct.unpack_from('<I',entries,j*12+8)[0]<<13);key=(ent,handle)
                                name=class_cache.get(key)
                                if name is None:
                                    name=reader.read(reader.u(ent+0x11c),64).split(b'\0')[0].decode('ascii',errors='replace');class_cache[key]=name
                                target_name=''
                                if (mode.startswith('frenzy') or mode.startswith('native-hunger')) and name=='npc_VHumanCombatant':
                                    np=reader.u(ent+0x26c);target_name=reader.read(np,64).split(b'\0')[0].decode('ascii',errors='replace') if np else ''
                                if name not in ['player','npc_VWolfMorph','npc_VFrenzyShadow','npc_VWerewolf','events_player'] and not name.startswith('item_w_') and not target_name.startswith('fk_target_'):continue
                                actors.append(dict(ptr=ent,handle=j|(struct.unpack_from('<I',entries,j*12+8)[0]<<13),cls=name,vt=hex(reader.u(ent)-base),p98=hex(reader.u(ent+0x98)),p9c=hex(reader.u(ent+0x9c)),seq=reader.u(ent+0x6f0) if name in ['player','npc_VWolfMorph'] else None,cycle=struct.unpack('<f',reader.read(ent+0x6f8,4))[0] if name in ['player','npc_VWolfMorph'] else None))
                                if target_name.startswith('fk_target_'):
                                    actors[-1].update(name=target_name,targetable=reader.read(ent+0x1480,1)[0],alive=reader.read(ent+0x1481,1)[0],life=reader.read(ent+0x200,1)[0],health=reader.u(ent+0x210),solid=reader.u(ent+0x2b0),effects=reader.u(ent+0x19c),spawn_flags=reader.u(ent+0x434),think_disabled=reader.read(ent+0x6080,1)[0],enemy=hex(reader.u(ent+0x5ce0)))
                                if name=='events_player':
                                    np=reader.u(ent+0x26c);actors[-1].update(event_name=reader.read(np,80).split(b'\0')[0].decode(errors='replace') if np else '',outputs_enabled=reader.read(ent+0x450,1)[0])
                                if name=='npc_VWolfMorph':
                                    actors[-1].update(state=reader.u(ent+0x168),link=hex(reader.u(ent+0x155c)),effects=hex(reader.u(ent+0x19c)),sequence_name='unresolved')
                                    try:actors[-1]['sequence_name']=native_sequence(reader.read,base,ent,reader.u(ent+0x6f0))
                                    except Exception:pass
                                if name in ('npc_VWolfMorph','npc_VFrenzyShadow','npc_VWerewolf'):
                                    actors[-1].update(origin=struct.unpack('<3f',reader.read(ent+0x404,12)))
                                if name=='npc_VWerewolf':actors[-1].update(ground=hex(reader.u(ent+0x384)),life=reader.read(ent+0x200,1)[0],health=reader.u(ent+0x210))
                                if name=='npc_VFrenzyShadow':
                                    actors[-1].update(native_effects=actor_effects(reader.read,base,ent),native_traits=dict(corpus=reader.u(ent+0x1364),strength=reader.u(ent+0x1180),stamina=reader.u(ent+0x1188),wits=reader.u(ent+0x11a0)),sequence_name='unresolved',activity=reader.u(ent+0xfec),weapon=reader.u(ent+0x19a4),enemy=reader.u(ent+0x5ce0),inventory=list(struct.unpack('<224I',reader.read(ent+0x1624,224*4))))
                                    try:actors[-1]['sequence_name']=native_sequence(reader.read,base,ent,reader.u(ent+0x6f0))
                                    except Exception:actors[-1]['sequence_observer_error']='incomplete lifetime sample'
                                if target_name.startswith('fk_target_'):
                                    try:actors[-1]['native_health']=native_health(reader.read,base,ent)
                                    except Exception:actors[-1]['health_observer_error']='incomplete lifetime sample'
                                if name=='player':bound=ent
                                if name.startswith('item_w_'):actors[-1].update(slot=reader.u(ent+0x73c),owner=reader.u(ent+0x88c))
                            except (OSError,RuntimeError):continue
                        if bound and reader.u(bound+0x11c) and reader.read(reader.u(bound+0x11c),7)==b'player\0':
                            if not checked_compat:
                                from native_inspect import pe,mem
                                dep={}
                                dump(session/'loaded_modules.json',{k:hex(v) for k,v in reader.modules.items()})
                                for addr in [0x334e70,0x335780,0x33589d,0x33dde0,0x21fe50,0x161a70,0x952d0,0x8fe80,0xe057,0x227a30,0x50d90,0x24f7b0,0x125c1,0x430e,0x2c2ec0,0x2c31f7,0x31c1d3,0x1f9a80,0xb7fe0,0xa0420,0x1f9af0,0x1644f0,0x19ce00,0x19d210,0xf5fc0,0x69e80,0x1618e0,0xd8830,0x336920,0x2008e0,0x196ec3,0xcee53]:
                                    expected=bytearray(mem[addr:addr+64])
                                    for block in getattr(pe,'DIRECTORY_ENTRY_BASERELOC',[]):
                                        for rr in block.entries:
                                            if rr.type==3 and addr<=rr.rva<addr+61:
                                                off=rr.rva-addr;struct.pack_into('<I',expected,off,(struct.unpack_from('<I',expected,off)[0]+base-pe.OPTIONAL_HEADER.ImageBase)&0xffffffff)
                                    actual=reader.read(base+addr,64)
                                    dep[hex(addr)]=dict(match=actual==expected,expected=expected.hex(),actual=actual.hex())
                                dump(session/'native_compat.json',dep);checked_compat=True
                                if mode.startswith('native-hunger'):
                                    required_hooks=[0x3daf] if CONFIG.get('legacy_counterexample') else [0x3daf,0x227a30,0x2c2ec0]
                                    for address in required_hooks:
                                        assert reader.read(base+address,1)==b'\xe9',('Missing native inventory/Corpus hook',hex(address))
                            if mode=='frenzy-melee':
                                for address in [0x161fc0,0x162038,0x375c80,0x8dc40,0x12503,0x376f20,0xf03d,0xc036,0x8dd30,0x32b0,0xd4e0,0x2725d0,0xd0b2,0x3e9e00,0x343020,0x33f6d0,0x329a70,0x94b70,0x12512,0xb230,0x6fbe,0x3daf,0x1f88eb,0x3485fd]:
                                    assert reader.read(base+address,1)==b'\xe9',('Missing component hook',hex(address))
                                assert reader.read(base+0x1618e0,1)==b'\x53'
                            r=reader.read(bound,0x2400)
                            ui=lambda o:struct.unpack_from('<I',r,o)[0]
                            row=dict(t=time.monotonic(),actors=actors,pc=bound,state=ui(0x168),substate=ui(0x16c),controller=hex(ui(0x1db0)),wolf=r[0x1edc],model_index=ui(0x2e0),effects=hex(ui(0x19c)),partner=hex(ui(0x1538)),role=ui(0x153c),grapple_type=ui(0x1540),seq=ui(0x6f0),cycle=struct.unpack_from('<f',r,0x6f8)[0],buttons=ui(0x2088),origin=struct.unpack_from('<3f',r,0x404),inventory=list(struct.unpack_from('<224I',r,0x1624)),weapon=ui(0x19a4),protean=ui(0x1380),frenzy=ui(0x146c),game_time=struct.unpack('<f',reader.read(reader.u(base+0x70b228)+12,4))[0])
                            try:row['sequence_name']=native_sequence(reader.read,base,bound,row['seq'])
                            except Exception:row['sequence_name']='unresolved'
                            row['saved_human']=reader.read(bound+0x23d4,260).split(b'\0')[0].decode('ascii',errors='replace');row['animation_layers']=[list(struct.unpack_from('<12I',r,0x734+48*j)) for j in range(4)]
                            row['blood_target']=hex(ui(0x149c));row['blood_next']=struct.unpack_from('<f',r,0x1490)[0];row['blocked_events']=r[0x19f6]
                            row['discipline_durations']=list(struct.unpack_from('<17f',r,0x1adc));row['discipline_begin']=list(struct.unpack_from('<17f',r,0x1b20));row['player_flags']=ui(0x434)
                            row['sounds']=[]
                            engine=reader.modules.get('engine.dll')
                            if engine:
                                row['save_status']={'reason':reader.u(engine+0xd5d48c),'server':reader.u(engine+0x348960),'client':reader.u(engine+0x1dbe50),'max_clients':reader.u(engine+0x12af1c8)}
                                for ci in range(min(reader.u(engine+0x13107d4),128)):
                                    ca=engine+0x1310b08+ci*0xa0;sfx=reader.u(ca)
                                    if not sfx:continue
                                    try:
                                        sound=reader.read(sfx,256).split(b'\0')[0].decode('ascii',errors='replace')
                                        if 'stealth' in sound.lower():
                                            mixer=reader.u(ca+4);rawpos=reader.read(mixer+8,8) if mixer else bytes(8)
                                            row['sounds'].append(dict(name=sound,channel=ci,position=struct.unpack('<d',rawpos)[0]))
                                    except (OSError,RuntimeError):pass
                            # Actor enumeration precedes the player sample. A scene may end
                            # between them, so validate full handles again before publishing.
                            # Do not report an already destroyed actor as a live orphan.
                            live=[]
                            for actor in actors:
                                check_entry=reader.read(table+(actor['handle']&8191)*12+4,8)
                                check_ptr,check_serial=struct.unpack('<2I',check_entry)
                                if check_ptr==actor['ptr'] and check_serial==actor['handle']>>13:live.append(actor)
                            actors=live;row['actors']=actors
                            current_player=live_player(actors,bound)
                            if current_player is None:
                                time.sleep(.035)
                                continue
                            def inventory_graph(handles):
                                graph={}
                                for handle in handles:
                                    if handle==0xffffffff:continue
                                    try:
                                        pointer,serial=struct.unpack('<II',reader.read(table+(handle&8191)*12+4,8))
                                        if not pointer or serial!=handle>>13:continue
                                        cls=reader.read(reader.u(pointer+0x11c),80).split(b'\0')[0].decode('ascii',errors='replace')
                                        if cls.startswith('item_w_'):graph[handle]=dict(cls=cls,slot=reader.u(pointer+0x73c),owner=reader.u(pointer+0x88c))
                                    except (OSError,RuntimeError):pass
                                return graph
                            row['inventory_items']=inventory_graph(row['inventory'])
                            if mode=='native-dependencies-off':
                                from native_inspect import mem
                                for addr,size in [(0x3daf,5),(0x33dde0,5),(0x351090,5),(0x3485fd,6),(0x161fc0,5),(0x227a30,6),(0x2c2ec0,6),(0x196ec3,5),(0xcee53,8)]:
                                    assert reader.read(base+addr,size)==mem[addr:addr+size],('Disabled feature installed a hook',hex(addr))
                            if mode.startswith('frenzy-maps'):
                                # The pinned SetNoFrenzyArea wrapper uses getter
                                # 23BD00: mov eax,[server+7532E8]; ret.
                                assert reader.read(base+0x23bd00,6)==b'\xa1'+struct.pack('<I',base+0x7532e8)+b'\xc3'
                                world=reader.u(base+0x7532e8)
                                row['world_nofrenzy']=reader.read(world+0x4a9,1)[0] if world else -1
                                row['werewolves']=[a for a in actors if a['cls']=='npc_VWerewolf']
                            for actor in row['actors']:
                                if actor['cls']=='npc_VFrenzyShadow':actor['inventory_items']=inventory_graph(actor['inventory'])
                            (session/'gate.txt').write_text(row['sequence_name']+'|'+row['partner'],encoding='ascii')
                            detail={key:row[key] for key in ['sequence_name','cycle','origin','wolf','state','controller','buttons','weapon','inventory','effects','protean','partner','role']}
                            detail['view_angles']=list(struct.unpack_from('<3f',r,0x206c))
                            detail['snapshot_request']=snapshot_request
                            detail['discipline_durations']=row['discipline_durations'];detail['discipline_begin']=row['discipline_begin'];detail['game_time']=row['game_time'];detail['observer_time']=row['t'];detail['player_flags']=hex(row['player_flags'])
                            detail['save_status']=row.get('save_status',{});detail['saved_human']=row['saved_human'];detail['animation_layers']=[[hex(v) for v in layer] for layer in row['animation_layers']];detail['morphs']=sum(e['cls']=='npc_VWolfMorph' for e in actors);detail['frenzy']=ui(0x146c)
                            detail['inventory']=[hex(h) for h in detail['inventory']];detail['weapon']=hex(detail['weapon']);detail['role']=hex(detail['role'])
                            if mode.startswith('frenzy') or mode.startswith('native-hunger'):
                                detail['targets']=[{k:a[k] for k in ['name','targetable','alive','life','health','solid','effects','spawn_flags','think_disabled','enemy']} for a in actors if a.get('name','').startswith('fk_target_')]
                                detail['player_handle']=hex(current_player['handle'])
                                detail['ai_flags']=reader.u(base+0x92053c)
                            if mode.startswith('native-hunger'):detail['player_effects']=actor_effects(reader.read,base,bound)
                            detail['events_outputs']={a['event_name']:a['outputs_enabled'] for a in actors if a['cls']=='events_player'}
                            if True:detail['morph_actors']=[dict(a,ptr=hex(a['ptr']),handle=hex(a['handle'])) for a in actors if a['cls']=='npc_VWolfMorph']
                            detail['shadow_actors']=[dict(cls=a['cls'],ptr=hex(a['ptr']),handle=hex(a['handle']),native_traits=a['native_traits'],native_effects=a['native_effects'],weapon_class=a['inventory_items'].get(a['weapon'],{}).get('cls',''),sequence_name=a['sequence_name'],activity=a['activity'],origin=a['origin'],inventory=[hex(h) for h in a['inventory']],weapon=hex(a['weapon']),enemy=hex(a['enemy'])) for a in actors if a['cls']=='npc_VFrenzyShadow']
                            detail['item_classes']={hex(h):item['cls'] for h,item in row['inventory_items'].items()}
                            if mode in ('filter-save','filter-restore'):
                                client=reader.modules['client.dll'];entry=reader.u(client+0x619928);filter_ptr=reader.u(entry+4) if entry else 0
                                detail['mat_fullbright_native']=reader.u(filter_ptr+0x2c) if filter_ptr else -1
                            if mode.startswith('frenzy-maps'):
                                detail['world_nofrenzy']=row['world_nofrenzy'];detail['werewolves']=row['werewolves']
                            for name in ['native-state-fallback','native-state']:
                                tmp=session/(name+'.tmp');tmp.write_text(repr(detail),encoding='ascii')
                                try:tmp.replace(session/(name+'.txt'))
                                except PermissionError:pass
                            rows.append(row)
                except (OSError,RuntimeError):pass
            log=session/'probe.log'
            if time.monotonic()-launch_started>30 and not log.exists():raise RuntimeError('No Python startup within 30 seconds; test helper did not start')
            errors=session/'python-errors.log'
            bootstrap_errors=GAME/'p5_owned_python_errors.txt'
            if bootstrap_errors.exists() and bootstrap_errors.stat().st_size:raise RuntimeError(bootstrap_errors.read_text())
            if errors.exists() and errors.stat().st_size:raise RuntimeError(errors.read_text())
            if log.exists() and "'ERROR'" in log.read_text():raise RuntimeError(log.read_text())
            if log.exists() and "'DONE'" in log.read_text():
                if done is None:done=time.monotonic()
                if time.monotonic()-done>.5:
                    saved_name={'save-active':'ProteanLifecycleActiveOwned','save-original-baseline':'ProteanLifecycleActiveOwned','filter-save':'ProteanFilterOwned'}.get(mode)
                    if saved_name and not (GAME/('Unofficial_Patch/save/'+saved_name+'.sav')).exists():
                        if time.monotonic()-done>5:raise RuntimeError('Engine did not create the owned save')
                    else:break
            time.sleep(.035)
        else:raise RuntimeError('Probe timeout; no successful scenario assertion')
        assert sha(GAME/'Unofficial_Patch/python/vamputil.py')==result['stock_python_sha256'],'Stock Python changed during native-only test'
        result['script_completed']=True
        if mode=='save-active':assert (GAME/'Unofficial_Patch/save/ProteanLifecycleActiveOwned.sav').exists(),'No active save created'
        for relative,digest in result.get('payload_sha256',{}).items():
            assert sha(GAME/relative)==digest and sha(HERE/'candidate/Payload'/relative)==digest,'Candidate changed during test'
        if reader:
            base=reader.modules['vampire.dll'];assert reader.read(base+0x16be10,4)==bytes.fromhex('83ec20a1'),'Test bootstrap did not remove its hook'
        print('\n'.join(line for line in log.read_text().splitlines() if not line.startswith("('NATIVE',")),flush=True)
        from audit_coexist_game import audit
        if mode!='frenzy-melee':
            from audit_game import audit
        result['assertions']=audit(mode,log.read_text(),rows)
        result['passed']=True
    except BaseException as e:
        result['error']=repr(e);traceback.print_exc()
    finally:
        if reader:k.CloseHandle(reader.h)
        if proc and proc.poll() is None:proc.terminate();proc.wait(timeout=15)
        if not gr.running_games() and hasattr(tx,'records'):
            try:tx.restore();result['restored']=True
            except Exception as error:result['restore_error']=repr(error);traceback.print_exc()
        dump(session/'observations.json',rows);dump(session/'result.json',result)
        if (HERE/'native-events.log').exists():shutil.copy2(HERE/'native-events.log',session/'native-events.log')
        if result.get('restored') and lock.exists() and json.loads(lock.read_text())['session']==str(session):lock.unlink()
        if result.get('restored'):
            from prune_backups import prune
            prune(session)
        print('RESULT',json.dumps(result),flush=True)
    if not result.get('passed'):raise SystemExit(1)
if __name__=='__main__':run()
