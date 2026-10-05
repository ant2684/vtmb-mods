"""Read-only engine observations; never sends input or writes game memory."""
import ctypes as C
import ctypes.wintypes as W
import json, struct, sys, time
from pathlib import Path
from process_reader import Process
def main_window(self):
    user=C.WinDLL('user32',use_last_error=True)
    found=[]
    cbtype=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    def cb(hwnd,param):
        pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,C.byref(pid))
        if pid.value==self.pid:
            cls=C.create_unicode_buffer(256);user.GetClassNameW(hwnd,cls,256)
            if cls.value=='Valve001':found.append(hwnd)
        return True
    user.EnumWindows(cbtype(cb),0)
    if len(found)!=1:raise RuntimeError('Expected one Valve001 owned game window')
    return found[0]
Process.window=main_window

def snapshot(p):
    e=p.modules['engine.dll']
    out={'wall':time.time(), 'pid':p.pid,'engine_base':hex(e),
         'paused':p.u(e+0x314874),'server_paused':p.u(e+0x12b0758),
         'client_time':p.d(e+0x314890), 'pause_depth':p.u(e+0xb43788),
         'menu_pause_depth':p.u(e+0xb4378c)}
    site=e+0x2d130
    raw=p.read(site,5)
    if raw[0]==0xe8:
        target=site+5+struct.unpack('<i',raw[1:])[0]
        out['pause_target']=hex(target)
        if target!=e+0x3c190:
            code=target-0x300
            if p.read(code,4)==bytes.fromhex('9c608bd8'):
                state=code+9+struct.unpack('<i',p.read(code+12,4))[0]
                out['clock']=dict(zip(['initialized','paused','pauseStart','totalPaused','rawNow','logicalNow'],struct.unpack('<IIdddd',p.read(state,40))))
    return out

if __name__=='__main__':
    pid=int(sys.argv[1]); p=Process(pid)
    if len(sys.argv)==2:
        a=snapshot(p); time.sleep(1); b=snapshot(p)
        print(json.dumps({'before':a,'after':b,'advance':b['client_time']-a['client_time']},indent=2))
    else:
        path=Path(sys.argv[2]); duration=float(sys.argv[3]) if len(sys.argv)>3 else 120
        end=time.monotonic()+duration
        with path.open('a',encoding='utf-8') as f:
            while time.monotonic()<end:
                try: row=snapshot(p)
                except OSError: break
                f.write(json.dumps(row)+'\n');f.flush();time.sleep(.1)
