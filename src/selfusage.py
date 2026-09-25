"""How much this program itself uses: CPU % and RAM (MB), straight from Windows (no installs)."""
import ctypes
import os
import time
from ctypes import wintypes

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.GetCurrentProcess.restype = wintypes.HANDLE
_k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4


class _MemCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


_k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MemCounters), wintypes.DWORD]


class SelfUsage:
    """Call sample() every few seconds: -> (cpu percent of the whole PC or None on the first call, RAM in MB)."""

    def __init__(self):
        self.h = _k32.GetCurrentProcess()
        self.cpus = os.cpu_count() or 1
        self.last = None

    def _cpu_seconds(self):
        t = [wintypes.FILETIME() for _ in range(4)]
        _k32.GetProcessTimes(self.h, *[ctypes.byref(x) for x in t])
        kernel, user = t[2], t[3]
        return ((kernel.dwHighDateTime << 32 | kernel.dwLowDateTime)
                + (user.dwHighDateTime << 32 | user.dwLowDateTime)) / 1e7

    def sample(self):
        now, busy = time.perf_counter(), self._cpu_seconds()
        cpu = None
        if self.last:
            dt = now - self.last[0]
            if dt > 0:
                cpu = max(0.0, (busy - self.last[1]) / dt / self.cpus * 100)
        self.last = (now, busy)
        mc = _MemCounters()
        mc.cb = ctypes.sizeof(mc)
        ram = mc.WorkingSetSize / 1048576 if _k32.K32GetProcessMemoryInfo(self.h, ctypes.byref(mc), mc.cb) else None
        return cpu, ram
