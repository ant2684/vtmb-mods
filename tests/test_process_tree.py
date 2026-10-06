"""Owned hanging-child fixtures: bounded termination, first output, isolation."""
import ctypes
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path
from infra.core import Blocked, run


def running(pid):
    if os.name == 'nt':
        from ctypes import wintypes as W
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.OpenProcess.argtypes, k.OpenProcess.restype = [W.DWORD, W.BOOL, W.DWORD], W.HANDLE
        k.WaitForSingleObject.argtypes, k.WaitForSingleObject.restype = [W.HANDLE, W.DWORD], W.DWORD
        k.CloseHandle.argtypes = [W.HANDLE]
        handle = k.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only, no termination access
        if not handle:
            return False
        try:
            return k.WaitForSingleObject(handle, 0) == 258
        finally:
            k.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    stat = Path('/proc') / str(pid) / 'stat'
    return not (stat.exists() and stat.read_text().rsplit(')', 1)[1].split()[0] == 'Z')


class ProcessTreeTests(unittest.TestCase):
    def assert_stopped(self, pid):
        deadline = time.monotonic() + 5
        while running(pid) and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertFalse(running(pid), 'Owned child survived closing its execution scope')

    def test_timeout_kills_hanging_child_retains_output_and_preserves_sibling(self):
        control = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(60)'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            grandchild = "import time;print('grandchild-first-output',flush=True);time.sleep(60)"
            child = ("import subprocess,sys;"
                     f"p=subprocess.Popen([sys.executable,'-B','-c',{grandchild!r}]);"
                     "print('owned-grandchild='+str(p.pid),flush=True);"
                     "print('child-first-output',flush=True);p.wait()")
            fixture = ("import subprocess,sys;"
                       f"p=subprocess.Popen([sys.executable,'-B','-c',{child!r}]);"
                       "print('owned-child='+str(p.pid),flush=True);"
                       "print('root-first-error',file=sys.stderr,flush=True);p.wait()")
            started = time.monotonic()
            with self.assertRaises(Blocked) as caught:
                run([sys.executable, '-B', '-c', fixture], timeout=2, process_tree=True)
            error = caught.exception
            self.assertIn('child-first-output', error.stdout)
            self.assertIn('grandchild-first-output', error.stdout)
            self.assertIn('root-first-error', error.stderr)
            self.assertIn('child-first-output', str(error))
            pid = int(re.search(r'owned-child=(\d+)', error.stdout)[1])
            self.assert_stopped(pid)
            self.assert_stopped(int(re.search(r'owned-grandchild=(\d+)', error.stdout)[1]))
            self.assertIsNone(control.poll(), 'An unrelated control process was terminated')
            self.assertLess(time.monotonic() - started, 10, 'Timeout cleanup was unbounded')
        finally:
            if control.poll() is None:
                control.terminate()
            control.wait(timeout=5)

    def test_successful_root_cannot_leave_detached_child(self):
        fixture = ("import subprocess,sys;"
                   "p=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'],"
                   "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                   "print('owned-child='+str(p.pid),flush=True)")
        output = run([sys.executable, '-B', '-c', fixture], timeout=5, process_tree=True)
        self.assert_stopped(int(re.search(r'owned-child=(\d+)', output)[1]))

    def test_normal_output_and_missing_executable(self):
        self.assertEqual(run([sys.executable, '-B', '-c', "print('complete')"],
                             timeout=5, process_tree=True).strip(), 'complete')
        with self.assertRaises(Blocked):
            run(['vtmb-regression-nonexistent-owned-fixture-executable'], timeout=2, process_tree=True)


if __name__ == '__main__':
    unittest.main()
