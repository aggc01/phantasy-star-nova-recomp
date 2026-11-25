"""Setup attempts and support reports.

Setup records its latest attempt in NovaData\\setup-attempt.json before it validates any input and updates it as it runs. The game
launcher records each start, launch failure and exit in NovaData\\Player\\launch.json. A support report is a ZIP of what those records,
the setup and game logs and a few settings say, with every path, user name, selected source file name and license or credential
value redacted. The ZIP is built from an explicit allowlist: nothing else in NovaData can reach it.
"""

from __future__ import annotations

import ctypes
import io
import json
import os
from pathlib import Path
import platform
import re
import secrets
import socket
import sys
import time
import zipfile

from setup_generations import PROVENANCE, atomic_json, launchable, read_generation, read_json, read_provenance

ATTEMPT = "setup-attempt.json"
REPORT_FORMAT = 1
MAX_LINES = 400
MAX_LINE = 600
STILL_ACTIVE = 259
# the only settings a report carries: graphics and input (runtime/core/settings.h). Everything else in settings.ini stays out.
SETTINGS_ALLOWLIST = ("render_scale", "frame_rate", "sharpen", "aspect", "post_aa", "anisotropy", "fullscreen", "full_res_world",
                      "shadow_filter", "ssao", "input_mode", "mouse_look", "raw_look", "gyro", "save_dialog", "hud_layout",
                      "aspect_ratio", "osd")
# the only fields of the setup attempt, the launch records and the update state a report carries
ATTEMPT_FIELDS = ("attempt_id", "kind", "started", "updated", "stage", "stages", "outcome", "exit_code", "generation",
                  "target_release", "message")
LAUNCH_FIELDS = ("state", "build", "started", "ended", "pid", "exit_code", "message")
UPDATE_FIELDS = ("highest_release", "last_attempt", "last_result", "last_error", "available_release", "available_version")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def process_alive(pid) -> bool:
    if not isinstance(pid, int) or pid <= 0 or os.name != "nt":
        return False
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = ctypes.c_uint32()
        return bool(kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))) and code.value == STILL_ACTIVE
    finally:
        kernel.CloseHandle(ctypes.c_void_p(handle))


class Attempt:
    """The latest setup attempt, written through to disk at every change so a killed setup still leaves its record."""

    def __init__(self, data: Path, kind: str, private_names=(), private_paths=()):
        self.path = data / ATTEMPT
        self.record = {"schema": 1, "attempt_id": secrets.token_hex(4), "kind": kind, "started": now_iso(), "updated": now_iso(),
                       "pid": os.getpid(), "stage": "checking the selected files", "stages": [], "outcome": "running",
                       "exit_code": None, "generation": None, "target_release": None, "message": "", "lines": [],
                       "private_names": sorted({str(n) for n in private_names if n}),
                       "private_paths": sorted({str(p) for p in private_paths if p})}
        self._write()

    def _write(self) -> None:
        self.record["updated"] = now_iso()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(self.path, self.record)
        except OSError:
            pass          # a record that cannot be written must never stop setup

    def line(self, text: str) -> None:
        lines = self.record["lines"]
        lines.append(f"{time.strftime('%H:%M:%S')} {str(text)[:MAX_LINE]}")
        del lines[:-MAX_LINES]
        self._write()

    def stage(self, name: str) -> None:
        stages = self.record["stages"]
        if stages and "end" not in stages[-1]:
            stages[-1]["end"] = now_iso()
        stages.append({"name": name, "start": now_iso()})
        self.record["stage"] = name
        self._write()

    def set(self, **fields) -> None:
        self.record.update(fields)
        self._write()

    def private(self, *names, paths=()) -> None:
        """Names (and full paths) of the files the player selected: the report replaces them, as whole strings."""
        self.record["private_names"] = sorted(set(self.record["private_names"]) | {str(n) for n in names if n})
        self.record["private_paths"] = sorted(set(self.record.get("private_paths", [])) | {str(p) for p in paths if p})
        self._write()

    def finish(self, outcome: str, exit_code: int, message: str = "") -> None:
        stages = self.record["stages"]
        if stages and "end" not in stages[-1]:
            stages[-1]["end"] = now_iso()
        self.record.update(outcome=outcome, exit_code=exit_code, message=str(message)[:2000])
        self._write()


# ---- redaction

ABSOLUTE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\r\n\"'<>|*?]*")
UNC = re.compile(r"\\\\[^\s\\/\"'<>|*?]+\\[^\r\n\"'<>|*?]*")
CREDENTIAL = re.compile(r"(?i)\b(klicensee|license|licence|password|passwd|secret|token|api[_-]?key|authorization|credential)s?\b"
                        r"(\s*[:=]\s*)(?!<)[^\s,;]+")
BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
HEX32 = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32}(?![0-9A-Fa-f])")


PATH_REST = r"[^\r\n\"'<>|*?]*"


class Redactor:
    def __init__(self, root: Path, private_names=(), private_paths=()):
        # The release folder and NovaData keep their relative part ("<NovaData>\installs\<id>\logs\build.log" is useful and holds
        # nothing private). The user's own folders (home, temp, app data) are replaced together with everything under them.
        entries = []        # (variant, label, keep the rest of the path)
        for path, label, keep in ((root / "NovaData", "<NovaData>", True), (root, "<release>", True), (Path.home(), "<home>", False)):
            for variant in {str(path), str(path).replace("\\", "/"), str(path).replace("\\", "\\\\")}:
                entries.append((variant, label, keep))
        for variable in ("USERPROFILE", "TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "HOMEPATH"):
            value = os.environ.get(variable)
            if value and len(value) > 3:
                for variant in {value, value.replace("\\", "/"), value.replace("\\", "\\\\")}:
                    entries.append((variant, "<path>", False))
        entries.sort(key=lambda entry: len(entry[0]), reverse=True)
        self.entry_labels = [label for _variant, label, _keep in entries]
        parts = [f"(?P<g{i}>{re.escape(variant)}{'' if keep else PATH_REST})" for i, (variant, _l, keep) in enumerate(entries)]
        self.known = re.compile("|".join(parts), re.IGNORECASE) if parts else None
        words = {os.environ.get("USERNAME", ""), os.environ.get("USER", ""), Path.home().name, os.environ.get("COMPUTERNAME", ""),
                 socket.gethostname()}
        self.words = sorted((w for w in words if len(w) >= 3), key=len, reverse=True)
        self.names = sorted((str(n) for n in private_names if n and len(str(n)) >= 3), key=len, reverse=True)
        # The exact paths the player selected are replaced first, as whole strings, so the words after one ("... produced a
        # eboot.bin.elf that differs") survive: the generic path rule below cannot tell where a path with spaces ends.
        selected = {variant for path in private_paths if path and len(str(path)) >= 4
                    for variant in (str(path), str(path).replace("\\", "/"), str(path).replace("\\", "\\\\"))}
        self.selected = (re.compile("|".join(re.escape(v) for v in sorted(selected, key=len, reverse=True)), re.IGNORECASE)
                         if selected else None)

    def __call__(self, text: str) -> str:
        if self.selected:
            text = self.selected.sub("<source-file>", text)
        if self.known:
            text = self.known.sub(lambda m: self.entry_labels[int(m.lastgroup[1:])], text)
        text = ABSOLUTE.sub("<path>", text)          # (a whole path first, so a file name inside it does not leave "<path><source-file>")
        text = UNC.sub("<path>", text)
        for name in self.names:
            text = re.sub(re.escape(name), "<source-file>", text, flags=re.IGNORECASE)
        for word in self.words:
            text = re.sub(rf"(?i)(?<![A-Za-z0-9]){re.escape(word)}(?![A-Za-z0-9])", "<user>", text)
        text = CREDENTIAL.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", text)
        text = BEARER.sub("Bearer <redacted>", text)
        return HEX32.sub("<redacted-hex>", text)

    def leaks(self, text: str) -> list[str]:
        """Anything the redaction should have removed that is still in `text` (used as a check before a report is written)."""
        found = []
        if re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]", text) or UNC.search(text):
            found.append("a drive or network path")
        for word in self.words:
            if re.search(rf"(?i)(?<![A-Za-z0-9]){re.escape(word)}(?![A-Za-z0-9])", text):
                found.append("the user or computer name")
        for name in self.names:
            if name.lower() in text.lower():
                found.append("a selected source file name")
        if HEX32.search(text):
            found.append("a 32-digit hex value")
        return found


# ---- reading the records

def excerpt(text: str, head: int = 40, tail: int = 220, limit: int = 60_000) -> str:
    lines = text.splitlines()
    if len(lines) > head + tail:
        omitted = len(lines) - head - tail
        lines = lines[:head] + [f"... {omitted} lines omitted ..."] + lines[-tail:]
    out = "\n".join(line[:1000] for line in lines)
    return out if len(out) <= limit else "... (earlier text omitted) ...\n" + out[-limit:]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def session_label(launch: dict | None, log_text: str) -> str:
    if not launch:
        return "No game session recorded"
    state = launch.get("state")
    if state == "launch-failed":
        return "Launch failure"
    if state != "exited":
        return "Interrupted or incomplete"
    code = launch.get("exit_code")
    if "== crash:" in log_text or (isinstance(code, int) and (code & 0xFFFFFFFF) >= 0xC0000000):
        return "Crash"
    return "Normal quit" if code == 0 else f"Abnormal exit (code {code})"


def attempt_label(record: dict | None) -> str:
    if not record:
        return "No setup attempt recorded"
    outcome = record.get("outcome")
    if outcome == "running":
        return "In progress" if process_alive(record.get("pid")) else "Interrupted or incomplete"
    if outcome == "success":
        return "Succeeded"
    return f"Failed at stage '{record.get('stage')}'"


def pick(record: dict | None, fields) -> dict:
    return {key: record[key] for key in fields if record and key in record}


def gpu_lines(*logs: str) -> list[str]:
    seen = []
    for text in logs:
        for line in text.splitlines():
            if re.search(r"gpu: vulkan device|gpu: render scale|vulkan.*(version|api)", line, re.IGNORECASE):
                if line.strip() not in seen:
                    seen.append(line.strip())
    return seen[:6]


def windows_text() -> str:
    try:
        v = sys.getwindowsversion()
        return f"Windows {platform.release()} (build {v.build}), {platform.machine()}"
    except AttributeError:
        return platform.platform()


def settings_allowlisted(path: Path) -> list[str]:
    out = []
    for line in read_text(path).splitlines():
        key, equals, value = line.partition("=")
        if equals and key.strip() in SETTINGS_ALLOWLIST:
            out.append(f"{key.strip()} = {value.strip()[:40]}")
    return out


# ---- the export

def release_info(root: Path) -> dict:
    meta = read_json(root / "engine" / "release" / "release.json") or {}
    version = read_text(root / "engine" / "version.txt").strip()
    return {"release": meta.get("release"), "version": meta.get("version") or version, "engine_version": version}


def export_report(root: Path, now: float | None = None) -> Path:
    """Write NovaData\\Reports\\support-<time>.zip and return its path. Raises RuntimeError if a redaction check fails (nothing is
    written then)."""
    data, player = root / "NovaData", root / "NovaData" / "Player"
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    attempt = read_json(data / ATTEMPT)
    redact = Redactor(root, (attempt or {}).get("private_names", []), (attempt or {}).get("private_paths", []))
    launch, previous_launch = read_json(player / "launch.json"), read_json(player / "launch.prev.json")
    session, previous_session = read_text(player / "session.log"), read_text(player / "session.prev.log")
    current, previous = read_generation(data / "current.txt"), read_generation(data / "previous.txt")
    provenance = read_provenance(data, current) if current else None
    ready, why = launchable(data, current)
    updates = read_json(data / "Updates" / "state.json") or {}
    config = read_json(root / "engine" / "release" / "update.json") or {}
    info = release_info(root)

    summary = [
        "Phantasy Star Nova Recomp support report",
        f"Created: {now_iso()} (report format {REPORT_FORMAT})",
        f"Release: version {info['version'] or 'unknown'}, release number {info['release']}",
        f"Windows: {windows_text()}",
    ]
    gpu = gpu_lines(session, previous_session)
    summary += [f"Graphics: {line}" for line in gpu] or ["Graphics: not recorded yet (the game has not run)"]
    summary += ["", "Builds",
                f"  Active build (the one the game launches): {current[:8] if current else 'none'}  "
                + (f"can start: yes" if ready else f"can start: NO - {why}")]
    if provenance:
        summary.append(f"    release {provenance.get('release')}, version {provenance.get('version')}, built {provenance.get('built')}; "
                       f"native {provenance['ids'].get('native', '')[:8]}, text {provenance['ids'].get('text', '')[:8]}, "
                       f"movies {provenance['ids'].get('movies', '')[:8]}")
    elif current:
        summary.append("    built before build records were kept (a successful run of this setup adds them)")
    summary.append(f"  Earlier build (can be rolled back to): {previous[:8] if previous else 'none'}")
    summary += ["", "Latest setup attempt"]
    if attempt:
        label = attempt_label(attempt)
        summary += [f"  {label}: {attempt.get('kind')} started {attempt.get('started')}, stage '{attempt.get('stage')}', "
                    f"exit code {attempt.get('exit_code')}",
                    f"  Build being made: {str(attempt.get('generation') or 'not yet known')[:8]}"
                    + (f", for release {attempt.get('target_release')}" if attempt.get('target_release') else ""),
                    f"  Result: {' | '.join(str(attempt.get('message') or 'none recorded').split(chr(10)))[:300]}"]
        if attempt.get("outcome") != "success" and current:
            summary.append(f"  The game can still be played from build {current[:8]} "
                           + ("(checked: it can start)." if ready else "(WARNING: it cannot start, see above)."))
    else:
        summary.append("  none recorded")
    summary += ["", "Game sessions"]
    for name, record, text in (("Latest", launch, session), ("Earlier", previous_launch, previous_session)):
        label = session_label(record, text)
        extra = f", exit code {record.get('exit_code')}" if record and "exit_code" in record else ""
        summary.append(f"  {name}: {label}" + (f" (build {str(record.get('build'))[:8]}, started {record.get('started')}{extra})" if record else ""))
    summary += ["", "Updates",
                f"  Update checks: {'on' if config.get('enabled') else 'off'}, channel {config.get('channel', 'n/a')}",
                f"  Highest release accepted: {updates.get('highest_release', 'none')}; last check result: {updates.get('last_result', 'never checked')}"]
    summary += ["", "Settings (graphics and input only)"] + [f"  {line}" for line in settings_allowlisted(player / "settings.ini")]
    summary += ["", "What this report holds: the records above, setup and game log excerpts, and the settings listed. Paths, user",
                "names, the names of the files you chose and any license values are replaced with <...> markers.",
                "It holds no saves, game files, packages, licenses, fonts, screenshots or memory dumps. Share it yourself if you choose."]

    members = {"summary.txt": "\n".join(summary) + "\n"}
    members["summary.json"] = json.dumps({
        "format": REPORT_FORMAT, "created": now_iso(), "release": info, "active_build": current, "previous_build": previous,
        "active_can_start": ready, "setup_attempt": pick(attempt, ATTEMPT_FIELDS) | {"label": attempt_label(attempt)},
        "latest_session": pick(launch, LAUNCH_FIELDS) | {"label": session_label(launch, session)},
        "earlier_session": pick(previous_launch, LAUNCH_FIELDS) | {"label": session_label(previous_launch, previous_session)},
        "updates": pick(updates, UPDATE_FIELDS), "graphics": gpu,
        "settings": settings_allowlisted(player / "settings.ini")}, indent=2, sort_keys=True, default=str) + "\n"
    if attempt:
        members["setup/attempt.txt"] = "\n".join((attempt.get("lines") or [])[-MAX_LINES:]) + "\n"
        generation = attempt.get("generation")
        logs = data / "installs" / generation / "logs" if generation else None
        if logs and logs.is_dir():
            for log in sorted(logs.glob("*.log"))[:20]:
                members[f"setup/logs/{log.name}"] = excerpt(read_text(log), head=10, tail=60, limit=12_000) + "\n"
    if session:
        members["game/session.log"] = excerpt(session) + "\n"
    if previous_session:
        members["game/session.prev.log"] = excerpt(previous_session) + "\n"

    out = {}
    for name, text in members.items():
        clean = redact(text)
        problems = redact.leaks(clean)
        if problems:
            raise RuntimeError(f"The report was not written: {name} still held {', '.join(sorted(set(problems)))} after redaction.")
        out[name] = clean
    folder = data / "Reports"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"support-{stamp}.zip"
    n = 1
    while path.exists():
        n += 1
        path = folder / f"support-{stamp}-{n}.zip"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in out.items():
            entry = zipfile.ZipInfo(name, time.localtime(now)[:6] if now else time.localtime()[:6])
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, text.encode("utf-8"))
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(buffer.getvalue())
    temporary.replace(path)
    return path
