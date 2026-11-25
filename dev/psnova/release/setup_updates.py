"""In-place updates: the signed feed, its verification, and the update components Setup stages under NovaData\\Updates.

An update is a signed manifest (manifest.json + manifest.sig, Ed25519 over the manifest bytes with a pinned public key) and up to
three component payloads: engine (the build sources), text (English text recipes and builder) and movies (English subtitle
recipes and builder). Each payload is a ZIP whose SHA-256 and size the manifest names. Nothing is extracted or run before the
signature and the payload hash verify. The root launchers, the verifier, the bundled Python and the toolchain are not
components: changing them takes a new release download.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import time
from urllib.parse import urlsplit
import sys
import urllib.request
import urllib.error
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent / "engine" / "decrypt"))
from Crypto.Signature import eddsa  # noqa: E402 (the bundled PyCryptodome: the Ed25519 verifier)

from setup_generations import atomic_json, read_json, remove_tree, sha256_file

UPDATER_VERSION = 1
APP_ID = "phantasy-star-nova-recomp"
SIGN_PREFIX = b"nova-update-manifest-v1\n"
CHECK_INTERVAL = 24 * 3600
ENGINE_DIRS = ("decrypt", "dev", "packs", "pipeline", "recompiler", "runtime", "third_party")
KINDS = ("engine", "text", "movies")
COMPONENT_FILES = {"engine": (), "text": ("build_text.py",), "movies": ("build_movies.py",)}
COMPONENT_DIRS = {"engine": ENGINE_DIRS, "text": ("text",), "movies": ("movies",)}
REBUILD = {"engine": "full", "text": "english-text", "movies": "english-movies"}
MAX_MANIFEST = 256 * 1024
MAX_PAYLOAD = 2 * 1024**3
MAX_UNPACKED = 3 * 1024**3
MAX_FILES = 40000
PAYLOAD_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}\.zip")


class UpdateError(Exception):
    """A problem the player can read: the message says what failed and what is untouched."""


# ---- the pinned configuration (engine\release\update.json). The shareable release ships it with updates off.

@dataclass
class Config:
    enabled: bool = False
    feed_url: str = ""
    public_key: bytes = b""
    channel: str = "stable"
    allow_loopback_http: bool = False
    qa: bool = False
    problem: str = ""


def load_config(root: Path) -> Config:
    raw = read_json(root / "engine" / "release" / "update.json")
    if not isinstance(raw, dict):
        return Config(problem="update checks are not configured in this release")
    config = Config(channel=str(raw.get("channel", "stable")), allow_loopback_http=bool(raw.get("allow_loopback_http")),
                    qa=bool(raw.get("qa")))
    if not raw.get("enabled"):
        config.problem = "update checks are off in this release"
        return config
    url, key = str(raw.get("feed_url", "")), str(raw.get("public_key", ""))
    parts = urlsplit(url)
    host = parts.hostname or ""
    loopback = host == "localhost"
    try:
        loopback = loopback or ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    if parts.scheme == "https" and host:
        pass
    elif parts.scheme == "http" and loopback and config.allow_loopback_http:
        pass
    else:
        config.problem = "the update feed address must be https (loopback http is only allowed in test configurations)"
        return config
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        config.problem = "the update trust key is missing or not a 64-digit hex Ed25519 public key"
        return config
    config.enabled, config.feed_url, config.public_key = True, url.rstrip("/") + "/", bytes.fromhex(key)
    return config


# ---- the manifest

def verify_manifest(manifest_bytes: bytes, signature: bytes, config: Config) -> dict:
    """Check the Ed25519 signature with the pinned key, then the manifest's own rules. Raises UpdateError."""
    if len(manifest_bytes) > MAX_MANIFEST:
        raise UpdateError("The update manifest is too large to be genuine, so it was ignored.")
    try:
        key = eddsa.import_public_key(config.public_key)
        eddsa.new(key, "rfc8032").verify(SIGN_PREFIX + manifest_bytes, signature)
    except (ValueError, TypeError):
        raise UpdateError("The update manifest's signature does not match this release's trust key. It was ignored and "
                          "nothing was downloaded.") from None
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except ValueError:
        raise UpdateError("The update manifest is not readable.") from None
    problems = manifest_problems(manifest, config)
    if problems:
        raise UpdateError(f"The update manifest is not valid ({problems}). It was ignored.")
    return manifest


def manifest_problems(manifest, config: Config) -> str:
    if not isinstance(manifest, dict):
        return "not an object"
    if manifest.get("schema") != 1:
        return "unknown schema"
    if manifest.get("app") != APP_ID or manifest.get("channel") != config.channel:
        return "it is for another app or channel"
    release = manifest.get("release")
    if not isinstance(release, int) or isinstance(release, bool) or release < 1:
        return "bad release number"
    for key, limit in (("version", 40), ("published", 40)):
        if not isinstance(manifest.get(key), str) or not 0 < len(manifest[key]) <= limit:
            return f"bad {key}"
    notes = manifest.get("notes")
    if isinstance(notes, list):
        notes = "\n".join(str(n) for n in notes)
    if not isinstance(notes, str) or len(notes) > 8000:
        return "bad notes"
    if not isinstance(manifest.get("min_updater"), int):
        return "bad minimum updater"
    components = manifest.get("components")
    if not isinstance(components, dict) or not components or set(components) - set(KINDS):
        return "bad components"
    for kind, item in components.items():
        if not isinstance(item, dict):
            return f"bad {kind} component"
        if not isinstance(item.get("payload"), str) or not PAYLOAD_NAME.fullmatch(item["payload"]):
            return f"bad {kind} payload name"
        size = item.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= MAX_PAYLOAD:
            return f"bad {kind} size"
        for field_name in ("sha256", "content_sha256"):
            if not isinstance(item.get(field_name), str) or not re.fullmatch(r"[0-9a-f]{64}", item[field_name]):
                return f"bad {kind} {field_name}"
    return ""


# ---- the feed

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http_get(url: str, limit: int, timeout: float = 15.0) -> bytes:
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers={"User-Agent": "NovaRecompUpdater/1"}), timeout=timeout) as response:
            data = response.read(limit + 1)
    except urllib.error.HTTPError as error:
        raise UpdateError(f"The update feed answered {error.code}.") from None
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise UpdateError(f"The update feed could not be reached ({getattr(error, 'reason', error)}). Playing is not affected.") from None
    if len(data) > limit:
        raise UpdateError("The update feed sent more data than expected, so it was ignored.")
    return data


def http_download(url: str, destination: Path, size: int, sha256: str, progress=None, timeout: float = 30.0) -> None:
    """Stream `url` to destination.part, refusing anything past `size`, then check size and SHA-256 before it is renamed."""
    opener = urllib.request.build_opener(_NoRedirect)
    part = destination.with_name(destination.name + ".part")
    digest, done = hashlib.sha256(), 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with opener.open(urllib.request.Request(url, headers={"User-Agent": "NovaRecompUpdater/1"}), timeout=timeout) as response, \
                part.open("wb") as out:
            while chunk := response.read(1024 * 1024):
                done += len(chunk)
                if done > size:
                    raise UpdateError("The download is larger than the signed manifest says, so it was discarded.")
                digest.update(chunk)
                out.write(chunk)
                if progress:
                    progress(done, size)
    except urllib.error.HTTPError as error:
        part.unlink(missing_ok=True)
        raise UpdateError(f"The update feed answered {error.code} for the download.") from None
    except (urllib.error.URLError, OSError, ValueError) as error:
        part.unlink(missing_ok=True)
        raise UpdateError(f"The download stopped ({getattr(error, 'reason', error)}). Nothing was installed; try again.") from None
    except UpdateError:
        part.unlink(missing_ok=True)
        raise
    if done != size or digest.hexdigest() != sha256:
        part.unlink(missing_ok=True)
        raise UpdateError("The downloaded file does not match the signed manifest (its size or SHA-256 differs). It was deleted "
                          "and nothing was installed.")
    part.replace(destination)


def fetch_manifest(config: Config, fetch=http_get) -> tuple[bytes, bytes, dict]:
    base = config.feed_url + config.channel + "/"
    manifest_bytes = fetch(base + "manifest.json", MAX_MANIFEST)
    signature_text = fetch(base + "manifest.sig", 1024).decode("ascii", "replace").strip()
    try:
        signature = bytes.fromhex(signature_text)
    except ValueError:
        raise UpdateError("The update signature is not readable, so the update was ignored.") from None
    return manifest_bytes, signature, verify_manifest(manifest_bytes, signature, config)


# ---- components: the files an update replaces, and the hash that names them

def list_component(kind: str, root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for name in COMPONENT_FILES[kind]:
        if (root / name).is_file():
            files[name] = root / name
    for folder in COMPONENT_DIRS[kind]:
        base = root / folder
        for path in sorted(base.rglob("*")) if base.is_dir() else []:
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files[path.relative_to(root).as_posix()] = path
    return dict(sorted(files.items()))


def tree_sha256(files: dict[str, Path]) -> str:
    digest = hashlib.sha256()
    for relative, path in files.items():
        digest.update(f"{relative}\0{sha256_file(path)}\n".encode())
    return digest.hexdigest()


def component_hash(kind: str, root: Path) -> str:
    return tree_sha256(list_component(kind, root))


def allowed_member(kind: str, name: str) -> bool:
    top = name.split("/", 1)[0]
    return top in COMPONENT_DIRS[kind] if "/" in name else name in COMPONENT_FILES[kind]


def verify_payload(path: Path, size: int, sha256: str) -> None:
    if not path.is_file() or path.stat().st_size != size or sha256_file(path) != sha256:
        raise UpdateError("The downloaded update does not match the signed manifest. It was not unpacked.")


def extract_component(zip_path: Path, kind: str, destination: Path, content_sha256: str, release: int, engine_support: Path | None) -> Path:
    """Unpack a verified payload into `destination` (a new folder). Every member must be a plain file inside the component's
    folders with a Windows-safe name. The unpacked tree must hash to the manifest's content hash. Raises UpdateError."""
    from vitadecrypt.pkg import unsafe_name_reason   # the same Windows-name rules the PKG importer applies
    partial = destination.with_name(destination.name + ".tmp")
    remove_tree(partial)
    partial.mkdir(parents=True)
    total = 0
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
            if len(members) > MAX_FILES:
                raise UpdateError("The update lists far more files than expected, so it was not unpacked.")
            seen = set()
            for member in members:
                name = member.filename
                if member.is_dir():
                    continue
                reason = unsafe_name_reason(name) or ("not a file of this component" if not allowed_member(kind, name) else None)
                if reason or (member.external_attr >> 16) & 0o170000 == 0o120000 or name.lower() in seen:
                    raise UpdateError(f"The update contains a file that is not allowed ({name!r}: {reason or 'link or repeat'}). "
                                      "Nothing was installed.")
                seen.add(name.lower())
                total += member.file_size
                if total > MAX_UNPACKED:
                    raise UpdateError("The update unpacks to more than expected, so it was stopped.")
                target = partial / Path(*name.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out, 1024 * 1024)
        if tree_sha256(list_component(kind, partial)) != content_sha256:
            raise UpdateError("The unpacked update does not match the signed manifest. Nothing was installed.")
        if kind == "engine" and engine_support:
            for name in ("assets", "version.txt"):    # the small files the pipeline reads beside the sources: copied, not updated
                source = engine_support / name
                if source.is_dir():
                    shutil.copytree(source, partial / name)
                elif source.is_file():
                    shutil.copyfile(source, partial / name)
        atomic_json(partial / "component.json", {"kind": kind, "content_sha256": content_sha256, "release": release})
        partial.replace(destination)
    except zipfile.BadZipFile:
        remove_tree(partial)
        raise UpdateError("The downloaded update is not a readable ZIP. Nothing was installed.") from None
    except BaseException:
        remove_tree(partial)
        raise
    return destination


# ---- source sets: where each component's files come from when a generation is built

@dataclass
class SourceSet:
    roots: dict = field(default_factory=dict)       # kind -> folder holding the component (engine: the 7 source folders)
    hashes: dict = field(default_factory=dict)      # kind -> content hash
    origins: dict = field(default_factory=dict)     # kind -> "release" or "update:<16 hex>"
    releases: dict = field(default_factory=dict)    # kind -> the release number those files belong to

    @property
    def release(self) -> int:
        return max(self.releases.values()) if self.releases else 1


def release_number(root: Path) -> int:
    meta = read_json(root / "engine" / "release" / "release.json") or {}
    value = meta.get("release")
    return value if isinstance(value, int) and value >= 1 else 1


def component_dir(data: Path, kind: str, content_sha256: str) -> Path:
    return data / "Updates" / "components" / kind / content_sha256[:16]


def release_sources(root: Path) -> SourceSet:
    """The files that came with the release folder itself."""
    release = release_number(root)
    roots = {"engine": root / "engine", "text": root / "localization", "movies": root / "localization"}
    return SourceSet(roots, {k: component_hash(k, roots[k]) for k in KINDS}, {k: "release" for k in KINDS},
                     {k: release for k in KINDS})


def sources_from_provenance(root: Path, data: Path, provenance: dict | None) -> SourceSet:
    """The sources the active build was made from, so a rebuild (or a rollback) keeps using them: a staged update component is
    used while it is newer than the files in the release folder and still verifies; otherwise the release folder's own files."""
    base = release_sources(root)
    if not provenance:
        return base
    chosen = SourceSet(dict(base.roots), dict(base.hashes), dict(base.origins), dict(base.releases))
    for kind in KINDS:
        record = (provenance.get("sources") or {}).get(kind) or {}
        content = record.get("content")
        origin = str(record.get("origin", "release"))
        if not content or not origin.startswith("update:") or not isinstance(record.get("release"), int):
            continue
        folder = component_dir(data, kind, content)
        meta = read_json(folder / "component.json") or {}
        if (record["release"] > base.releases[kind] and meta.get("content_sha256") == content and folder.is_dir()
                and component_hash(kind, folder) == content):     # (the files are checked again: they are about to be built)
            chosen.roots[kind], chosen.hashes[kind] = folder, content
            chosen.origins[kind], chosen.releases[kind] = origin, record["release"]
    return chosen


def overlay_sources(base: SourceSet, staged: dict, release: int) -> SourceSet:
    """`base` with the staged components (kind -> (folder, content hash)) in place of the same kinds."""
    out = SourceSet(dict(base.roots), dict(base.hashes), dict(base.origins), dict(base.releases))
    for kind, (folder, content) in staged.items():
        out.roots[kind], out.hashes[kind] = folder, content
        out.origins[kind], out.releases[kind] = f"update:{content[:16]}", release
    return out


def collect_components(data: Path, keep: set) -> None:
    """Delete staged component folders that no kept build uses (`keep` is a set of (kind, content[:16]))."""
    root = data / "Updates" / "components"
    for kind_dir in root.iterdir() if root.is_dir() else []:
        for folder in kind_dir.iterdir():
            if folder.is_dir() and (kind_dir.name, folder.name) not in keep:
                remove_tree(folder)


# ---- state: when the feed was last asked, what it offered, the highest release ever accepted

def state_path(data: Path) -> Path:
    return data / "Updates" / "state.json"


def read_state(data: Path) -> dict:
    state = read_json(state_path(data))
    return state if isinstance(state, dict) else {}


def write_state(data: Path, state: dict) -> None:
    state_path(data).parent.mkdir(parents=True, exist_ok=True)
    atomic_json(state_path(data), state)


def accept_release(data: Path, release: int) -> None:
    """Record the highest release this install has taken. It only goes up: rolling back a build does not lower it, so an older
    feed can never be offered again after a newer release was accepted."""
    state = read_state(data)
    if release > state.get("highest_release", 0):
        state["highest_release"] = release
        state["last_result"] = f"release {release} is installed"
        state["last_error"] = ""
        state.pop("available", None)
        for key in ("available_release", "available_version"):
            state.pop(key, None)
        write_state(data, state)


def highest_release(root: Path, data: Path) -> int:
    return max(read_state(data).get("highest_release", 0), release_number(root))


class _CheckLock:
    """Keeps the launcher's quiet check and Setup's check from asking the feed at once."""

    def __init__(self, data: Path):
        self.path = data / "Updates" / "check.lock"

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if time.time() - self.path.stat().st_mtime > 600:
                self.path.unlink()
        except OSError:
            pass
        try:
            os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            self.held = True
        except OSError:
            self.held = False
        return self

    def __exit__(self, *exc):
        if self.held:
            self.path.unlink(missing_ok=True)


# ---- plans and checks

def plan_update(manifest: dict, installed: dict) -> dict:
    """What taking `manifest` would involve, given the content hash of each installed component (kind -> hash)."""
    notes = manifest["notes"]
    changed = [k for k in KINDS if k in manifest["components"] and manifest["components"][k]["content_sha256"] != installed.get(k)]
    rebuild = "none" if not changed else ("full" if "engine" in changed else "+".join(REBUILD[k] for k in changed))
    return {"release": manifest["release"], "version": manifest["version"], "published": manifest["published"],
            "notes": "\n".join(notes) if isinstance(notes, list) else notes, "min_updater": manifest["min_updater"],
            "components": changed, "download_bytes": sum(manifest["components"][k]["size"] for k in changed), "rebuild": rebuild}


def check_for_updates(root: Path, installed: dict, force: bool = False, now: float | None = None, fetch=http_get) -> dict:
    """Ask the feed (at most once a day unless `force`), and record the answer in NovaData\\Updates\\state.json. Never raises: a
    feed that cannot be reached or trusted is recorded as the result. Returns the state."""
    data = root / "NovaData"
    config = load_config(root)
    now = time.time() if now is None else now
    state = read_state(data)
    if not config.enabled:
        return state | {"enabled": False, "last_result": f"off: {config.problem}"}
    if not force and now - state.get("last_attempt", 0) < CHECK_INTERVAL:
        return state | {"enabled": True, "throttled": True}
    with _CheckLock(data) as lock:
        if not lock.held:
            return state | {"enabled": True, "throttled": True}
        state = read_state(data)
        state["last_attempt"] = now
        state.pop("throttled", None)
        try:
            manifest_bytes, signature, manifest = fetch_manifest(config, fetch)
            highest = highest_release(root, data)
            if manifest["release"] <= highest:
                state.update(last_result=f"up to date (feed offers release {manifest['release']}, this install has {highest})",
                             last_error="")
                state.pop("available", None)
            elif manifest["min_updater"] > UPDATER_VERSION:
                state.update(last_result="a newer release needs a new download",
                             last_error="This update needs a newer Setup than this release has. Download the new release.")
                state.pop("available", None)
            else:
                plan = plan_update(manifest, installed)
                state.update(last_result=f"release {manifest['release']} is available", last_error="", available=plan,
                             available_release=manifest["release"], available_version=manifest["version"])
                pending = data / "Updates" / "pending"
                pending.mkdir(parents=True, exist_ok=True)
                (pending / "manifest.json").write_bytes(manifest_bytes)
                (pending / "manifest.sig").write_text(signature.hex() + "\n", encoding="ascii")
        except UpdateError as error:
            state.update(last_result="could not check", last_error=str(error))
        write_state(data, state)
    return state | {"enabled": True}
