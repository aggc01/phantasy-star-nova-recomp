"""Generations: the builds under NovaData\\installs, which one is active, and how one replaces another.

A generation is NovaData\\installs\\<24 hex>. NovaData\\current.txt names the one the game launches and NovaData\\previous.txt
the one before it, kept so the player can roll back. A generation carries provenance.json: the fingerprints it was built
from and the SHA-256 of the files that make it run, so a later build can reuse it only when those files verify.
"""

from __future__ import annotations

import ctypes
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time

GENERATION = re.compile(r"[0-9a-f]{24}")
PROVENANCE = "provenance.json"
PROVENANCE_SCHEMA = 1
TITLE = "PCSG00351"
RECOMP = Path("library/decrypted") / TITLE / "recomp"
MODULES = ("libc.img", "libgxm_es4.img", "libgpu_es4.img", "libscemp4.img", "libsceavplayer.img")
CHUNK = 8 * 1024 * 1024


class GameRunning(Exception):
    pass


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as file:
        file.write(text)
        file.flush()
        os.fsync(file.fileno())
    temporary.replace(path)


def atomic_json(path: Path, value) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_generation(path: Path) -> str | None:
    """The 24-hex id in a current.txt or previous.txt, or None when the file is missing or not an id."""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text if GENERATION.fullmatch(text) else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


# ---- the game lock: the launcher holds NovaData\Player\playing.lock open, sharing nothing, while the game runs

_kernel = ctypes.windll.kernel32 if os.name == "nt" else None
if _kernel:
    _kernel.CreateFileW.restype = ctypes.c_void_p
    _kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                                    ctypes.c_uint32, ctypes.c_void_p]
    _kernel.CloseHandle.argtypes = [ctypes.c_void_p]
INVALID = ctypes.c_void_p(-1).value


@contextmanager
def game_lock(player: Path):
    """Hold the game's lock so the launcher cannot start the game while install state changes. Raises GameRunning if the game
    (or another setup) already holds it."""
    player.mkdir(parents=True, exist_ok=True)
    handle = _kernel.CreateFileW(str(player / "playing.lock"), 0x40000000, 0, None, 4, 0x80, None)   # GENERIC_WRITE, no sharing, OPEN_ALWAYS
    if handle in (None, INVALID):
        raise GameRunning("Phantasy Star Nova is running (or is being updated by another setup). Close the game, then try again. "
                          "The installed game is untouched.")
    try:
        yield
    finally:
        _kernel.CloseHandle(handle)


def game_is_running(player: Path) -> bool:
    try:
        with game_lock(player):
            return False
    except GameRunning:
        return True


# ---- what a generation needs to launch (the launcher's own checks, play_nova.c)

def recomp_dir(data: Path, generation: str) -> Path:
    return data / "installs" / generation / RECOMP


def launchable(data: Path, generation: str | None) -> tuple[bool, str]:
    if not generation:
        return False, "no build is selected"
    base = recomp_dir(data, generation)
    for name in ("game_host.exe", "game.img", "SDL3.dll", *MODULES):
        if not (base / name).is_file():
            return False, f"{name} is missing from build {generation[:8]}"
    entry = base / "entry.txt"
    try:
        if not re.fullmatch(r"[0-9a-f]{1,8}", entry.read_text(encoding="utf-8").strip()):
            return False, f"entry.txt of build {generation[:8]} is not valid"
    except OSError:
        return False, f"entry.txt is missing from build {generation[:8]}"
    return True, "ready"


# ---- provenance

def read_provenance(data: Path, generation: str) -> dict | None:
    record = read_json(data / "installs" / generation / PROVENANCE)
    if not isinstance(record, dict) or record.get("schema") != PROVENANCE_SCHEMA or record.get("generation") != generation:
        return None
    if not all(isinstance(record.get(key), dict) for key in ("ids", "sources", "outputs")):
        return None
    return record


def hash_outputs(base: Path, names) -> dict:
    return {name: sha256_file(base / name) for name in names}


def verify_outputs(base: Path, recorded: dict) -> list[str]:
    """Problems found when the recorded files are checked again: missing, or a different SHA-256."""
    problems = []
    for name, expected in sorted(recorded.items()):
        path = base / name
        if not path.is_file():
            problems.append(f"{name} is missing")
        elif sha256_file(path) != expected:
            problems.append(f"{name} has changed")
    return problems


# ---- copying a generation: independent of the donor, with the donor's own hard links kept as links within the copy

def _on_error(function, path, error):
    os.chmod(path, stat.S_IWRITE)
    function(path)


def remove_tree(path: Path) -> None:
    if path.is_symlink() or path.is_junction():
        os.rmdir(path)
    elif path.exists():
        shutil.rmtree(path, onexc=_on_error)


def tree_bytes(path: Path) -> int:
    """Bytes on disk under `path`, counting each hard-linked file once."""
    seen, total = set(), 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                info = os.stat(os.path.join(root, name))
            except OSError:
                continue
            key = (info.st_dev, info.st_ino)
            if info.st_nlink > 1 and info.st_ino:
                if key in seen:
                    continue
                seen.add(key)
            total += info.st_size
    return total


def copy_tree_independent(source: Path, destination: Path, skip=lambda relative: False, progress=None) -> int:
    """Copy `source` to `destination` as files of their own. Files that were hard-linked together in `source` are linked together
    in the copy (so a 3 GB game archive stays one 3 GB file), but nothing is linked to the donor. Returns the bytes written."""
    linked, written, done = {}, 0, 0
    for root, dirs, files in os.walk(source):
        relative_root = Path(root).relative_to(source)
        dirs[:] = [d for d in dirs if not skip((relative_root / d).as_posix() + "/")]
        (destination / relative_root).mkdir(parents=True, exist_ok=True)
        for name in files:
            relative = (relative_root / name).as_posix()
            if skip(relative):
                continue
            origin, target = Path(root) / name, destination / relative_root / name
            info = origin.stat()
            key = (info.st_dev, info.st_ino) if info.st_nlink > 1 and info.st_ino else None
            if key and key in linked:
                os.link(linked[key], target)
            else:
                shutil.copyfile(origin, target)
                os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns))
                written += info.st_size
                if key:
                    linked[key] = target
            done += 1
            if progress and done % 200 == 0:
                progress(done)
    return written


# ---- the active generation, the one before it, retention, rollback

def generations(data: Path) -> list[str]:
    root = data / "installs"
    return sorted(p.name for p in root.iterdir() if GENERATION.fullmatch(p.name) and p.is_dir()) if root.is_dir() else []


def retain(data: Path, keep: set, report) -> None:
    """Delete every generation except the ones in `keep` (the active one and the previous one). A build that cannot be removed
    (a locked file) is retried the next time."""
    for name in generations(data):
        path = data / "installs" / name
        if name in keep or path.is_symlink() or path.is_junction():
            continue
        report(f"Removing the replaced build {name[:8]}")
        try:
            remove_tree(path)
        except OSError as error:
            report(f"Could not remove the replaced build {name[:8]} ({error}). Setup will try again next time.")


def activate(data: Path, generation: str, report) -> str | None:
    """Make `generation` the one the game launches: previous.txt takes the old current, then current.txt is replaced in one
    atomic step. Returns the build that was active before (now the previous), or None."""
    ok, why = launchable(data, generation)
    if not ok:
        raise RuntimeError(f"The new build cannot be started ({why}); the installed game was not changed.")
    old = read_generation(data / "current.txt")
    if old and old != generation:
        atomic_text(data / "previous.txt", old + "\n")
    atomic_text(data / "current.txt", generation + "\n")
    keep = {generation}
    previous = read_generation(data / "previous.txt")
    if previous:
        keep.add(previous)
    retain(data, keep, report)
    return old if old != generation else read_generation(data / "previous.txt")


def roll_back(data: Path, report) -> tuple[str, str]:
    """Swap the active build and the previous one. Returns (the build now active, the build rolled back from). Raises
    RuntimeError, leaving the game untouched, when there is no previous build or it cannot start."""
    current = read_generation(data / "current.txt")
    previous = read_generation(data / "previous.txt")
    if not previous or previous == current or previous not in generations(data):
        raise RuntimeError("There is no earlier build to go back to.")
    ok, why = launchable(data, previous)
    if not ok:
        raise RuntimeError(f"The earlier build cannot be started ({why}), so it was not selected.")
    atomic_text(data / "current.txt", previous + "\n")
    if current:
        atomic_text(data / "previous.txt", current + "\n")
    report(f"Rolled back to build {previous[:8]}; build {current[:8] if current else '?'} is kept as the earlier build.")
    return previous, current or ""


def wait_for_removal(path: Path, seconds: float = 3.0) -> bool:
    end = time.monotonic() + seconds
    while path.exists() and time.monotonic() < end:
        time.sleep(0.1)
    return not path.exists()
