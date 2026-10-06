"""Finite execution of an owned process tree; never enumerate/kill by name.

Windows starts the root suspended and assigns it to an unnamed kill-on-close
Job Object before its first instruction, so early-spawned children cannot
escape assignment. POSIX uses a new process group for synthetic regressions.
"""
import os
import signal
import subprocess


class _WindowsJob:
    def __init__(self):
        import ctypes as C
        from ctypes import wintypes as W
        self.C = C
        self.kernel = k = C.WinDLL('kernel32', use_last_error=True)

        class BasicLimits(C.Structure):
            _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64),
                        ('flags', W.DWORD), ('minimum_working_set', C.c_size_t),
                        ('maximum_working_set', C.c_size_t), ('active_process_limit', W.DWORD),
                        ('affinity', C.c_size_t), ('priority', W.DWORD), ('scheduling', W.DWORD)]

        class IOCounters(C.Structure):
            _fields_ = [(name, C.c_uint64) for name in
                        ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]

        class ExtendedLimits(C.Structure):
            _fields_ = [('basic', BasicLimits), ('io', IOCounters),
                        ('process_memory', C.c_size_t), ('job_memory', C.c_size_t),
                        ('peak_process_memory', C.c_size_t), ('peak_job_memory', C.c_size_t)]

        class ThreadEntry(C.Structure):
            _fields_ = [('size', W.DWORD), ('usage', W.DWORD), ('thread_id', W.DWORD),
                        ('process_id', W.DWORD), ('base_priority', W.LONG),
                        ('delta_priority', W.LONG), ('flags', W.DWORD)]

        self.ThreadEntry = ThreadEntry
        signatures = {
            'CreateJobObjectW': ([W.LPVOID, W.LPCWSTR], W.HANDLE),
            'SetInformationJobObject': ([W.HANDLE, C.c_int, W.LPVOID, W.DWORD], W.BOOL),
            'AssignProcessToJobObject': ([W.HANDLE, W.HANDLE], W.BOOL),
            'TerminateJobObject': ([W.HANDLE, W.UINT], W.BOOL),
            'OpenProcess': ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            'CreateToolhelp32Snapshot': ([W.DWORD, W.DWORD], W.HANDLE),
            'Thread32First': ([W.HANDLE, C.POINTER(ThreadEntry)], W.BOOL),
            'Thread32Next': ([W.HANDLE, C.POINTER(ThreadEntry)], W.BOOL),
            'OpenThread': ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            'ResumeThread': ([W.HANDLE], W.DWORD),
            'CloseHandle': ([W.HANDLE], W.BOOL),
        }
        for name, (args, result) in signatures.items():
            api = getattr(k, name)
            api.argtypes, api.restype = args, result
        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(self.handle, 9, C.byref(limits), C.sizeof(limits)):
            error = C.WinError(C.get_last_error())
            self.close()
            raise error

    def assign_and_resume(self, process):
        C, k = self.C, self.kernel
        # AssignProcess requires PROCESS_SET_QUOTA | PROCESS_TERMINATE.
        handle = k.OpenProcess(0x0100 | 0x0001, False, process.pid)
        if not handle:
            raise C.WinError(C.get_last_error())
        try:
            if not k.AssignProcessToJobObject(self.handle, handle):
                raise C.WinError(C.get_last_error())
        finally:
            k.CloseHandle(handle)
        snapshot = k.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
        if snapshot == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        try:
            entry = self.ThreadEntry()
            entry.size = C.sizeof(entry)
            found = k.Thread32First(snapshot, C.byref(entry))
            while found:
                if entry.process_id == process.pid:
                    thread = k.OpenThread(0x0002, False, entry.thread_id)
                    if not thread:
                        raise C.WinError(C.get_last_error())
                    try:
                        if k.ResumeThread(thread) == 0xFFFFFFFF:
                            raise C.WinError(C.get_last_error())
                    finally:
                        k.CloseHandle(thread)
                    return
                found = k.Thread32Next(snapshot, C.byref(entry))
            raise OSError('Suspended owned process has no resumable primary thread')
        finally:
            k.CloseHandle(snapshot)

    def close(self):
        if getattr(self, 'handle', None):
            # This closes only our unnamed job, including its descendants.
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def run(command, *, timeout, env=None, cwd=None):
    """Return CompletedProcess or TimeoutExpired with the collected first output.

    Intended for collectors/finite tools, not a launcher whose game must outlive
    the launcher. Even successful roots cannot leave their descendants running.
    """
    job = _WindowsJob() if os.name == 'nt' else None
    process = None
    closed = False

    def close_tree():
        nonlocal closed
        if closed:
            return
        closed = True
        if job:
            job.close()
        elif process:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    try:
        options = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE,
                   'text': True, 'env': env, 'cwd': cwd}
        if job:
            options['creationflags'] = subprocess.CREATE_NO_WINDOW | 0x00000004  # CREATE_SUSPENDED
        else:
            options['start_new_session'] = True
        process = subprocess.Popen(command, **options)
        if job:
            try:
                job.assign_and_resume(process)
            except BaseException:
                # Assignment failed: the suspended root has executed nothing.
                process.kill()
                close_tree()
                process.communicate(timeout=5)
                raise
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as first_timeout:
            close_tree()
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                # Do not wait without a bound if an OS/pipe failure obstructs drain.
                stdout, stderr = first_timeout.output, first_timeout.stderr
            def text(value):
                return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
            raise subprocess.TimeoutExpired(command, timeout, output=text(stdout), stderr=text(stderr)) from first_timeout
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    finally:
        close_tree()
        if process:
            for stream in (process.stdout, process.stderr):
                if stream:
                    stream.close()
