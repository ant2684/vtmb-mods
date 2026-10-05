"""User-authorized Windows input; owned PID, read-only game observations."""
import ctypes as C,ctypes.wintypes as W,json,struct,time,sys,re,math
from pathlib import Path
from process_reader import Process,k
from observe import snapshot
u=C.WinDLL('user32',use_last_error=True)
u.SetProcessDPIAware()
u.GetForegroundWindow.restype=W.HWND
u.SetForegroundWindow.argtypes=[W.HWND]
u.ShowWindow.argtypes=[W.HWND,C.c_int]
u.ClientToScreen.argtypes=[W.HWND,C.POINTER(W.POINT)]
u.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
u.GetWindowThreadProcessId.restype=W.DWORD
u.GetKeyboardLayout.argtypes=[W.DWORD]
u.GetKeyboardLayout.restype=C.c_void_p
u.GetAsyncKeyState.argtypes=[C.c_int]
u.GetAsyncKeyState.restype=C.c_short
class KI(C.Structure):_fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',C.c_size_t)]
class MI(C.Structure):_fields_=[('dx',W.LONG),('dy',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',C.c_size_t)]
class U(C.Union):_fields_=[('ki',KI),('mi',MI)]
class INPUT(C.Structure):_fields_=[('kind',W.DWORD),('value',U)]
u.SendInput.argtypes=[W.UINT,C.POINTER(INPUT),C.c_int]
class Driver:
 def __init__(self,session):
  self.session=Path(session);self.owned=json.loads((self.session/'process.json').read_text(encoding='utf-8-sig'));self.p=Process(self.owned['Id']);self.player=None
  times=[W.FILETIME() for _ in range(4)];k.GetProcessTimes.argtypes=[W.HANDLE]+[C.POINTER(W.FILETIME)]*4
  assert k.GetProcessTimes(self.p.h,*[C.byref(t) for t in times])
  assert ((times[0].dwHighDateTime<<32)|times[0].dwLowDateTime)+504911232000000000==self.owned['Ticks']
  self.hwnd=self.p.window();u.ShowWindow(self.hwnd,9);u.SetForegroundWindow(self.hwnd);time.sleep(.7);self.focus()
  cfg=(Path(json.loads((self.session/'launch.json').read_text(encoding='utf-8-sig'))['GameRoot'])/'Unofficial_Patch/cfg/config.cfg').read_text(encoding='cp1252')
  self.bindings={cmd:key for key,cmd in re.findall(r'bind "([^"]+)" "([^"]+)"',cfg) if len(key)==1}
 def focus(self):
  pid=W.DWORD();u.GetWindowThreadProcessId(self.hwnd,C.byref(pid))
  if pid.value!=self.p.pid or u.GetForegroundWindow()!=self.hwnd:raise RuntimeError('Owned game lost foreground; input halted')
 def send(self,event,check=True):
  if check:self.focus()
  if u.SendInput(1,C.byref(event),C.sizeof(event))!=1:raise C.WinError(C.get_last_error())
 def delay(self,t):
  end=time.monotonic()+t
  while time.monotonic()<end:self.focus();time.sleep(min(.02,max(0,end-time.monotonic())))
 def key(self,vk,hold=.08,on_hold=None):
  scan=u.MapVirtualKeyW(vk,0);event=INPUT(1,U(ki=KI(vk if vk==0x13 else 0,0 if vk==0x13 else scan,0 if vk==0x13 else 8,0,0)))
  monitor=vk in (ord('S'),ord('W'),0x1b,0x7a,0xc0)
  if monitor:before=self.snap()
  try:
   self.send(event)
   if monitor:self.log('physical_key_down',before,self.snap(),vk=vk,scan=scan,flags=int(event.value.ki.flags),phase=getattr(self,'phase','unspecified'))
   if on_hold:self.delay(hold/2);on_hold();self.delay(hold/2)
   else:self.delay(hold)
  finally:
   event.value.ki.flags|=2;self.send(event,False)
   if monitor:self.log('physical_key_up',before,self.snap(),vk=vk,scan=scan,flags=int(event.value.ki.flags),phase=getattr(self,'phase','unspecified'))
 def move(self,dx):
  self.send(INPUT(0,U(mi=MI(dx,0,0,1,0,0))));self.delay(.25)
 def panel(self,a):
  if not a:return None
  vp=self.p.u(a+4);raw=self.p.read(vp,0x44)
  assert self.p.read(self.p.u(self.p.u(vp)+0x54),4)==bytes.fromhex('8a4142c3')
  bounds=struct.unpack_from('<4h',raw,0x34)
  return {'address':a,'visible':raw[0x42],'bounds':bounds}
 def snap(self):
  p=self.p;e=p.modules['engine.dll'];ui=p.modules['gameui.dll'];c=p.modules['client.dll'];sv=p.modules['vampire.dll'];r=snapshot(p)
  obj=p.u(e+0x13064a8);dlg=p.u(obj+8);r['console']=self.panel(dlg);r['close']=self.panel(p.u(dlg+0xbc));r['menu']=self.panel(p.u(ui+0x6c338));r['other_ui']=self.panel(p.u(e+0x1306490))
  r['angles']=struct.unpack('<3f',p.read(e+0x314868,12));r['mouse_active']=p.u(p.u(c+0x27ba58)+0x28);r['foreground']=u.GetForegroundWindow()==self.hwnd
  r['keys']={'back':struct.unpack('<3I',p.read(c+0x4d3af0,12)),'forward':struct.unpack('<3I',p.read(c+0x4d3590,12))}
  r['os_keys']={name:bool(u.GetAsyncKeyState(vk)&0x8000) for name,vk in [('S',0x53),('W',0x57),('Ctrl',0x11),('Shift',0x10),('Alt',0x12)]}
  binding=p.u(e+0xd607c8+ord('s')*4)
  r['back_binding']=p.read(binding,64).split(b'\0',1)[0].decode('ascii','replace') if binding else None
  # Read-only native routing state. Key_Event updates keydown before the
  # client filter, and repeats after it; retain all keys to detect remapping.
  r['native_key_route']={'destination':p.u(e+0xd6350c),'blocked':p.u(e+0xd63510),
   'keydown':list(struct.unpack('<256I',p.read(e+0xd5ff50,1024))),
   'repeats':list(struct.unpack('<256I',p.read(e+0xd60fc8,1024)))}
  cp=p.u(c+0x4a0d50)
  r['viewport_route']={'player':cp,'use_panel':p.u(cp+0x16b8) if cp else None,
   'overlay_1':p.u(c+0x3ef0b4),'overlay_2':p.u(c+0x5fb1f8),
   'overlay_3':p.u(c+0x3ee138),'overlay_4':p.u(c+0x3eee40),
   'overlay_4_active':p.read(c+0x3eee48,1)[0]}
  table=p.u(sv+0x566458)
  if self.player:
   idx,serial,ent=self.player
   if p.u(table+idx*12+4)!=ent or p.u(table+idx*12+8)!=serial:self.player=None
  if not self.player:
   found=[]
   for idx in range(8192):
    ent=p.u(table+idx*12+4)
    if not ent:continue
    try:name=p.read(p.u(ent+0x11c),40).split(b'\0',1)[0]
    except OSError:continue
    if name==b'player':found.append((idx,p.u(table+idx*12+8),ent))
   assert len(found)==1,('Expected one player',found)
   self.player=found[0]
  r['player_handle']=self.player[0]|(self.player[1]<<13);r['origin']=struct.unpack('<3f',p.read(self.player[2]+0x404,12))
  return r
 def log(self,label,before,after,**extra):
  row={'label':label,'before':before,'after':after,**extra}
  with (self.session/'input.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
  return row
 def toggle(self,opened,delay=.15):
  b=self.snap();self.key(0xc0);self.delay(delay);a=self.snap();self.log('console_open' if opened else 'console_tilde_close',b,a,delay=delay)
  assert a['console']['visible']==int(opened),('Console visibility did not transition',a)
 def click_x(self,delay=.15):
  b=self.snap();assert b['console']['visible'] and b['close']['visible']
  x1,y1,x2,y2=b['close']['bounds'];assert 8<=x2-x1<=100 and 8<=y2-y1<=100
  point=W.POINT((x1+x2)//2,(y1+y2)//2);assert u.ClientToScreen(self.hwnd,C.byref(point))
  vx,vy,vw,vh=(u.GetSystemMetrics(i) for i in (76,77,78,79));x=int((point.x-vx)*65535/(vw-1));y=int((point.y-vy)*65535/(vh-1))
  self.send(INPUT(0,U(mi=MI(x,y,0,0xc001,0,0))));self.delay(.03)
  try:self.send(INPUT(0,U(mi=MI(0,0,0,2,0,0))));self.delay(.05)
  finally:self.send(INPUT(0,U(mi=MI(0,0,0,4,0,0))),False)
  self.delay(delay);a=self.snap();self.log('console_x_close',b,a,point=[point.x,point.y]);assert not a['console']['visible'],'True X click did not close console'
 def probe(self,label,require_both=True):
  self.delay(.8)
  quiet=self.snap();self.delay(.25);start=self.snap();self.log(label+'_quiet',quiet,start)
  drift=math.hypot(start['origin'][0]-quiet['origin'][0],start['origin'][1]-quiet['origin'][1]);angles=[]
  for dx in (80,-80):
   b=self.snap();self.move(dx);a=self.snap();delta=(a['angles'][1]-b['angles'][1]+180)%360-180
   angles.append(delta);self.log(label+'_mouse',b,a,dx=dx,yaw_delta=delta)
  movements=[];directed=[];accepted=[]
  for cmd in ('+back','+forward'):
   key=self.bindings[cmd];b=self.snap();held=[];self.key(ord(key.upper()),.25,lambda:held.append(self.snap()));self.delay(.15);a=self.snap();dist=math.hypot(a['origin'][0]-b['origin'][0],a['origin'][1]-b['origin'][1]);movements.append(dist)
   accepted.append(bool(held[0]['keys'][cmd[1:]][2]&1))
   yaw=math.radians(b['angles'][1]);dot=(a['origin'][0]-b['origin'][0])*math.cos(yaw)+(a['origin'][1]-b['origin'][1])*math.sin(yaw)
   directed.append(-dot if cmd=='+back' else dot)
   self.log(label+'_move',b,a,held=held[0],binding=key,command=cmd,horizontal=dist,forward_projection=dot)
  a=self.snap();result={'label':label,'time':start['client_time']-quiet['client_time'],'yaw':angles,'horizontal':movements,'mouse_active':a['mouse_active'],'paused':a['paused'],'server':a['server_paused'],'menu_depth':a['menu_pause_depth']}
  result.update(quiet_drift=drift,directed=directed,accepted=accepted,require_both=require_both)
  movement_ok=min(directed)>2 if require_both else max(directed)>2 and min(directed)>=-.5
  result['passed']=result['time']>.1 and angles[0]*angles[1]<0 and min(map(abs,angles))>.5 and movement_ok and all(accepted) and drift<1 and a['mouse_active']==1 and a['paused']==a['server_paused']==0 and a['menu_pause_depth']==0
  print(json.dumps(result),flush=True);return result
 def text_command(self,text,post_delay=4):
  # Only reload is needed in normal-binary input verification. No movement commands.
  assert text in ('v_setpause','v_unpause','pause','hideconsole','ent_fire Radio2 Activate','ent_fire Radio2 Deactivate','exec console_task_overlap.cfg','bind F11 pause','developer 0','exec cleanup_aliases.cfg') or re.fullmatch(r'(?:load|save) rc_[a-z0-9_]+',text) or re.fullmatch(r"__import__\('cleanup_probe'\)\.action\('[a-z0-9_]+'\)",text),text
  tid=u.GetWindowThreadProcessId(self.hwnd,None);u.GetKeyboardLayout.restype=C.c_void_p
  if not self.snap()['console']['visible']:self.toggle(True)
  # Clear a retained console edit/history entry before typing. Keep the layout.
  control=INPUT(1,U(ki=KI(0,0x1d,8,0,0)))
  try:self.send(control);self.key(ord('A'),.06)
  finally:control.value.ki.flags=10;self.send(control,False)
  self.key(0x08,.06)
  for char in text:
   event=INPUT(1,U(ki=KI(0,ord(char),4,0,0)))
   try:self.send(event);self.delay(.05)
   finally:event.value.ki.flags=6;self.send(event,False)
  b=self.snap();self.key(0x0d);self.delay(post_delay);a=self.snap();self.log('console_command',b,a,command=text)
  if text.startswith('load rc_'):assert a['player_handle']!=b['player_handle'] and not a['console']['visible'] and a['server_paused']==0,'Fresh reload not confirmed'
  elif text=='v_setpause':assert a['pause_depth']==1 and a['server_paused']==1 and not a['console']['visible'],'Script pause command not confirmed'
