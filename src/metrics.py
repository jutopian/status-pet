"""Reads system and per-app resource usage using only Windows built-ins.

CPU / RAM / per-process stats come straight from kernel32 via ctypes.
GPU usage comes from NVML (nvml.dll, ships with the NVIDIA driver); if that
can't be loaded, a single long-running nvidia-smi process is used instead.
Without NVIDIA (AMD / Intel), Windows' own GPU Engine counters (pdh.dll, the
same numbers Task Manager shows) are read instead.
"""
import ctypes
import ctypes.wintypes as wt
import os
import shutil
import subprocess
import threading
import time

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class FILETIME(ctypes.Structure):
    _fields_ = [("lo", wt.DWORD), ("hi", wt.DWORD)]


def _ft(f):
    return (f.hi << 32) | f.lo


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wt.DWORD),
        ("dwMemoryLoad", wt.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


class PROCESS_MEMORY_COUNTERS_EX2(ctypes.Structure):
    """PrivateWorkingSetSize is the "Memory" number Task Manager shows (Win10 1809+)."""
    _fields_ = [
        ("cb", wt.DWORD),
        ("PageFaultCount", wt.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
        ("PrivateWorkingSetSize", ctypes.c_size_t),
        ("SharedCommitUsage", ctypes.c_ulonglong),
    ]


PMC_BASE_SIZE = PROCESS_MEMORY_COUNTERS_EX2.PrivateUsage.offset   # plain PROCESS_MEMORY_COUNTERS


kernel32.GetSystemTimes.argtypes = [ctypes.POINTER(FILETIME)] * 3
kernel32.GetSystemTimes.restype = wt.BOOL
kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
kernel32.GlobalMemoryStatusEx.restype = wt.BOOL
kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wt.BOOL
kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wt.BOOL
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.CloseHandle.restype = wt.BOOL
kernel32.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(FILETIME)] * 4
kernel32.GetProcessTimes.restype = wt.BOOL
kernel32.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX2), wt.DWORD]
kernel32.K32GetProcessMemoryInfo.restype = wt.BOOL


class SystemCpu:
    """Total CPU usage in percent, measured between consecutive sample() calls."""

    def __init__(self):
        self._prev = self._times()

    @staticmethod
    def _times():
        idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
        if not kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        return _ft(idle), _ft(kernel), _ft(user)

    def sample(self):
        cur = self._times()
        prev, self._prev = self._prev, cur
        if cur is None or prev is None:
            return None
        idle = cur[0] - prev[0]
        total = (cur[1] - prev[1]) + (cur[2] - prev[2])  # kernel time includes idle
        if total <= 0:
            return None
        return max(0.0, min(100.0, (total - idle) / total * 100))


def read_ram():
    """Returns (used_gb, total_gb) or None."""
    ms = MEMORYSTATUSEX()
    ms.dwLength = ctypes.sizeof(ms)
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
        return None
    gb = 1024 ** 3
    return (ms.ullTotalPhys - ms.ullAvailPhys) / gb, ms.ullTotalPhys / gb


def _iter_processes():
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE_VALUE:
        return
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            yield entry.th32ProcessID, entry.th32ParentProcessID, entry.szExeFile
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)


class AppMonitor:
    """CPU % and RAM per session for any set of tracked apps, from ONE process snapshot per sample."""

    def __init__(self):
        self._ncpu = os.cpu_count() or 1
        self._prev = {}
        self._prev_t = time.perf_counter()
        self._pmc = PROCESS_MEMORY_COUNTERS_EX2()
        self.exe_names = set()                        # every running exe name (lower case), for "Add running app"

    def sample(self, defs):
        """defs: {app_id: (main prefixes, helper prefixes, merge)} (exe-name prefixes). Each main app is a
        session; helpers belong to the session that started them. merge: a main app started by another copy of
        itself joins that copy's session (multi-process apps). Returns {app_id: [{'cpu', 'ram_gb'}, ...]}
        with sessions oldest first; apps that aren't running are left out."""
        now = time.perf_counter()
        parent, match = {}, {}                        # pid -> parent pid; pid -> (app_id, is_main)
        names = set()
        for pid, ppid, exe in _iter_processes():
            parent[pid] = ppid
            name = exe.lower()
            names.add(name)
            for app, (mains, helpers, _) in defs.items():
                if name.startswith(mains):
                    match[pid] = (app, True)
                    break
                if helpers and name.startswith(helpers):
                    match[pid] = (app, False)
                    break
        self.exe_names = names
        if not match:
            self._prev, self._prev_t = {}, now
            return {}

        root_of = {}
        for pid, (app, is_main) in match.items():
            merge = defs[app][2]
            root, p = pid, (None if is_main and not merge else parent.get(pid))
            for _ in range(8):                        # depth cap also guards against PID loops
                if not p:
                    break
                m = match.get(p)
                if m and m[0] == app:
                    root = p
                    if m[1]:
                        break
                p = parent.get(p)
            root_of[pid] = root

        sessions, new_prev, pmc = {}, {}, self._pmc   # root -> [app, cpu delta, ram bytes, creation time]
        for pid, root in root_of.items():
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
            if not h:
                continue
            s = sessions.setdefault(root, [match[root][0] if root in match else match[pid][0], 0, 0, float("inf")])
            try:
                c, e, k, u = FILETIME(), FILETIME(), FILETIME(), FILETIME()
                if kernel32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
                    t = _ft(k) + _ft(u)
                    new_prev[pid] = t
                    if pid in self._prev:
                        s[1] += t - self._prev[pid]
                    if pid == root:
                        s[3] = _ft(c)
                pmc.cb = ctypes.sizeof(pmc)
                if kernel32.K32GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                    s[2] += pmc.PrivateWorkingSetSize
                else:
                    pmc.cb = PMC_BASE_SIZE
                    if kernel32.K32GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                        s[2] += pmc.WorkingSetSize
            finally:
                kernel32.CloseHandle(h)

        wall = (now - self._prev_t) * 1e7
        scale = 100 / (wall * self._ncpu) if self._prev and wall > 0 else 0.0
        self._prev, self._prev_t = new_prev, now
        out = {}
        for _, s in sorted(sessions.items(), key=lambda kv: (kv[1][3], kv[0])):
            out.setdefault(s[0], []).append({"cpu": max(0.0, min(100.0, s[1] * scale)), "ram_gb": s[2] / 1024 ** 3})
        return out


class _NvmlUtilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _PdhItem(ctypes.Structure):
    # PDH_FMT_COUNTERVALUE_ITEM_W read as a double
    _fields_ = [("name", wt.LPWSTR), ("status", wt.DWORD), ("value", ctypes.c_double)]


class GpuMonitor:
    """GPU usage in percent via sample(); None when no GPU can be read.

    NVML is a direct driver call (well under a millisecond), so it is read on
    demand. The nvidia-smi fallback keeps ONE process running in loop mode and
    reads its output on a background thread, instead of starting a new process
    every poll. Without NVIDIA, Windows GPU Engine counters are read on a
    background thread every `interval` seconds (~2 ms per read).
    If NVIDIA is present it is always used, even next to another GPU.
    nvidia=False skips NVIDIA (for testing the Windows counters).
    """

    PDH_FMT_DOUBLE_NOCAP = 0x200 | 0x8000
    PDH_MORE_DATA = 0x800007D2

    def __init__(self, interval=2.0, nvidia=True):
        self._nvml = self._handle = None
        self._util = _NvmlUtilization()
        self._proc = None
        self._latest = None
        self._stop = threading.Event()
        if not (nvidia and (self._init_nvml() or self._start_smi(interval))):
            threading.Thread(target=self._read_pdh, args=(interval,), daemon=True).start()

    def _init_nvml(self):
        paths = (os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvml.dll"),
                 os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                              "NVIDIA Corporation", "NVSMI", "nvml.dll"))
        for path in paths:
            try:
                lib = ctypes.CDLL(path)
                handle = ctypes.c_void_p()
                if lib.nvmlInit_v2() == 0 and lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle)) == 0:
                    self._nvml, self._handle = lib, handle
                    return True
            except OSError:
                continue
        return False

    def _start_smi(self, interval):
        exe = shutil.which("nvidia-smi")
        if not exe:
            return False
        try:
            self._proc = subprocess.Popen(
                [exe, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits",
                 f"-lms={int(interval * 1000)}"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError:
            return False
        threading.Thread(target=self._read_smi, daemon=True).start()
        return True

    def _read_smi(self):
        for line in self._proc.stdout:
            try:
                self._latest = float(line.split(",")[0])
            except ValueError:
                pass

    def _read_pdh(self, interval):
        """Background loop over the Windows GPU Engine counters. Each instance is one
        process on one engine (3D, Copy, Video...) of one GPU; like Task Manager, the
        processes are summed per engine and the busiest engine is the GPU usage."""
        try:
            pdh = ctypes.WinDLL("pdh")
        except OSError:
            return
        query, counter = wt.HANDLE(), wt.HANDLE()
        if pdh.PdhOpenQueryW(None, 0, ctypes.byref(query)) != 0:
            return
        try:
            if pdh.PdhAddEnglishCounterW(query, r"\GPU Engine(*)\Utilization Percentage",
                                         0, ctypes.byref(counter)) != 0:
                return
            pdh.PdhCollectQueryData(query)  # first read only sets the baseline
            buf = ctypes.create_string_buffer(0)
            size, count = wt.DWORD(), wt.DWORD()
            while not self._stop.wait(interval):
                pdh.PdhCollectQueryData(query)
                size.value = ctypes.sizeof(buf)
                r = pdh.PdhGetFormattedCounterArrayW(counter, self.PDH_FMT_DOUBLE_NOCAP,
                                                     ctypes.byref(size), ctypes.byref(count), buf)
                if (r & 0xFFFFFFFF) == self.PDH_MORE_DATA:  # buffer too small: grow and retry
                    buf = ctypes.create_string_buffer(size.value + 4096)
                    size.value = ctypes.sizeof(buf)
                    r = pdh.PdhGetFormattedCounterArrayW(counter, self.PDH_FMT_DOUBLE_NOCAP,
                                                         ctypes.byref(size), ctypes.byref(count), buf)
                if r != 0:
                    self._latest = None
                    continue
                items = ctypes.cast(buf, ctypes.POINTER(_PdhItem))
                engines = {}
                for i in range(count.value):
                    it = items[i]
                    if it.status in (0, 1):  # PDH_CSTATUS_VALID_DATA / NEW_DATA
                        key = it.name.split("_luid_", 1)[-1]  # drop the process part
                        engines[key] = engines.get(key, 0.0) + it.value
                self._latest = min(100.0, max(engines.values())) if engines else None
        finally:
            pdh.PdhCloseQuery(query)

    def sample(self):
        if self._nvml:
            if self._nvml.nvmlDeviceGetUtilizationRates(self._handle, ctypes.byref(self._util)) == 0:
                return float(self._util.gpu)
            return None
        return self._latest

    def close(self):
        self._stop.set()
        if self._proc:
            self._proc.kill()
        if self._nvml:
            self._nvml.nvmlShutdown()
