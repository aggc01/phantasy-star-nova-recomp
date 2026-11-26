#!/usr/bin/env python3
"""Bounded external Windows x64 hot-thread PC sampler."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
import platform
import re
import sys
import time
from typing import Any


if os.name != "nt":
    raise SystemExit("win_cpu_sample.py requires Windows")

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

HANDLE = wintypes.HANDLE
DWORD = wintypes.DWORD
BOOL = wintypes.BOOL
WORD = wintypes.WORD
ULONG_PTR = ctypes.c_size_t


class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", DWORD), ("cntUsage", DWORD), ("th32ThreadID", DWORD),
        ("th32OwnerProcessID", DWORD), ("tpBasePri", ctypes.c_long),
        ("tpDeltaPri", ctypes.c_long), ("dwFlags", DWORD),
    ]


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", DWORD), ("dwHighDateTime", DWORD)]


class MODULEINFO(ctypes.Structure):
    _fields_ = [("lpBaseOfDll", ctypes.c_void_p), ("SizeOfImage", DWORD), ("EntryPoint", ctypes.c_void_p)]


class SYSTEM_INFO_UNION(ctypes.Union):
    _fields_ = [("dwOemId", DWORD), ("w", WORD * 2)]


class SYSTEM_INFO(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("u", SYSTEM_INFO_UNION), ("dwPageSize", DWORD), ("lpMinimumApplicationAddress", ctypes.c_void_p),
                ("lpMaximumApplicationAddress", ctypes.c_void_p), ("dwActiveProcessorMask", ULONG_PTR),
                ("dwNumberOfProcessors", DWORD), ("dwProcessorType", DWORD), ("dwAllocationGranularity", DWORD),
                ("wProcessorLevel", WORD), ("wProcessorRevision", WORD)]


def _prototype(dll: Any, name: str, restype: Any, argtypes: list[Any]) -> Any:
    fn = getattr(dll, name)
    fn.restype = restype
    fn.argtypes = argtypes
    return fn


CreateToolhelp32Snapshot = _prototype(kernel32, "CreateToolhelp32Snapshot", HANDLE, [DWORD, DWORD])
Thread32First = _prototype(kernel32, "Thread32First", BOOL, [HANDLE, ctypes.POINTER(THREADENTRY32)])
Thread32Next = _prototype(kernel32, "Thread32Next", BOOL, [HANDLE, ctypes.POINTER(THREADENTRY32)])
OpenThread = _prototype(kernel32, "OpenThread", HANDLE, [DWORD, BOOL, DWORD])
GetThreadTimes = _prototype(kernel32, "GetThreadTimes", BOOL, [HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)])
SuspendThread = _prototype(kernel32, "SuspendThread", DWORD, [HANDLE])
ResumeThread = _prototype(kernel32, "ResumeThread", DWORD, [HANDLE])
GetThreadContext = _prototype(kernel32, "GetThreadContext", BOOL, [HANDLE, ctypes.c_void_p])
CloseHandle = _prototype(kernel32, "CloseHandle", BOOL, [HANDLE])
SetLastError = _prototype(kernel32, "SetLastError", None, [DWORD])
OpenProcess = _prototype(kernel32, "OpenProcess", HANDLE, [DWORD, BOOL, DWORD])
IsWow64Process2 = _prototype(kernel32, "IsWow64Process2", BOOL, [HANDLE, ctypes.POINTER(WORD), ctypes.POINTER(WORD)])
GetNativeSystemInfo = _prototype(kernel32, "GetNativeSystemInfo", None, [ctypes.POINTER(SYSTEM_INFO)])
EnumProcessModulesEx = _prototype(psapi, "EnumProcessModulesEx", BOOL, [HANDLE, ctypes.POINTER(HANDLE), DWORD, ctypes.POINTER(DWORD), DWORD])
GetModuleInformation = _prototype(psapi, "GetModuleInformation", BOOL, [HANDLE, HANDLE, ctypes.POINTER(MODULEINFO), DWORD])
GetModuleFileNameExW = _prototype(psapi, "GetModuleFileNameExW", DWORD, [HANDLE, HANDLE, wintypes.LPWSTR, DWORD])

TH32CS_SNAPTHREAD = 0x00000004
THREAD_SUSPEND_RESUME = 0x0002
THREAD_GET_CONTEXT = 0x0008
THREAD_QUERY_INFORMATION = 0x0040
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
LIST_MODULES_ALL = 0x03
IMAGE_FILE_MACHINE_UNKNOWN = 0
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_FILE_MACHINE_ARM64 = 0xAA64
CONTEXT_AMD64_CONTROL = 0x00100001
CONTEXT_FLAGS_OFFSET = 48
CONTEXT_RIP_OFFSET = 248
CONTEXT_BYTES = 1232
LOG_READ_CAP = 64 * 1024
LOG_LINE_CAP = 16 * 1024
TELEMETRY_LINE = re.compile(r"\b(metrics?|gpu[\s_-]*fence|waits?|hitch(?:ed|es)?|frames?)\b", re.IGNORECASE)


def _win_error(action: str) -> OSError:
    code = ctypes.get_last_error()
    return OSError(code, f"{action}: {ctypes.FormatError(code).strip()}")


def _filetime_value(value: FILETIME) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def _thread_cpu(handle: HANDLE) -> int:
    created, exited, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    if not GetThreadTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
        raise _win_error("GetThreadTimes")
    return (_filetime_value(kernel) + _filetime_value(user)) * 100


def _thread_ids(pid: int) -> list[int]:
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snapshot == HANDLE(-1).value:
        raise _win_error("CreateToolhelp32Snapshot")
    ids: list[int] = []
    try:
        entry = THREADENTRY32()
        entry.dwSize = ctypes.sizeof(entry)
        SetLastError(0)
        ok = Thread32First(snapshot, ctypes.byref(entry))
        while ok:
            if entry.th32OwnerProcessID == pid:
                ids.append(int(entry.th32ThreadID))
            SetLastError(0)
            ok = Thread32Next(snapshot, ctypes.byref(entry))
        err = ctypes.get_last_error()
        if err not in (0, 18):  # ERROR_NO_MORE_FILES is normal.
            raise OSError(err, f"Thread32Next: {ctypes.FormatError(err).strip()}")
    finally:
        CloseHandle(snapshot)
    return ids


def _read_rip(thread: HANDLE) -> int:
    raw = ctypes.create_string_buffer(CONTEXT_BYTES + 15)
    aligned = (ctypes.addressof(raw) + 15) & ~15
    ctypes.cast(aligned + CONTEXT_FLAGS_OFFSET, ctypes.POINTER(DWORD))[0] = CONTEXT_AMD64_CONTROL
    if not GetThreadContext(thread, ctypes.c_void_p(aligned)):
        raise _win_error("GetThreadContext")
    return int(ctypes.cast(aligned + CONTEXT_RIP_OFFSET, ctypes.POINTER(ctypes.c_uint64))[0])


def _open_thread(tid: int) -> HANDLE:
    h = OpenThread(THREAD_QUERY_INFORMATION | THREAD_GET_CONTEXT | THREAD_SUSPEND_RESUME, False, tid)
    if not h:
        raise _win_error("OpenThread")
    return h


def _check_architecture(process: HANDLE) -> None:
    if ctypes.sizeof(ctypes.c_void_p) != 8 or platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("Run this helper with 64-bit x86 Python on Windows x64")
    process_machine, native_machine = WORD(), WORD()
    if not IsWow64Process2(process, ctypes.byref(process_machine), ctypes.byref(native_machine)):
        raise _win_error("IsWow64Process2 (Windows 10+ required)")
    if native_machine.value != IMAGE_FILE_MACHINE_AMD64 or process_machine.value != IMAGE_FILE_MACHINE_UNKNOWN:
        raise RuntimeError("Target must be a native x64 process (not WOW64, ARM64, or another architecture)")


def _modules(process: HANDLE) -> list[dict[str, Any]]:
    cap = 256
    while True:
        arr = (HANDLE * cap)()
        needed = DWORD()
        if not EnumProcessModulesEx(process, arr, ctypes.sizeof(arr), ctypes.byref(needed), LIST_MODULES_ALL):
            raise _win_error("EnumProcessModulesEx")
        count = needed.value // ctypes.sizeof(HANDLE)
        if count <= cap:
            break
        cap = count + 32
    modules = []
    for hmod in arr[:count]:
        info = MODULEINFO()
        if not GetModuleInformation(process, hmod, ctypes.byref(info), ctypes.sizeof(info)):
            continue
        pathbuf = ctypes.create_unicode_buffer(32768)
        n = GetModuleFileNameExW(process, hmod, pathbuf, len(pathbuf))
        modules.append({"base": int(info.lpBaseOfDll or 0), "size": int(info.SizeOfImage), "path": pathbuf.value if n else None})
    return modules


class LogTail:
    """Bounded, append-only session.log tail that starts at the current EOF."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.file = open(self.path, "rb")
        self.file.seek(0, os.SEEK_END)
        self.start_offset = self.file.tell()
        self.pending = b""
        self.discarding_long_line = False
        self.dropped_long_lines = 0

    def poll(self) -> list[dict[str, Any]]:
        data = self.pending + self.file.read(LOG_READ_CAP)
        self.pending = b""
        records = []
        while True:
            newline = data.find(b"\n")
            if newline < 0:
                break
            raw_line, data = data[:newline], data[newline + 1:]
            if self.discarding_long_line:
                self.discarding_long_line = False
                self.dropped_long_lines += 1
                continue
            if len(raw_line) > LOG_LINE_CAP:
                self.dropped_long_lines += 1
                continue
            line = raw_line.rstrip(b"\r").decode("utf-8", errors="replace")
            if TELEMETRY_LINE.search(line):
                records.append({"type": "telemetry", "t_monotonic_ns": time.monotonic_ns(),
                                "log_path": self.path, "line": line})
        if self.discarding_long_line:
            # Ignore an overlong unterminated line until its newline arrives.
            pass
        elif len(data) > LOG_LINE_CAP:
            self.discarding_long_line = True
        else:
            self.pending = data
        return records

    def close(self) -> None:
        self.file.close()


def _capture_pc(thread: HANDLE) -> tuple[int | None, str | None]:
    suspended = False
    pc: int | None = None
    error: str | None = None
    try:
        previous = SuspendThread(thread)
        if previous == 0xFFFFFFFF:
            error = str(_win_error("SuspendThread"))
        else:
            suspended = True
            pc = _read_rip(thread)
    except OSError as exc:
        error = str(exc)
    finally:
        if suspended:
            # Always balance our successful suspend, including GetThreadContext failure.
            if ResumeThread(thread) == 0xFFFFFFFF:
                resume_error = str(_win_error("ResumeThread"))
                error = f"{error}; {resume_error}" if error else resume_error
                pc = None
    return pc, error


def run(pid: int, seconds: float, hz: int, out_path: str, log_path: str | None = None) -> int:
    if pid <= 0 or pid == os.getpid():
        raise ValueError("--pid must identify another process; sampling the helper itself is forbidden")
    if not 0.1 <= seconds <= 300:
        raise ValueError("--seconds must be between 0.1 and 300")
    if not 20 <= hz <= 50:
        raise ValueError("--hz must be between 20 and 50")
    utc_start = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    monotonic_ns_origin = time.monotonic_ns()
    process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not process:
        raise _win_error("OpenProcess")
    successes = 0
    errors: dict[str, int] = {}
    previous_cpu: dict[int, int] = {}
    known_threads: list[int] = []
    last_refresh = 0.0
    interval = 1.0 / hz
    start = time.monotonic()
    deadline = start + seconds
    tailer: LogTail | None = None
    try:
        # Establish the EOF cursor before module inventory so appended log lines
        # during setup are retained, without reading the historical log body.
        if log_path:
            tailer = LogTail(log_path)
        _check_architecture(process)
        modules = _modules(process)
        with open(out_path, "w", encoding="utf-8", newline="\n") as out:
            def emit(record: dict[str, Any]) -> None:
                out.write(json.dumps(record, separators=(",", ":")) + "\n")
                out.flush()

            emit({"type": "metadata", "pid": pid, "architecture": "x64", "sample_hz": hz,
                  "duration_seconds": seconds, "modules": modules, "utc_start": utc_start,
                  "monotonic_ns_origin": monotonic_ns_origin,
                  "log_path": tailer.path if tailer else None,
                  "log_start_offset": tailer.start_offset if tailer else None,
                  "note": "PC-only thread samples; modules are a point-in-time PSAPI inventory"})
            while time.monotonic() < deadline:
                now = time.monotonic()
                if now - last_refresh >= 1.0:
                    try:
                        known_threads = _thread_ids(pid)
                    except OSError as exc:
                        errors[str(exc)] = errors.get(str(exc), 0) + 1
                    last_refresh = now
                candidates: list[tuple[int, int, int]] = []
                for tid in known_threads:
                    h = OpenThread(THREAD_QUERY_INFORMATION, False, tid)
                    if not h:
                        message = str(_win_error(f"OpenThread({tid})"))
                        errors[message] = errors.get(message, 0) + 1
                        continue
                    try:
                        cpu = _thread_cpu(h)
                    except OSError as exc:
                        errors[str(exc)] = errors.get(str(exc), 0) + 1
                        continue
                    finally:
                        CloseHandle(h)
                    prior = previous_cpu.get(tid)
                    previous_cpu[tid] = cpu
                    if prior is not None and cpu > prior:
                        candidates.append((cpu - prior, tid, cpu))
                for cpu_delta, tid, cpu_total in sorted(candidates, reverse=True)[:4]:
                    h = None
                    try:
                        h = _open_thread(tid)
                        pc, error = _capture_pc(h)
                        if error:
                            errors[error] = errors.get(error, 0) + 1
                        if pc is not None:
                            emit({"type": "sample", "t_monotonic_ns": time.monotonic_ns(), "tid": tid,
                                  "pc": f"0x{pc:016x}", "cpu_delta_ns": cpu_delta, "cpu_total_ns": cpu_total})
                            successes += 1
                    except OSError as exc:
                        errors[str(exc)] = errors.get(str(exc), 0) + 1
                    finally:
                        if h:
                            CloseHandle(h)
                if tailer:
                    for record in tailer.poll():
                        emit(record)
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(interval, remaining))
            if tailer:
                for record in tailer.poll():
                    emit(record)
            emit({"type": "summary", "successful_samples": successes, "errors": errors,
                  "elapsed_seconds": time.monotonic() - start,
                  "dropped_oversize_log_lines": tailer.dropped_long_lines if tailer else 0})
        return 0 if successes else 2
    finally:
        if tailer:
            tailer.close()
        CloseHandle(process)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", required=True, type=int, help="PID of an explicitly selected native x64 target process")
    parser.add_argument("--seconds", type=float, default=10.0, help="bounded capture duration: 0.1..300 (default 10)")
    parser.add_argument("--hz", type=int, default=30, help="sampling interval rate: 20..50 Hz (default 30)")
    parser.add_argument("--out", required=True, help="JSONL output path")
    parser.add_argument("--log", help="optional session.log to tail from EOF for metrics, GPU fence/wait, hitch, or frame lines")
    args = parser.parse_args()
    try:
        return run(args.pid, args.seconds, args.hz, args.out, args.log)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"win_cpu_sample: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
