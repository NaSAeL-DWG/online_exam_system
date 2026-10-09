"""压测进程和整机资源采样；使用系统 API，不额外安装监控依赖。"""

import asyncio
import ctypes
import os
import platform
import time
from collections import defaultdict
from pathlib import Path


class ResourceSampler:
    def __init__(self):
        self.phase = "provision"
        self.processes = {}
        self.samples = []
        self.stopped = asyncio.Event()
        self.previous = None
        self.started = time.perf_counter()
        self.cpu_name = platform.processor()
        if os.name == "nt":
            import winreg
            from ctypes import wintypes

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            ) as key:
                self.cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self.kernel.OpenProcess.restype = wintypes.HANDLE
            self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
                ctypes.POINTER(wintypes.FILETIME)
            ] * 4
            self.kernel.GetSystemTimes.argtypes = [ctypes.POINTER(wintypes.FILETIME)] * 3
            self.kernel.K32GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            self.kernel.GlobalMemoryStatusEx.argtypes = [ctypes.c_void_p]
            self.kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
            self.kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
            self.kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
            self.kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]

    def windows_process_trees(self):
        """Windows venv 可保留启动器，必须合并它实际运行的 Python 子进程。"""

        from ctypes import wintypes

        class Entry(ctypes.Structure):
            _fields_ = [
                ("size", wintypes.DWORD),
                ("usage", wintypes.DWORD),
                ("pid", wintypes.DWORD),
                ("heap", ctypes.c_size_t),
                ("module", wintypes.DWORD),
                ("threads", wintypes.DWORD),
                ("parent", wintypes.DWORD),
                ("priority", wintypes.LONG),
                ("flags", wintypes.DWORD),
                ("executable", wintypes.WCHAR * 260),
            ]

        snapshot = self.kernel.CreateToolhelp32Snapshot(2, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise OSError("PROCESS_TREE_SAMPLING_FAILED")
        parents = {}
        try:
            entry = Entry()
            entry.size = ctypes.sizeof(entry)
            found = self.kernel.Process32FirstW(snapshot, ctypes.byref(entry))
            while found:
                parents[entry.pid] = entry.parent
                found = self.kernel.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            self.kernel.CloseHandle(snapshot)
        trees = {}
        for name, process in self.processes.items():
            members = {process.pid}
            while True:
                descendants = {pid for pid, parent in parents.items() if parent in members}
                if descendants.issubset(members):
                    break
                members.update(descendants)
            trees[name] = members
        return trees

    def read(self):
        if os.name != "nt":
            return self.read_proc()
        from ctypes import wintypes

        class Memory(ctypes.Structure):
            _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                (name, ctypes.c_ulonglong)
                for name in (
                    "total",
                    "available",
                    "total_page",
                    "available_page",
                    "total_virtual",
                    "available_virtual",
                    "extended",
                )
            ]

        class ProcessMemory(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("page_faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "peak_rss",
                    "rss",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ]

        def seconds(value):
            return ((value.dwHighDateTime << 32) | value.dwLowDateTime) / 10_000_000

        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        if not self.kernel.GlobalMemoryStatusEx(ctypes.byref(memory)):
            raise OSError("MEMORY_SAMPLING_FAILED")
        idle, kernel, user = [wintypes.FILETIME() for _ in range(3)]
        if not self.kernel.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        ):
            raise OSError("CPU_SAMPLING_FAILED")
        result = {
            "time": time.perf_counter(),
            "physical_memory_bytes": memory.total,
            "available_memory_bytes": memory.available,
            "system_cpu_total": seconds(kernel) + seconds(user),
            "system_cpu_idle": seconds(idle),
        }
        for name, members in self.windows_process_trees().items():
            result[f"{name}_cpu_seconds"] = 0
            result[f"{name}_rss_bytes"] = 0
            observed = []
            for pid in members:
                handle = self.kernel.OpenProcess(0x1000 | 0x10, False, pid)
                if not handle:
                    continue
                try:
                    observed.append(pid)
                    times = [wintypes.FILETIME() for _ in range(4)]
                    pm = ProcessMemory()
                    pm.cb = ctypes.sizeof(pm)
                    if self.kernel.GetProcessTimes(
                        handle, *(ctypes.byref(value) for value in times)
                    ):
                        result[f"{name}_cpu_seconds"] += seconds(times[2]) + seconds(times[3])
                    if self.kernel.K32GetProcessMemoryInfo(
                        handle, ctypes.byref(pm), ctypes.sizeof(pm)
                    ):
                        result[f"{name}_rss_bytes"] += pm.rss
                finally:
                    self.kernel.CloseHandle(handle)
            result[f"{name}_process_tree_pids"] = sorted(observed)
        return result

    def read_proc(self):
        """Linux 重跑时按 /proc 的公开系统计数采样。"""

        fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        ticks = [int(value) for value in fields]
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            name, value = line.split(":", 1)
            mem[name] = int(value.strip().split()[0]) * 1024
        result = {
            "time": time.perf_counter(),
            "physical_memory_bytes": mem["MemTotal"],
            "available_memory_bytes": mem["MemAvailable"],
            "system_cpu_total": sum(ticks[:8]),
            "system_cpu_idle": ticks[3] + ticks[4],
        }
        for name, process in self.processes.items():
            path = Path(f"/proc/{process.pid}/stat")
            if not path.exists():
                continue
            values = path.read_text().rsplit(")", 1)[1].split()
            result[f"{name}_cpu_seconds"] = (int(values[11]) + int(values[12])) / os.sysconf(
                "SC_CLK_TCK"
            )
            result[f"{name}_rss_bytes"] = int(values[21]) * os.sysconf("SC_PAGE_SIZE")
        return result

    async def run(self):
        while not self.stopped.is_set():
            raw = self.read()
            sample = {key: value for key, value in raw.items() if not key.endswith("cpu_seconds")}
            sample["phase"] = self.phase
            sample["elapsed_seconds"] = round(raw["time"] - self.started, 3)
            if self.previous:
                delta = raw["time"] - self.previous["time"]
                total = raw["system_cpu_total"] - self.previous["system_cpu_total"]
                idle = raw["system_cpu_idle"] - self.previous["system_cpu_idle"]
                sample["system_cpu_percent"] = (
                    round((total - idle) / total * 100, 3) if total else 0
                )
                for name in self.processes:
                    key = f"{name}_cpu_seconds"
                    if key in raw and key in self.previous:
                        sample[f"{name}_cpu_one_core_percent"] = round(
                            max(0, raw[key] - self.previous[key]) / delta * 100, 3
                        )
            self.samples.append(sample)
            self.previous = raw
            try:
                await asyncio.wait_for(self.stopped.wait(), timeout=0.5)
            except TimeoutError:
                pass

    def summary(self):
        phases = defaultdict(list)
        for sample in self.samples:
            phases[sample["phase"]].append(sample)
        result = {}
        for phase, rows in phases.items():
            result[phase] = {"samples": len(rows)}
            for name in ("api", "worker"):
                rss = [row[f"{name}_rss_bytes"] for row in rows if f"{name}_rss_bytes" in row]
                cpu = [
                    row[f"{name}_cpu_one_core_percent"]
                    for row in rows
                    if f"{name}_cpu_one_core_percent" in row
                ]
                if rss:
                    result[phase][f"{name}_rss_peak_bytes"] = max(rss)
                trees = [
                    len(row[f"{name}_process_tree_pids"])
                    for row in rows
                    if f"{name}_process_tree_pids" in row
                ]
                if trees:
                    result[phase][f"{name}_os_process_tree_count_peak"] = max(trees)
                if cpu:
                    result[phase][f"{name}_cpu_one_core_peak_percent"] = max(cpu)
            cpu = [row["system_cpu_percent"] for row in rows if "system_cpu_percent" in row]
            if cpu:
                result[phase]["system_cpu_peak_percent"] = max(cpu)
            result[phase]["available_memory_min_bytes"] = min(
                row["available_memory_bytes"] for row in rows
            )
        return result
