"""Scripted commands and screenshots restricted to the recorded owned VTMB PID."""
import argparse, ctypes as C, ctypes.wintypes as W, json, struct, sys, time
from pathlib import Path
from PIL import ImageGrab

# Local read-only observer never runs other projects' test runners.
from process_reader import Process, k
from observe import snapshot

u=C.WinDLL('user32',use_last_error=True)
u.SetProcessDPIAware()
u.GetForegroundWindow.restype=W.HWND
u.ShowWindow.argtypes=[W.HWND,C.c_int]
u.SetForegroundWindow.argtypes=[W.HWND]
class KI(C.Structure):
    _fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',C.c_size_t)]
class MI(C.Structure):
    _fields_=[('dx',W.LONG),('dy',W.LONG),('data',W.DWORD),('flags',W.DWORD),('time',W.DWORD),('extra',C.c_size_t)]
class Union(C.Union):_fields_=[('ki',KI),('mi',MI)]
class INPUT(C.Structure):_fields_=[('kind',W.DWORD),('value',Union)]
u.SendInput.argtypes=[W.UINT,C.POINTER(INPUT),C.c_int]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('session');ap.add_argument('--command',action='append',default=[])
    ap.add_argument('--seconds',type=float,default=0);ap.add_argument('--label',default='capture')
    a=ap.parse_args();s=Path(a.session);owned=json.loads((s/'process.json').read_text(encoding='utf-8-sig'));p=Process(owned['Id'])
    ft=[W.FILETIME() for _ in range(4)];k.GetProcessTimes.argtypes=[W.HANDLE]+[C.POINTER(W.FILETIME)]*4
    assert k.GetProcessTimes(p.h,*[C.byref(t) for t in ft])
    assert ((ft[0].dwHighDateTime<<32)|ft[0].dwLowDateTime)+504911232000000000==owned['Ticks']
    hwnd=p.window();u.ShowWindow(hwnd,9);u.SetForegroundWindow(hwnd);time.sleep(.5)
    def focus():
        if u.GetForegroundWindow()!=hwnd:raise RuntimeError('Owned game lost foreground')
    def send(scan,flags):
        ev=INPUT(1,Union(ki=KI(0,scan,flags,0,0)))
        if u.SendInput(1,C.byref(ev),C.sizeof(ev))!=1:raise C.WinError(C.get_last_error())
    def key(scan):
        focus()
        try:send(scan,8);time.sleep(.06)
        finally:send(scan,10)
        time.sleep(.08)
    def visible():
        e=p.modules['engine.dll'];dlg=p.u(p.u(e+0x13064a8)+8);vp=p.u(dlg+4)
        return bool(p.read(vp+0x42,1)[0])
    for cmd in a.command:
        if not visible():key(0x29);time.sleep(.5)
        focus()
        try:send(0x1d,8);key(0x1e)
        finally:send(0x1d,10)
        key(0x0e)
        for ch in cmd:
            focus()
            try:send(ord(ch),4);time.sleep(.008)
            finally:send(ord(ch),6)
        key(0x1c);time.sleep(.5)
        with (s/'commands.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'wall':time.time(),'command':cmd})+'\n')
    if visible():key(0x29);time.sleep(.5)
    dest=s/a.label;dest.mkdir(exist_ok=True)
    start=time.monotonic();count=0
    while True:
        focus();row=snapshot(p);row['elapsed']=time.monotonic()-start
        row['last_caption']=p.read(p.modules['engine.dll']+0x1306a40,2048).split(b'\0',1)[0].decode('cp1252','replace')
        c=p.modules['client.dll'];row['client_mode']=p.u(c+0x5f99d8);row['chat']=p.u(c+0x4cef90)
        row['background_branch']=p.read(c+0xf1ae5,6).hex();row['cinematic_fade']=p.f(c+0x5fbf38+0x450)
        if row['chat']:
            row['chat_raw']=p.read(row['chat'],0xa0).hex()
            row['chat_lines']=[]
            for i in range(6):
                ptr=p.u(row['chat']+0x68+4*i)
                entry={'ptr':ptr,'raw':p.read(ptr,0xdc).hex()} if ptr else None
                if entry:
                    vp=p.u(ptr+4);entry['bounds']=struct.unpack('<4h',p.read(vp+0x34,8));entry['visible']=p.read(vp+0x42,1)[0]
                    for off in (0x78,0x7c,0x84,0x88):
                        address=p.u(ptr+off)
                        if address:
                            try:
                                text=p.read(address,512).decode('utf-16-le','replace').split('\0',1)[0]
                                if text and all(ord(ch)>=32 or ch in '\n\r\t' for ch in text):entry['text_'+hex(off)]=text
                            except OSError:pass
                row['chat_lines'].append(entry)
        with (dest/'observations.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
        ImageGrab.grab().save(dest/('%03d.png'%count));count+=1
        if time.monotonic()-start>=a.seconds:break
        time.sleep(.8)
    print(json.dumps({'frames':count,'elapsed':time.monotonic()-start,'pid':p.pid}))
if __name__=='__main__':main()
