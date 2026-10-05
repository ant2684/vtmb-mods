"""Minimal, read-only Windows process/module reader for local observations."""
import ctypes as C
import ctypes.wintypes as W
import struct
k = C.WinDLL('kernel32', use_last_error=True)
k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k.OpenProcess.restype = W.HANDLE
k.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
k.CloseHandle.argtypes = [W.HANDLE]
k.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
k.CreateToolhelp32Snapshot.restype = W.HANDLE
class MODULE(C.Structure):
    _fields_ = [('dwSize', W.DWORD), ('th32ModuleID', W.DWORD), ('th32ProcessID', W.DWORD),
                ('GlblcntUsage', W.DWORD), ('ProccntUsage', W.DWORD), ('modBaseAddr', C.c_void_p),
                ('modBaseSize', W.DWORD), ('hModule', W.HMODULE), ('szModule', W.WCHAR * 256),
                ('szExePath', W.WCHAR * 260)]
k.Module32FirstW.argtypes = [W.HANDLE, C.POINTER(MODULE)]
k.Module32NextW.argtypes = [W.HANDLE, C.POINTER(MODULE)]
class Process:
    def __init__(self, pid):
        self.pid = pid
        self.h = k.OpenProcess(0x410, False, pid)
        if not self.h: raise C.WinError(C.get_last_error())
        try:
            self.refresh()
            if 'engine.dll' not in self.modules: raise RuntimeError('Engine module unavailable in this user context')
        except Exception:
            k.CloseHandle(self.h)
            raise
    def refresh(self):
        pid = self.pid
        sh = k.CreateToolhelp32Snapshot(0x18, pid)
        if sh == C.c_void_p(-1).value: raise C.WinError(C.get_last_error())
        m = MODULE(); m.dwSize = C.sizeof(m); self.modules = {}
        try:
            ok = k.Module32FirstW(sh, C.byref(m))
            while ok:
                self.modules[m.szModule.lower()] = m.modBaseAddr
                ok = k.Module32NextW(sh, C.byref(m))
        finally: k.CloseHandle(sh)
    def read(self, address, size):
        buf = C.create_string_buffer(size); done = C.c_size_t()
        if not k.ReadProcessMemory(self.h, address, buf, size, C.byref(done)) or done.value != size:
            raise C.WinError(C.get_last_error())
        return buf.raw
    def u(self, a): return struct.unpack('<I', self.read(a, 4))[0]
    def f(self, a): return struct.unpack('<f', self.read(a, 4))[0]
    def d(self, a): return struct.unpack('<d', self.read(a, 8))[0]
