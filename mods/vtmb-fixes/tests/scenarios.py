"""Fresh owned-game recipes using retained observers, never dated certificates."""
import hashlib,json,os,re,runpy,shutil,struct,sys,time,threading
from pathlib import Path

def dump(path,value):path.write_bytes((json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode())
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()

def player_stamp(p):
 try:
  server=p.modules['vampire.dll'];table=p.u(server+0x566458);_,pc,serial=struct.unpack('<3I',p.read(table+12,12))
  if pc and p.read(p.u(pc+0x11c),7)==b'player\0':return pc,serial
 except OSError:pass
 return None

def transition(ctx,p,old):
 end=time.monotonic()+70
 while True:
  stamp=player_stamp(p)
  if stamp is not None and stamp!=old:break
  assert time.monotonic()<end,'Native actor identity did not change during transition'
  time.sleep(.05)
 ctx['wait_world'](ctx['proc'],p)

def console(ctx):
 repo,game,folder=ctx['repo'],ctx['game'],ctx['folder']
 source=(repo/'mods/console/tests/gameplay/console_clean.py').read_text()
 assert source.count("d.text_command('load rc_console',4)")==1
 source=source.replace("d.text_command('load rc_console',4)",'_reload(d)')
 source=source.replace('time.sleep(25);d=Driver(session)','d=Driver(session)')
 # Keep distinct phases separate until the native menu-close transition settles.
 source=source.replace(" d.phase='script';"," d.delay(1.0)\n d.phase='script';")
 shutil.copy2(repo/'mods/console/tests/gameplay/console_task_overlap.cfg',game/'Unofficial_Patch/cfg/console_task_overlap.cfg')
 def reload(d):
  from infra.container_gameplay import Control
  old=d.snap()['player_handle'];stamp=player_stamp(d.p);d.game=game
  Control.command(d,'load '+ctx['stem'],.3,transition=True)
  transition(ctx,d.p,stamp);d.player=None;d.hwnd=d.p.window()
  assert d.snap()['player_handle']!=old,'Reload did not create a new native player'
 argv=sys.argv;sys.argv=[str(repo/'mods/console/tests/gameplay/console_clean.py'),str(folder)]
 try:exec(compile(source,'<fresh unified console recipe>','exec'),{'_reload':reload})
 finally:sys.argv=argv
 result=json.loads((folder/'runner-result.json').read_text());assert result['passed'];return result

def history(ctx):
 folder=ctx['folder'];dump(folder/'identity.json',{'plugin':ctx['sha'](ctx['game']/'Bin/loader/ant2684-fixes-adjustments.vtm')})
 original=ctx['repo']/'infra/history_auto_spend.py';source=original.read_text()
 assert source.count('d.key(0x32);time.sleep(1)')==1
 source=source.replace('d.key(0x32);time.sleep(1)','time.sleep(4);_number(d,"2");_creation_ready(d)')
 a=source.index('def start_observed():');b=source.index('\ndef record(',a)
 source=source[:a]+'''def start_observed():
    rect=W.RECT();u.GetWindowRect(d.hwnd,C.byref(rect))
    assert (rect.left,rect.top,rect.right,rect.bottom)==(0,0,2560,1440)
    time.sleep(2);assert not d.console(),'Fresh main menu should not open a console'
    d.record('actual_menu',True);d.click(1280,615)
    end=time.monotonic()+45
    while not d.snap()['players']:
        assert time.monotonic()<end,'New Game did not create its native player';time.sleep(.2)
    time.sleep(3);d.key(0x77);time.sleep(1);d.click(517,167);_creation_ready(d);_name(d)
''' +source[b:]
 source=source.replace('d.click(2260,1328)','_allocation_button(d)')
 source=source.replace('select_history(d,10)','_bonus_history(d)')
 def name(d):
  from drive import INPUT,U,KI
  d.click(600,74)
  for ch in 'VFTest':
   ev=INPUT(1,U(ki=KI(0,ord(ch),4,0,0)))
   try:d.send(ev)
   finally:ev.value.ki.flags=6;d.send(ev,False)
  d.key(13);d.record('named_character',True)
 def number(d,value):
  # This is the registered native wizard command: its handler requires the
  # active wizard, maps the one-based choice and calls the original UI action.
  d.command('vchargen_key '+value,.3)
  if d.console():d.click(1444,123)
  time.sleep(.4)
 def creation_ready(d):
  from infra.history_ui import observe
  from driver import Driver as NativePanel
  end=time.monotonic()+45;last=0
  while time.monotonic()<end:
   if d.p.read(d.p.modules['vampire.exe']+0x3f32c,1)[0]:
    if time.monotonic()-last>2:d.click(1280,720);last=time.monotonic()
   else:
    if time.monotonic()-last>2:d.click(517,167);last=time.monotonic()
    ui=observe(d.p)
    if ui.get('initialized'):
     panel=NativePanel.panel(d,ui['auto_button']);x1,y1,x2,y2=panel['bounds']
     if 0<=x1<x2<=2560 and 0<=y1<y2<=1440 and 20<x2-x1<1000 and 10<y2-y1<150:return
   time.sleep(.1)
  d.record('creation_ready_timeout',True);raise RuntimeError('Character editor did not finish loading/layout after native question')
 def bonus_history(d):
  d.click(180,166);d.click(1215,729);d.record('history_dropdown',True)
  # Installed UHD draws 38px rows; All-Star Athlete is visibly row ten.
  d.click(200,1155)
 def allocation_button(d):
  from infra.history_ui import observe
  from driver import Driver as NativePanel
  ui=observe(d.p);buttons=[]
  for key in ['auto_button','reset_button']:
   panel=NativePanel.panel(d,ui[key])
   if panel['visible']:buttons.append((key,panel))
  assert len(buttons)==1,('Expected one visible allocation action',buttons)
  key,panel=buttons[0];x1,y1,x2,y2=panel['bounds'];assert 0<x2-x1<600 and 0<y2-y1<150
  with (folder/'allocation-actions.jsonl').open('a') as out:out.write(json.dumps({'button':key,'panel':panel,'before':ui})+'\n')
  d.click((x1+x2)//2,(y1+y2)//2)
 recipe=folder/'history-native-recipe.py';recipe.write_bytes(source.encode())
 argv=sys.argv;sys.argv=[str(original),str(folder),'full']
 try:exec(compile(source,str(recipe),'exec'),{'__file__':str(original),'__name__':'__vf_history__','_allocation_button':allocation_button,'_creation_ready':creation_ready,'_number':number,'_bonus_history':bonus_history,'_name':name})
 finally:sys.argv=argv
 result=json.loads((folder/'full-result.json').read_text());assert result['result']=='PASS';return result

def container(ctx):
 from infra import container_gameplay as recipe
 from process_reader import k
 from driver import Driver
 folder,game=ctx['folder'],ctx['game'];baseline=ctx['scenario']=='container-baseline'
 native=['Bin/engine.dll','Vampire/cl_dlls/client.dll','Vampire/dlls/vampire.dll','Vampire/cl_dlls/GameUI.dll']
 background={p.relative_to(game).as_posix():digest(p) for p in (game/'Bin/loader').glob('*.vtm') if not p.name.startswith('zz-vf-')}
 identity={'session':folder.name,'scenario':'container.baseline' if baseline else 'container.stacks','scenario_version':2 if baseline else 3,
  'modules':{rel:digest(game/rel) for rel in native},'artifacts':{} if baseline else {'Bin/loader/ant2684-fixes-adjustments.vtm':digest(game/'Bin/loader/ant2684-fixes-adjustments.vtm')},
  'resources':{},'background_mods':background,'save_sha256':digest(ctx['seed']),
  'configuration_control':'Same exact unified VTM and background modules; only ContainerStackFix is 0 in baseline, all other groups remain 1'}
 dump(folder/'identity.json',identity)
 if not baseline:
  assert ctx['baseline'] is not None
  os.environ['VTMB_CONTAINER_BASELINE']=str(ctx['baseline'].resolve())
 # Existing Loading Wait For Enter is preserved. Send its native continuation
 # key only to our foreground game; no video/config override for the prompt.
 original_snap=recipe.Control.snap;original_choices=recipe.Control.dialog_choices;original_command=recipe.Control.command;original_key=recipe.Control.key
 last=[0.0]
 def snap(d):
  if d.p.read(d.p.modules['vampire.exe']+0x3f32c,1)[0] and time.monotonic()-last[0]>1:
   d.key(0x0d);last[0]=time.monotonic()
  return original_snap(d)
 def choices(d):
  value=original_choices(d)
  if value.get('npc_speaking'):
   d.key(ord('1'));d.delay(.1)
   with (folder/'dialogue-skips.jsonl').open('a') as out:out.write(json.dumps({'wall':time.time(),'native_npc_speaking':True,'input':'1'})+'\n')
  return value
 def key(d,vk,*args,**kwargs):
  if ord('1')<=vk<=ord('9'):
   state=original_choices(d)
   assert state['active'],'Native dialogue must own a selected reply'
   selected=-2 if state.get('npc_speaking') else vk-ord('1')
   if selected>=0:assert selected<len(state['choices'])
   d.command('dialogpick '+str(selected),.2)
   with (folder/'native-dialogue-commands.jsonl').open('a') as out:out.write(json.dumps({'before':state,'selected':selected,'command':'dialogpick '+str(selected)})+'\n')
  else:return original_key(d,vk,*args,**kwargs)
 def command(d,line,wait=.6,transition=False):
  stamp=player_stamp(d.p) if transition else None
  original_command(d,line,wait,transition)
  if transition:
   globals()['transition'](ctx,d.p,stamp);d.player=None;d.hwnd=d.p.window()
 recipe.Control.snap=snap;recipe.Control.dialog_choices=choices;recipe.Control.command=command;recipe.Control.key=key
 try:return recipe.collect(folder)
 finally:recipe.Control.snap=original_snap;recipe.Control.dialog_choices=original_choices;recipe.Control.command=original_command;recipe.Control.key=original_key

def radio(ctx):
 sys.path.insert(0,str(ctx['repo']/'mods/subtitle/tests'))
 import startup_gameplay as recipe
 p=recipe.StartupProbe(ctx['folder']);rows={}
 def record(label,seconds=2):rows[label]=recipe.record(p,label,seconds);return rows[label]
 def change(command,mapname):
  old=next(e for e in p.entities() if e['class']=='player')
  stamp=player_stamp(p.p);p.command(command);transition(ctx,p.p,stamp)
  row=recipe.ready(p,mapname,(old['entity'],old['serial']));return row
 recipe.ready(p,'sm_pawnshop_1');recipe.advancing(record('initial',3),True)
 p.command('ent_fire Radio2 Deactivate');recipe.advancing(record('off'),False)
 p.command('ent_fire Radio2 Activate');recipe.advancing(record('resumed'),True)
 p.command('ent_fire Radio2 Activate');recipe.advancing(record('repeat_on'),True)
 cfg=(ctx['game']/'Unofficial_Patch/cfg/config.cfg').read_text(encoding='cp1252')
 assert not re.search(r'bind\s+"?F11\b',cfg,re.I),'Preserve existing F11 binding'
 p.command('bind F11 pause');p.key(0x57);time.sleep(.4);paused=record('paused',3)
 assert all(r['paused']==r['server_paused']==1 for r in paused)
 assert abs(paused[-1]['server_time']-paused[0]['server_time'])<.02
 before,after=recipe.radio(paused[0])[1],recipe.radio(paused[-1])[1]
 assert (before['mixer'],before['source'])==(after['mixer'],after['source'])
 assert abs(after['sample_position']-before['sample_position'])<=2048 and after['caption_index']==before['caption_index']
 p.key(0x57);p.command('unbind F11');recipe.advancing(record('after_pause'),True)
 p.command('save rc_startup_on');change('load rc_startup_on','sm_pawnshop_1');recipe.advancing(record('loaded_on'),True)
 p.command('ent_fire Radio2 Deactivate');p.command('save rc_startup_off');change('load rc_startup_off','sm_pawnshop_1');recipe.advancing(record('loaded_off'),False)
 p.command('ent_fire Radio2 Activate');recipe.advancing(record('loaded_resume'),True)
 change('map la_hub_1','la_hub_1');recipe.advancing(record('default_off'),False)
 change('map sm_pawnshop_1','sm_pawnshop_1');recipe.advancing(record('fresh_return'),True)
 return {'status':'PASS','scope':'Fresh first-on, off/on/repeated-on, visible current caption, decoder/world pause and resume, saved on/off reload and map return',
  'limits':'No independent process PCM correlation, TV transition or full unaccelerated radio loop is certified by this recipe'}

def loading(ctx):
 """Actual reload, press/release continuation and first fresh native attack."""
 from infra.container_gameplay import Control
 from driver import INPUT,U,MI,u,C
 d=Control(ctx['folder']);p=d.p;e=p.modules['engine.dll'];c=p.modules['client.dll'];sv=p.modules['vampire.dll']
 stop=threading.Event();rows=[];phase=['initial'];errors=[]
 def sample():
  row={'t':time.monotonic(),'phase':phase[0],'plaque':p.u(e+0xb42318),'loading_byte':p.read(e+0xb42314,1)[0],
   'waiting_click':p.read(p.modules['vampire.exe']+0x3f32c,1)[0],'host':p.u(e+0xd5e0b0),'pending':p.u(e+0xd5e0b4),'attack_state':p.u(c+0x4d2f44),'mouse1':bool(u.GetAsyncKeyState(1)&0x8000)}
  try:
   table=p.u(sv+0x566458);entry=p.read(table+12,12);_,pc,serial=struct.unpack('<3I',entry)
   if pc and p.read(p.u(pc+0x11c),7)==b'player\0':
    raw=p.read(pc+0x2088,16)
    if p.read(table+12,12)==entry:row.update(pc=pc,serial=serial,buttons=struct.unpack('<4I',raw),sequence=p.u(pc+0x6f0))
  except OSError:pass
  return row
 def observe():
  try:
   with (ctx['folder']/'loading-observations.jsonl').open('x') as f:
    while not stop.is_set():
     row=sample();rows.append(row);f.write(json.dumps(row,separators=(',',':'))+'\n');time.sleep(.002)
  except BaseException as error:errors.append(repr(error))
 def button(down):d.send(INPUT(0,U(mi=MI(0,0,0,2 if down else 4,0,0))),check=down)
 thread=threading.Thread(target=observe);thread.start();held=False
 try:
  if d.snap()['console']['visible']:d.click_x()
  phase[0]='positive_before';button(True);held=True;d.delay(.2);button(False);held=False;d.delay(.2)
  assert any(r['phase']=='positive_before' and r.get('buttons',[0,0])[1]&1 for r in rows),'Pre-load native server attack control missing'
  phase[0]='reload';old=d.snap()['player_handle'];d.command('load '+ctx['stem'],.05,transition=True)
  end=time.monotonic()+45
  while not p.u(e+0xb42318):
   assert time.monotonic()<end,'Loading plaque never became active';time.sleep(.005)
  end=time.monotonic()+70
  while not p.read(p.modules['vampire.exe']+0x3f32c,1)[0]:
   assert time.monotonic()<end,'Native click continuation prompt never appeared'
   d.focus();time.sleep(.01)
  phase[0]='loading_click_and_hold';button(True);held=True;d.delay(.4)
  assert p.read(p.modules['vampire.exe']+0x3f32c,1)[0],'Loader unexpectedly continued before release'
  phase[0]='release';button(False);held=False
  ctx['wait_world'](ctx['proc'],p,continue_loading=False)
  phase[0]='after_continue';d.delay(.8);d.player=None;after=d.snap();assert after['player_handle']!=old,'Native reload identity unchanged'
  phase[0]='fresh_press';button(True);held=True;d.delay(.2);button(False);held=False;d.delay(.2)
  forbidden=[r for r in rows if r['phase'] in ['loading_click_and_hold','after_continue'] and any(v&1 for v in r.get('buttons',[0,0])[:2])]
  assert not forbidden,('Unexpected native attack across loading',forbidden[:3])
  assert any(r['phase']=='fresh_press' and r.get('buttons',[0,0])[1]&1 for r in rows),'First fresh post-release press did not reach native server attack'
  return {'status':'PASS','scope':'Fresh reload with actual press/release continuation; loading click causes no post-load attack, first fresh press reaches native server attack','rows':len(rows),'unexpected_attack_samples':len(forbidden),'limits':'External 2ms polling is sampled; this Loader requires release to continue, so held-button arrival is not reachable in its current mode. No taxi/melee matrix claimed'}
 finally:
  if held:button(False)
  stop.set();thread.join(5);assert not thread.is_alive() and not errors,errors

def literal_command(d,line,wait=.4,transition=False):
 # The game's interactive console also recognizes commands that are not cfg
 # commands. Submit this one bounded line literally, preserving native routing.
 from driver import INPUT,U,KI
 assert '\n' not in line and '\r' not in line
 if not d.snap()['console']['visible']:d.toggle(True)
 control=INPUT(1,U(ki=KI(0,0x1d,8,0,0)))
 try:d.send(control);d.key(ord('A'),.03)
 finally:control.value.ki.flags=10;d.send(control,False)
 d.key(8,.03)
 for ch in line:
  ev=INPUT(1,U(ki=KI(0,ord(ch),4,0,0)))
  try:d.send(ev);d.delay(.008)
  finally:ev.value.ki.flags=6;d.send(ev,False)
 d.key(13,.03)
 if transition:time.sleep(wait);return
 d.delay(wait)
 if line.startswith(('vstats ','vclan ')):
  from PIL import ImageGrab
  ImageGrab.grab().save(d.session/('interactive-vstats-%d.png'%time.time_ns()))
 if d.snap()['console']['visible']:d.click_x(.35)
 d.delay(.3)

def protean(ctx):
 from infra.container_gameplay import Control
 d=Control(ctx['folder']);d.command=lambda line,wait=.6,transition=False:literal_command(d,line,wait,transition);p=d.p;sv=p.modules['vampire.dll'];states={}
 def state(label):
  entities=d.entities();players=[v for v in entities.values() if v['class']=='player'];assert len(players)==1
  pc=players[0]['address'];world=p.u(sv+0x7532e8)
  value={'player':players[0],'active_protean':p.u(pc+0x1380),'wolf':p.read(pc+0x1edc,1)[0],'frenzy':p.u(pc+0x146c),'controller':p.u(pc+0x1db0),
   'world_nofrenzy':p.read(world+0x4a9,1)[0] if world else -1,'shadows':[v for v in entities.values() if v['class']=='npc_VFrenzyShadow']}
  states[label]=value;dump(ctx['folder']/'protean-states.json',states);return value
 stamp=player_stamp(p);d.command('changelevel la_library_1',.1,transition=True);transition(ctx,p,stamp);d.player=None;d.ui_address=None
 d.command('sv_cheats 1',.2);d.command('vclan player_gangrel',.3);d.command('giftxp 1000',.2)
 first=state('fresh_library');assert first['world_nofrenzy']==0 and not first['shadows']
 d.command("__import__('__main__').FindPlayer().Bloodgain(15)",.2)
 # Nominated character may have a different base rank; observe it explicitly.
 path=ctx['folder']/'base-protean.txt'
 def rank():
  d.command("__import__('__builtin__').open("+repr(str(path))+",'w').write(str(__import__('__main__').FindPlayer().base_protean))",.2)
  return int(path.read_text())
 for _ in range(3):
  n=rank()
  pc=player_stamp(p)[0];groups=p.u(pc+0x13c0);g=p.u(groups);vals=p.u(p.u(g+8))
  with (ctx['folder']/'rank-progress.jsonl').open('a') as out:out.write(json.dumps({'rank':n,'xp':p.u(vals+34*4),'clan':p.u(vals+10*4)})+'\n')
  if n==5:break
  d.command('vstats get protean 5',.3)
 assert rank()==5
 d.command('vdiscipline_int protean',.1);d.delay(3);war=state('warform');assert war['active_protean']==5 and war['wolf']==1
 d.command("__import__('__main__').FindEntityByName('guard1').ScriptUnhide()",.2)
 setup=ctx['game']/'Unofficial_Patch/python/vf_library_setup.py'
 setup.write_bytes(b"import __main__\ndef apply():\n p=__main__.FindPlayer();n=__main__.FindEntityByName('guard1');xyz=n.GetOrigin();p.SetOrigin((xyz[0]+100,xyz[1],xyz[2]))\n")
 d.command("__import__('vf_library_setup').apply()",.2)
 pc=state('before_frenzy_setup')['player']['address']
 if p.u(pc+0x434)&0x8000:d.command('notarget',.2)
 d.command("__import__('__main__').FindEntityByName('guard1').SetRelationship('player D_HT 10')",.2)
 d.command('frenzyplayer',.1);until=time.monotonic()+6
 while True:
  both=state('warform_frenzy')
  if both['frenzy']>0 and len(both['shadows'])==1:break
  assert time.monotonic()<until,'Native Frenzy did not acquire its Shadow after the original transition'
  d.delay(.1)
 assert both['wolf']==1
 d.command('vdiscipline_endall',.1);d.delay(3);ending=state('protean_ended');assert ending['active_protean']==0 and ending['wolf']==0
 # A real map transition must discard every previous Frenzy/Shadow lifetime.
 stamp=player_stamp(p);d.command('map sm_pawnshop_1',.1,transition=True);transition(ctx,p,stamp);d.player=None;clean=state('map_cleanup');assert not clean['shadows'] and not clean['frenzy'] and not clean['wolf']
 return {'status':'PASS','scope':'Preserved Library map permission; actual P5 form, native Frenzy with one Shadow, form end and fresh-map cleanup alongside all fixes','limits':'Unchanged PFI release retains its prior detailed qualification; this scenario does not repeat Griffith collision or all melee cases'}

def flame(ctx):
 """Real flamethrower/NPC hit and stock floating-number queue, no DLL probe."""
 import math
 from infra.container_gameplay import Control
 from driver import INPUT,U,MI
 from PIL import ImageGrab
 d=Control(ctx['folder']);p=d.p;sv=p.modules['vampire.dll'];stamp=player_stamp(p)
 d.command('map la_library_1',.1,transition=True);transition(ctx,p,stamp);d.player=None
 helper=ctx['game']/'Unofficial_Patch/python/vf_flame_setup.py'
 helper.write_bytes(b"import __main__\ndef apply():\n p=__main__.FindPlayer();n=__main__.FindEntityByName('guard1');n.ScriptUnhide();xyz=p.GetOrigin();n.SetOrigin((xyz[0]+200,xyz[1],xyz[2]));n.SetRelationship('player D_NU 10');p.GiveItem('item_w_flamethrower');p.GiveAmmo('item_w_flamethrower',1000)\n")
 d.command('sv_cheats 1',.2)
 d.command("__import__('sys').stderr=__import__('__builtin__').open("+repr(str(ctx['folder']/'python-errors.txt'))+",'a',0)",.2)
 d.command("__import__('vf_flame_setup').apply()",.3);d.command('damage_floaters 1',.2)
 d.command("__import__('__builtin__').open("+repr(str(ctx['folder']/'target-methods.txt'))+",'w').write(repr(dir(__import__('__main__').FindEntityByName('guard1'))))",.2)
 d.command('use item_w_flamethrower',.3);d.delay(2)
 view=d.snap()['angles'];yaw=math.radians(view[1]);origin=struct.unpack('<3f',p.read(player_stamp(p)[0]+0x404,12))
 where=(origin[0]+200*math.cos(yaw),origin[1]+200*math.sin(yaw),origin[2])
 d.command("__import__('__main__').FindEntityByName('guard1').SetOrigin("+repr(where)+")",.2)
 entities=d.entities();targets=[v for v in entities.values() if v['name']=='guard1'];assert len(targets)==1
 target=targets[0];pc=next(v['address'] for v in entities.values() if v['class']=='player');weapon=p.u(pc+0x19a4)
 dump(ctx['folder']/'flame-setup.json',{'entities':list(entities.values()),'selected':weapon,'selected_class':entities.get(weapon,{}).get('class'),'state':p.u(pc+0x168),'substate':p.u(pc+0x16c)})
 assert entities[weapon]['class']=='item_w_flamethrower','Native selected weapon is not flamethrower'
 position=struct.unpack('<3f',p.read(pc+0x404,12));location=struct.unpack('<3f',p.read(target['address']+0x404,12));angles=d.snap()['angles'];yaw=math.radians(angles[1]);delta=[location[i]-position[i] for i in range(3)]
 front=delta[0]*math.cos(yaw)+delta[1]*math.sin(yaw);side=-delta[0]*math.sin(yaw)+delta[1]*math.cos(yaw)
 assert 80<front<400 and abs(side)<10 and abs(delta[2])<30,('Target not in the actual view direction',position,location,angles)
 dump(ctx['folder']/'flame-native-target.json',{'npc_component':p.u(target['address']+0x98),'invulnerable':p.read(p.u(target['address']+0x98)+0x63d8,1)[0],'floater_cvar':p.u(p.u(sv+0x752ddc)+0x2c)})
 before=p.u(target['address']+0x210);rows=[];pressed=False;start=time.monotonic();last_picture=0
 try:
  d.send(INPUT(0,U(mi=MI(0,0,0,2,0,0))));pressed=True
  while time.monotonic()-start<4.0:
   d.focus();handles=struct.unpack('<25I',p.read(sv+0x753230,100));heads=struct.unpack('<25I',p.read(sv+0x752ce0,100))
   for index,handle in enumerate(handles):
    if handle==target['handle'] and heads[index]:
     try:owner,amount,next_node=struct.unpack('<3I',p.read(heads[index],12))
     except OSError:continue
     if owner==target['handle'] and 0<amount<10000:rows.append({'t':time.monotonic()-start,'target':handle,'amount':amount,'node':heads[index]})
   if time.monotonic()-start-last_picture>.3:
    ImageGrab.grab().save(ctx['folder']/('flame-%02d.png'%round((time.monotonic()-start)*10)));last_picture=time.monotonic()-start
   time.sleep(.002)
 finally:
  if pressed:d.send(INPUT(0,U(mi=MI(0,0,0,4,0,0))),False)
 after=p.u(target['address']+0x210)
 evidence={'target':target,'weapon':entities[weapon],'view_angles':angles,'player_position':position,'target_position':location,'front':front,'side':side,'raw_health_before':before,'raw_health_after':after,'native_number_queue':rows}
 dump(ctx['folder']/'flame-evidence.json',evidence)
 events=[json.loads(row) for row in (ctx['folder']/'flame-queue.jsonl').read_text().splitlines()] if (ctx['folder']/'flame-queue.jsonl').exists() else []
 dump(ctx['folder']/'flame-native-events.json',events)
 assert rows or any(row['target']==target['address'] and row['amount']>0 for row in events),'Real hit did not produce an observed native damage-number queue entry'
 return {'status':'PASS','scope':'Real equipped flamethrower hit on a verified in-view live NPC; stock floating-number queue contains positive hit amounts','queue_samples':len(rows),'limits':'External native queue observer; the unchanged production VTM and all background modules are present. Raw field +210 is not a qualified health accessor and supports no HP claim. No new net-HP policy or damage-balance claim; screenshots retained separately'}

def run(ctx):
 functions={'console':console,'history':history,'container':container,'container-baseline':container,'radio':radio,'loading':loading,'protean':protean,'flame':flame}
 return functions[ctx['scenario']](ctx)
