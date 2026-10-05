"""Owned-process read-only broadcast observations and bounded console input."""
import ctypes as C, ctypes.wintypes as W, json, struct, time, sys
from pathlib import Path
from PIL import ImageGrab
from process_reader import Process,k
from observe import snapshot
u=C.WinDLL('user32',use_last_error=True);u.SetProcessDPIAware()
u.GetForegroundWindow.restype=W.HWND
u.SetForegroundWindow.argtypes=[W.HWND];u.ShowWindow.argtypes=[W.HWND,C.c_int]
class KI(C.Structure):_fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',C.c_size_t)]
class MI(C.Structure):_fields_=[('dx',W.LONG),('dy',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',C.c_size_t)]
class U(C.Union):_fields_=[('ki',KI),('mi',MI)]
class INPUT(C.Structure):_fields_=[('kind',W.DWORD),('value',U)]
u.SendInput.argtypes=[W.UINT,C.POINTER(INPUT),C.c_int]
class Probe:
 def __init__(self,session):
  self.session=Path(session);self.owned=json.loads((self.session/'process.json').read_text(encoding='utf-8-sig'));self.p=Process(self.owned['Id'])
  ft=[W.FILETIME() for _ in range(4)];k.GetProcessTimes.argtypes=[W.HANDLE]+[C.POINTER(W.FILETIME)]*4
  assert k.GetProcessTimes(self.p.h,*[C.byref(t) for t in ft])
  assert ((ft[0].dwHighDateTime<<32)|ft[0].dwLowDateTime)+504911232000000000==self.owned['Ticks']
  self.hwnd=self.p.window();u.ShowWindow(self.hwnd,9);u.SetForegroundWindow(self.hwnd);time.sleep(.5)
 def focus(self):
  owner=W.DWORD();u.GetWindowThreadProcessId(self.hwnd,C.byref(owner))
  if owner.value!=self.owned['Id']:raise RuntimeError('Owned game window identity changed')
  if u.GetForegroundWindow()!=self.hwnd:
   u.SetForegroundWindow(self.hwnd);time.sleep(.3)
  if u.GetForegroundWindow()!=self.hwnd:raise RuntimeError('Owned game lost foreground')
 def send(self,scan,flags,check=True):
  if check:self.focus()
  ev=INPUT(1,U(ki=KI(0,scan,flags,0,0)))
  if u.SendInput(1,C.byref(ev),C.sizeof(ev))!=1:raise C.WinError(C.get_last_error())
 def key(self,scan):
  try:self.send(scan,8);time.sleep(.06)
  finally:self.send(scan,10,False)
  time.sleep(.08)
 def pause_key(self):
  self.focus();event=INPUT(1,U(ki=KI(0x13,0,0,0,0)))
  try:
   assert u.SendInput(1,C.byref(event),C.sizeof(event))==1;time.sleep(.08)
  finally:
   event.value.ki.flags=2;assert u.SendInput(1,C.byref(event),C.sizeof(event))==1
  time.sleep(.3)
 def console(self):
  p=self.p;e=p.modules['engine.dll'];dlg=p.u(p.u(e+0x13064a8)+8)
  return bool(p.read(p.u(dlg+4)+0x42,1)[0])
 def command(self,cmd):
  allowed=('load autosave','load broadcast_sync_diag','save broadcast_sync_diag','ent_fire tv_button Press','ent_fire Radio2 Activate','ent_fire Radio2 Deactivate','map sm_apartment_1','pause','bind F11 pause','unbind F11','ent_fire newscaster SetFakeSilence 0','ent_fire newscaster SetFakeSilence 1','ent_fire tv_screen ScriptUnhide','ent_fire tv_screen ScriptHide')
  if cmd not in allowed:raise ValueError(cmd)
  if not self.console():self.key(0x29);time.sleep(.5)
  self.focus()
  try:self.send(0x1d,8);self.key(0x1e)
  finally:self.send(0x1d,10,False)
  self.key(0x0e)
  for ch in cmd:
   try:self.send(ord(ch),4);time.sleep(.035)
   finally:self.send(ord(ch),6,False)
  self.key(0x1c);time.sleep(.3)
  if self.console():self.key(0x29)
  with (self.session/'commands.jsonl').open('a') as f:f.write(json.dumps({'qpc':time.perf_counter(),'wall':time.time(),'command':cmd})+'\n')
 def string(self,address,n=256):
  if not address:return ''
  try:return self.p.read(address,n).split(b'\0',1)[0].decode('cp1252','replace')
  except OSError:return '<unreadable>'
 def entities(self):
  p=self.p;sv=p.modules['vampire.dll'];table=p.u(sv+0x566458);data=p.read(table,8192*12);out=[]
  for idx in range(8192):
   _,ent,serial=struct.unpack_from('<III',data,idx*12)
   if not ent:continue
   try:cls=self.string(p.u(ent+0x11c),64)
   except OSError:continue
   if any(x in cls.lower() for x in ('radio','newscaster','scene')) or cls in ('player','func_button'):
    row={'idx':idx,'serial':serial,'entity':ent,'class':cls,'strings':{}}
    raw=p.read(ent,0x130)
    for off in range(0xe8,0x130,4):
     val=struct.unpack_from('<I',raw,off)[0]
     s=self.string(val,128)
     if s and s!='<unreadable>' and all(32<=ord(c)<127 for c in s):row['strings'][hex(off)]=s
    if 'newscaster' in cls.lower():
     row['fake_silence']=p.read(ent+0x104,1)[0];row['playing']=p.read(ent+0x64c0,1)[0];row['news_fields']=p.read(ent+0x665c,0x38).hex()
     handle=p.u(ent+0x6554);row['scene_handle']=handle
     if handle!=0xffffffff:
      _,scene,ser=struct.unpack_from('<III',data,(handle&0x1fff)*12)
      if ser==handle>>13 and scene:
       row['scene']={'address':scene,'filename':self.string(p.u(scene+0x450)), 'raw':p.read(scene+0x440,0x190).hex()}
    if 'radio' in cls.lower():row['fake_silence']=p.read(ent+0x104,1)[0]
    if cls=='scripted_scene':
     row['scene_file']=self.string(p.u(ent+0x450));row['scene_raw']=p.read(ent+0x440,0x240).hex()
    out.append(row)
  return out
 def channels(self):
  p=self.p;e=p.modules['engine.dll'];count=p.u(e+0x13107d4);assert count<=128;out=[]
  for i in range(count):
   a=e+0x1310b08+i*0xa0;sfx=p.u(a)
   if not sfx:continue
   name=self.string(sfx+4)
   if not any(x in name.lower() for x in ('radio','newscaster','tv_')):continue
   mixer=p.u(a+4);source=p.u(sfx+0x104)
   row={'index':i,'channel':a,'name':self.string(sfx+1),'sfx':sfx,'mixer':mixer,'source':source,'caption_index':p.u(a+0x94),'caption_start':p.f(a+0x98),'raw':p.read(a,0xa0).hex()}
   if mixer:
    row['mixer_vtable']=p.u(mixer)-e;row['sample_position']=p.d(mixer+8);row['mixer_raw']=p.read(mixer,0x50).hex()
   if source:
    row['source_vtable']=p.u(source)-e;row['sample_rate']=p.u(source+8);row['source_raw']=p.read(source,0x80).hex()
    try:
     caption=source+0x18;pi=row['caption_index']>>16;si=row['caption_index']&65535;count=p.u(caption+0x820)
     if 0<count<512 and pi<count:
      phrase=p.u(p.u(caption+0x814)+pi*4);sentences=p.u(phrase+0x10);n=p.u(phrase+0x1c)
      if 0<n<1024 and si<n:
       s=sentences+si*12;row['caption_interval']={'phrase':pi,'sentence':si,'start':p.f(s),'end':p.f(s+4),'text':self.string(p.u(s+8),2048)}
    except OSError:pass
   out.append(row)
  return out
 def snap(self):
  p=self.p;e=p.modules['engine.dll'];sv=p.modules['vampire.dll'];row=snapshot(p);row['qpc']=time.perf_counter();row['server_time']=p.f(p.u(sv+0x70b228)+12);row['channels']=self.channels();row['last_caption']=self.string(e+0x1306a40,2048);row['entities']=self.entities()
  return row
 def record(self,label,seconds=0):
  dest=self.session/label;dest.mkdir(exist_ok=True);start=time.perf_counter();last=-100;count=0
  with (dest/'trace.jsonl').open('a') as f:
   while True:
    row=self.snap();row['elapsed']=time.perf_counter()-start;f.write(json.dumps(row)+'\n');f.flush()
    if row['elapsed']-last>=2:
     self.focus();ImageGrab.grab().save(dest/f'{count:03d}.png');count+=1;last=row['elapsed']
    if row['elapsed']>=seconds:break
    time.sleep(.1)
  print(json.dumps({'label':label,'seconds':row['elapsed'],'channels':[{k:c[k] for k in ('name','caption_index','sample_position','sample_rate') if k in c} for c in row['channels']],'last_caption':row['last_caption']}),flush=True)
if __name__=='__main__':
 p=Probe(sys.argv[1]);mode=sys.argv[2]
 if mode=='command':p.command(sys.argv[3])
 elif mode=='record':p.record(sys.argv[3],float(sys.argv[4]) if len(sys.argv)>4 else 0)
 elif mode=='snap':print(json.dumps(p.snap(),indent=2))
