"""Owned-process input and read-only character observations; no memory writes."""
import ctypes as C, ctypes.wintypes as W, json, struct, sys, time, re
from pathlib import Path
from process_reader import Process, k
from observe import main_window
u=C.WinDLL('user32',use_last_error=True);u.SetProcessDPIAware()
u.GetForegroundWindow.restype=W.HWND
u.SetForegroundWindow.argtypes=[W.HWND];u.ShowWindow.argtypes=[W.HWND,C.c_int]
class KI(C.Structure): _fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',C.c_size_t)]
class MI(C.Structure): _fields_=[('dx',W.LONG),('dy',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',C.c_size_t)]
class U(C.Union): _fields_=[('ki',KI),('mi',MI)]
class INPUT(C.Structure): _fields_=[('kind',W.DWORD),('value',U)]
u.SendInput.argtypes=[W.UINT,C.POINTER(INPUT),C.c_int]
class Driver:
 def __init__(self,session):
  self.session=Path(session);owned=json.loads((self.session/'process.json').read_text(encoding='utf-8-sig'))
  deadline=time.time()+45
  while True:
   try:
    self.p=Process(owned['Id']);self.hwnd=main_window(self.p)
    if self.console():break
    # Console must be initialized, but it may already be closed in a session.
    break
   except (OSError,RuntimeError):
    if hasattr(self,'p'):k.CloseHandle(self.p.h)
    if time.time()>deadline:raise
    time.sleep(.3)
  ts=[W.FILETIME() for _ in range(4)];k.GetProcessTimes.argtypes=[W.HANDLE]+[C.POINTER(W.FILETIME)]*4
  assert k.GetProcessTimes(self.p.h,*[C.byref(t) for t in ts])
  assert ((ts[0].dwHighDateTime<<32)|ts[0].dwLowDateTime)+504911232000000000==owned['Ticks']
  u.ShowWindow(self.hwnd,9);u.SetForegroundWindow(self.hwnd);time.sleep(.3)
  self.click_delay=.5
 def focus(self):
  pid=W.DWORD();u.GetWindowThreadProcessId(self.hwnd,C.byref(pid))
  if pid.value!=self.p.pid or u.GetForegroundWindow()!=self.hwnd:raise RuntimeError('Owned game not foreground')
 def send(self,ev,check=True):
  if check:self.focus()
  if u.SendInput(1,C.byref(ev),C.sizeof(ev))!=1:raise C.WinError(C.get_last_error())
 def key(self,vk):
  ev=INPUT(1,U(ki=KI(0,u.MapVirtualKeyW(vk,0),8,0,0)))
  try:self.send(ev);time.sleep(.05)
  finally:ev.value.ki.flags=10;self.send(ev,False)
  time.sleep(.07)
 def console(self):
  e=self.p.modules['engine.dll'];obj=self.p.u(e+0x13064a8)
  return bool(self.p.read(self.p.u(self.p.u(obj+8)+4)+0x42,1)[0])
 def command(self,text,delay=.4):
  if not re.fullmatch(r'[A-Za-z0-9_ .;"/+-]+',text):raise ValueError(text)
  if not self.console():self.key(0xc0);time.sleep(.3)
  if not self.console():raise RuntimeError('Native console did not open; command was not sent')
  ev=INPUT(1,U(ki=KI(0,0x1d,8,0,0)))
  try:self.send(ev);self.key(0x41)
  finally:ev.value.ki.flags=10;self.send(ev,False)
  self.key(0x08)
  for ch in text:
   ev=INPUT(1,U(ki=KI(0,ord(ch),4,0,0)))
   try:self.send(ev);time.sleep(.008)
   finally:ev.value.ki.flags=6;self.send(ev,False)
  self.key(0x0d);time.sleep(delay)
  with (self.session/'commands.jsonl').open('a') as f:f.write(json.dumps({'command':text,'wall':time.time()})+'\n')
 def click(self,x,y,delay=None):
  self.focus();rect=W.RECT();u.GetWindowRect(self.hwnd,C.byref(rect))
  if not rect.left<=x<rect.right or not rect.top<=y<rect.bottom:raise ValueError('Click outside owned window')
  u.SetCursorPos(x,y);time.sleep(.05)
  try:self.send(INPUT(0,U(mi=MI(0,0,0,2,0,0))));time.sleep(.05)
  finally:self.send(INPUT(0,U(mi=MI(0,0,0,4,0,0))),False)
  time.sleep(self.click_delay if delay is None else delay)
 def string(self,a,n=128):
  if not a:return ''
  try:return self.p.read(a,n).split(b'\0')[0].decode('cp1252','replace')
  except OSError:return '<unreadable>'
 def snap(self,effective=False):
  p=self.p;row={'wall':time.time(),'pid':p.pid,'modules':p.modules,'console':self.console(),'players':[]}
  if 'vampire.dll' not in p.modules:return row
  v=p.modules['vampire.dll'];table=p.u(v+0x566458)
  if not table:return row
  data=p.read(table,8192*12)
  row['occupied_entity_slots']=sum(1 for idx in range(8192) if struct.unpack_from('<I',data,idx*12+4)[0])
  for idx in range(8192):
   _,a,ser=struct.unpack_from('<III',data,idx*12)
   if not a:continue
   if self.string(p.u(a+0x11c),32)!='player':continue
   pr={'address':a,'index':idx,'serial':ser,'history':struct.unpack('<i',p.read(a+0x13a0,4))[0], 'gender_cached':p.u(a+0x13cc),'model_index':p.u(a+0x2e0), 'groups':[]}
   n=p.u(a+0x13bc);arr=p.u(a+0x13c0)
   if n>32:raise ValueError('Unexpected stat group count')
   for j in range(n):
    g=p.u(arr+j*4);typ=p.u(g+0x10);container=p.u(g+8);values=p.u(container)
    count=p.u(g+4)
    if count>256:raise ValueError(('Unexpected values count',count))
    pr['groups'].append({'address':g,'type':typ,'raw':p.read(g,0x28).hex(),'container_raw':p.read(container,0x18).hex(),'count':count,'values':list(struct.unpack('<'+'i'*count,p.read(values,count*4))),'secondary':list(struct.unpack('<'+'i'*count,p.read(p.u(container+4),count*4)))})
   row['players'].append(pr)
  if effective and row['players']:
   from offline_getter import Getter
   getter=Getter(p)
   for pr in row['players']:
    for group in pr['groups']:
     group['effective']=[getter.effective(group['address'],i) for i in range(group['count'])]
     indices=range(1,10) if group['type']==0 else range(1,13) if group['type']==1 else [i for i,v in enumerate(group['values']) if v>0] if group['type']==2 else []
     group['costs']={str(i):getter.cost(group['address'],group['type'],i,group['values'][i]) for i in indices}
  return row
 def record(self,label,picture=False):
  r=self.snap();(self.session/(label+'.json')).write_text(json.dumps(r,indent=2))
  if picture:
   from PIL import ImageGrab
   self.focus();rect=W.RECT();u.GetWindowRect(self.hwnd,C.byref(rect));ImageGrab.grab(bbox=(rect.left,rect.top,rect.right,rect.bottom)).save(self.session/(label+'.png'))
  print(json.dumps({'label':label,'pid':r['pid'],'console':r['console'],'players':[{'history':p['history'],'gender':p['gender_cached'],'clan':p['groups'][0]['values'][10],'Strength':p['groups'][0]['values'][1],'Experience':p['groups'][0]['values'][34]} for p in r['players']]}),flush=True)
if __name__=='__main__':
 d=Driver(sys.argv[1]);mode=sys.argv[2]
 if mode=='command':d.command(sys.argv[3],float(sys.argv[4]) if len(sys.argv)>4 else .4)
 elif mode=='key':d.key(int(sys.argv[3],0))
 elif mode=='click':d.click(int(sys.argv[3]),int(sys.argv[4]))
 elif mode=='record':d.record(sys.argv[3],len(sys.argv)>4 and sys.argv[4]=='picture')
