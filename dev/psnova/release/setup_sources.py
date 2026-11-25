"""Find the Phantasy Star Nova base game, update and license in what the player selected.

The player can give setup a base-game PKG and an update PKG, one ZIP that holds both, or extracted folders. This
module reads each selection's own metadata, decides which package is the 1.00 base and which is the 1.05 update, and
checks the license, all before setup writes anything. It also streams ZIP members to scratch files for the importer.
Nothing here decrypts a game: a PKG's identity comes from its header and an unencrypted file table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import re
import shutil
import struct
import sys
import zipfile
import zlib

ENGINE = Path(__file__).resolve().parent / "engine"
sys.path.insert(0, str(ENGINE / "decrypt"))
from vitadecrypt import pkg as PKG  # noqa: E402
from vitadecrypt import rif as RIF  # noqa: E402
from vitadecrypt import sfo as SFO  # noqa: E402

TITLE = "PCSG00351"
CONTENT = "JP0177-PCSG00351_00-NOVAAPPLICATION0"
BASE_VERSION = "1.00"
UPDATE_VERSION = "1.05"
NAME = "Phantasy Star Nova"
GAME_FIELD = "Game PKG or ZIP"
UPDATE_FIELD = "Update PKG"
LICENSE_FIELD = "Game license"
NoNpDrm_AID = 0x0123456789ABCDEF   # the account id of a license that decrypts away from a console (pipeline/licenses.py)
PKG_MAGIC = b"\x7fPKG"
ZIP_MAGICS = (b"PK\x03\x04", b"PK\x05\x06")
READ = 4 * 1024 * 1024
TABLE_LIMIT = 256 * 1024 * 1024    # a PKG's header and file table lie in its first bytes; a ZIP member is read forward this far at most


class SetupError(Exception):
    pass


@dataclass
class Package:
    """One thing setup will import: a role, and where it is."""
    role: str                       # "base" | "update"
    form: str                       # "folder" | "pkg" | "zip"
    path: Path                      # the folder, the PKG file, or the ZIP file
    member: str | None = None       # the member's name inside the ZIP
    index: int | None = None        # and its position in the ZIP's listing (a name can repeat)
    size: int = 0
    version: str = ""
    embedded_license: bool = False
    sha256: str = ""                # of the PKG's bytes, set by fingerprint()
    field: str = ""                 # the setup field it came from, for messages

    @property
    def label(self) -> str:
        return f"{self.path} ({self.member})" if self.member else str(self.path)


@dataclass
class Sources:
    base: Package
    update: Package
    license: Path | None = None
    license_sha256: str = ""
    notes: list = field(default_factory=list)


@dataclass
class Found:
    """What one selected file, ZIP member or folder turned out to be."""
    package: Package
    explicit: bool                  # selected directly (any problem stops setup) rather than found inside a ZIP
    ok: bool = False
    problem: str = ""
    rank: int = 9                   # how relevant the problem is when a role stays empty (lower is more relevant)


def human(size: int) -> str:
    return f"{size / 1024**3:.1f} GB" if size >= 1024**3 else f"{size / 1024**2:.0f} MB"


# ---- looking at a selected path

def classify(path: Path, field_name: str) -> str:
    if path.is_dir():
        return "folder"
    if not path.exists():
        raise SetupError(f"{field_name}: the file or folder was not found:\n{path}")
    try:
        with path.open("rb") as stream:
            head = stream.read(4)
    except OSError as error:
        raise SetupError(f"{field_name}: {path} cannot be read ({error}).") from error
    if head == PKG_MAGIC:
        return "pkg"
    if head in ZIP_MAGICS:
        return "zip"
    raise SetupError(f"{field_name}: {path} is not a PKG or a ZIP file. Choose the game's .pkg file, a .zip that "
                     "holds the PKG files, or an extracted game folder.")


class PrefixReader:
    """read(offset, n) over a stream that can only be read forward, for a PKG inside a ZIP: the header, file table and
    param.sfo all lie near the start, so the bytes read so far are kept and nothing is read twice."""

    def __init__(self, stream, size: int):
        self.stream, self.size, self.buffer = stream, size, bytearray()

    def __call__(self, offset: int, count: int) -> bytes:
        end = offset + count
        if offset < 0 or end > self.size:
            raise PKG.PkgError("the file ends before its own header says it does -- truncated download?")
        if end > TABLE_LIMIT:
            raise PKG.PkgError("its file table is not where a PKG's is -- not a normal PKG")
        while len(self.buffer) < end:
            chunk = self.stream.read(min(READ, end - len(self.buffer)))
            if not chunk:
                raise PKG.PkgError("the file ended while it was being read -- truncated or damaged")
            self.buffer += chunk
        return bytes(self.buffer[offset:end])


DAMAGED = (PKG.PkgError, ValueError, struct.error, IndexError, KeyError, OverflowError, EOFError, zlib.error,
           zipfile.BadZipFile)


def judge_pkg(view, package: Package, where: str) -> Found:
    """Is this PKG the supported base, the supported update, or something else? `view` is PKG.inspect_pkg's result."""
    info = view.info
    app = SFO.get_app_info(info.sfo)
    package.embedded_license = view.entry(PKG.LICENSE_NAME) is not None
    package.version = app.app_version
    found = Found(package, explicit=False)
    if info.kind in ("dlc", "theme"):
        found.problem = f"{where} is add-on content ({info.kind}), not the game or its update."
        found.rank = 4
        return found
    if (info.title_id, info.content_id, app.content_id) != (TITLE, CONTENT, CONTENT):
        found.problem = (f"{where} is not Phantasy Star Nova: it is title {info.title_id or '(missing)'}, content ID "
                         f"{info.content_id or '(missing)'}. Setup needs the Japanese {NAME} {TITLE}.")
        found.rank = 3
        return found
    if info.kind == "app" and app.category == "gd":
        package.role, wanted = "base", BASE_VERSION
    elif info.kind == "patch":
        package.role, wanted = "update", UPDATE_VERSION
    else:
        found.problem = f"{where} has the category {app.category or '(missing)'}, which is not the base game or its update."
        found.rank = 3
        return found
    if app.app_version != wanted:
        kind = "base game" if package.role == "base" else "update"
        found.problem = (f"{where} is the {kind} version {app.app_version or '(missing)'}. Setup needs the Japanese "
                         f"{NAME} {kind} version {wanted}.")
        found.rank = 1
        return found
    found.ok = True
    return found


def damaged(package: Package, where: str, reason) -> Found:
    return Found(package, explicit=False, problem=f"{where} is damaged or incomplete ({reason}). Copy or download it again.",
                 rank=2)


def pkg_file_found(path: Path, field_name: str) -> Found:
    package = Package("", "pkg", path, size=path.stat().st_size, field=field_name)
    try:
        found = judge_pkg(PKG.inspect_pkg_file(str(path)), package, str(path))
    except OSError as error:
        raise SetupError(f"{field_name}: {path} cannot be read ({error}).") from error
    except DAMAGED as error:
        found = damaged(package, str(path), error)
    found.explicit = True
    return found


def zip_found(path: Path, field_name: str) -> list:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise SetupError(f"{field_name}: {path} is not a readable ZIP file ({error}). Download or copy it again.") from error
    except OSError as error:
        raise SetupError(f"{field_name}: {path} cannot be read ({error}).") from error
    results = []
    with archive:
        for index, member in enumerate(archive.infolist()):
            if member.is_dir() or member.file_size < 4:
                continue
            package = Package("", "zip", path, member.filename, index, member.file_size, field=field_name)
            where = f"{path} ({member.filename})"
            looks_like_pkg = member.filename.lower().endswith(".pkg")
            try:
                with archive.open(member) as stream:
                    if stream.read(4) != PKG_MAGIC:
                        if looks_like_pkg:
                            results.append(Found(package, False, problem=f"{where} has a .pkg name but is not a PKG file: "
                                                 "its first bytes are wrong. It is damaged, or another kind of file.", rank=2))
                        continue
                with archive.open(member) as stream:
                    view = PKG.inspect_pkg(PrefixReader(stream, member.file_size), member.file_size)
                results.append(judge_pkg(view, package, where))
            except NotImplementedError as error:   # (checked first: it is a kind of RuntimeError)
                if looks_like_pkg:
                    results.append(Found(package, False, problem=f"{where} uses a compression method setup cannot read "
                                         f"({error}). Make the ZIP again with 'Deflate' or 'Store'.", rank=0))
            except RuntimeError:   # (zipfile: a password-protected member)
                if looks_like_pkg:
                    results.append(Found(package, False, problem=f"{where} is password protected. Setup cannot open it; "
                                         "put the PKG in a ZIP without a password.", rank=0))
            except DAMAGED as error:
                results.append(damaged(package, where, error))
    return results


# ---- extracted folders (the layout setup has always accepted)

def folder_base(game: Path):
    candidates = (game / "app" / TITLE, game / TITLE, game)
    return next((path for path in candidates if (path / "sce_sys/param.sfo").is_file()), None)


def folder_update_paths(game: Path, base, explicit_update):
    if explicit_update:
        selected = explicit_update.resolve()
        return (selected / "patch" / TITLE, selected / TITLE, selected)
    return (game / "patch" / TITLE, base.parent.parent / "patch" / TITLE, base.parent / "patch" / TITLE)


def folder_info(path: Path):
    try:
        return SFO.get_app_info(SFO.read_sfo_file(str(path / "sce_sys/param.sfo")))
    except (ValueError, OSError, IndexError, struct.error) as error:
        raise SetupError(f"Unreadable sce_sys\\param.sfo in {path}: {error}") from error


def verify_folder(path: Path, role: str) -> Path:
    category, version, kind = ("gd", BASE_VERSION, "base game") if role == "base" else ("gp", UPDATE_VERSION, "update")
    info = folder_info(path)
    if (info.title_id, info.content_id, info.category) != (TITLE, CONTENT, category):
        raise SetupError(f"Expected the Japanese {TITLE} {kind} in {path}. Found title "
                         f"{info.title_id or '(missing)'}, content ID {info.content_id or '(missing)'}, "
                         f"category {info.category or '(missing)'}, version {info.app_version or '(missing)'}.")
    if info.app_version != version:
        raise SetupError(f"The {kind} at {path} reports {info.app_version or '(missing)'}. "
                         f"Supply the Japanese {kind} version {version} for {TITLE}.")
    return path


def select_folders(game: Path, explicit_update):
    """The base and update folders of an extracted dump, checked against their param.sfo. Raises SetupError."""
    game = game.resolve()
    base = folder_base(game)
    if base is None:
        raise SetupError(f"Could not find the Japanese {TITLE} base game. Select the folder containing "
                         f"app\\{TITLE} or select the base game folder with sce_sys\\param.sfo.\nSelected: {game}")
    update_paths = folder_update_paths(game, base, explicit_update)
    update = next((path for path in update_paths if (path / "sce_sys/param.sfo").is_file()), None)
    for path, role in ((base, "base"), (update, "update")):
        if path is None:
            expected = update_paths[0] / "sce_sys/param.sfo"
            raise SetupError(f"Missing the Japanese {TITLE} update 1.05. Select the folder containing patch\\{TITLE} "
                             f"or browse for the update separately.\nExpected metadata: {expected}")
        verify_folder(path, role)
    return base, update


def folder_found(path: Path, field_name: str, role: str) -> Found:
    """An extracted folder chosen next to a PKG or ZIP: the game folder in the Game field, or the update folder."""
    path = path.resolve()
    candidates = (path / "app" / TITLE, path / TITLE, path) if role == "base" else (path / "patch" / TITLE, path / TITLE, path)
    folder = next((p for p in candidates if (p / "sce_sys/param.sfo").is_file()), None)
    if folder is None:
        raise SetupError(f"{field_name}: no {NAME} game files (sce_sys\\param.sfo) were found in the folder {path}.")
    info = folder_info(folder)
    package = Package("", "folder", folder, field=field_name, version=info.app_version)
    found = Found(package, explicit=True)
    if (info.title_id, info.content_id) != (TITLE, CONTENT):
        found.problem = (f"{folder} is not Phantasy Star Nova: it is title {info.title_id or '(missing)'}, content ID "
                         f"{info.content_id or '(missing)'}. Setup needs the Japanese {NAME} {TITLE}.")
        found.rank = 3
        return found
    kind = {"gd": ("base", "base game", BASE_VERSION), "gp": ("update", "update", UPDATE_VERSION)}.get(info.category)
    if kind is None:
        found.problem = f"{folder} has the category {info.category or '(missing)'}, which is not the base game or its update."
        found.rank = 3
        return found
    package.role, noun, wanted = kind
    found.ok = info.app_version == wanted
    if not found.ok:
        found.problem = (f"The {noun} at {folder} reports {info.app_version or '(missing)'}. "
                         f"Supply the Japanese {noun} version {wanted} for {TITLE}.")
        found.rank = 1
    return found


# ---- choosing the base and the update

def describe(found: Found) -> str:
    return found.package.label


def assign(founds: list) -> tuple:
    roles = {"base": [], "update": []}
    for found in founds:
        if found.ok:
            roles[found.package.role].append(found)
    for role, matches in roles.items():
        if len(matches) > 1:
            names = "\n".join(f"  {describe(m)}  ({m.package.field})" for m in matches)
            what = f"the base game {BASE_VERSION}" if role == "base" else f"the update {UPDATE_VERSION}"
            raise SetupError(f"More than one package matches {what}:\n{names}\nKeep one of them: choose one {role} "
                             "package, or remove the extra file from the ZIP.")
    for found in founds:      # a file the player chose directly must be a package setup can use
        if found.explicit and not found.ok:
            raise SetupError(found.problem)
    base, update = roles["base"], roles["update"]
    if base and update:
        return base[0].package, update[0].package
    others = sorted((f for f in founds if not f.ok), key=lambda f: f.rank)
    extra = "".join(f"\n  - {f.problem}" for f in others[:4])
    if not base:
        only = (f"The update {UPDATE_VERSION} was found ({describe(update[0])}) but the base game was not. " if update else "")
        raise SetupError(f"{only}Setup needs the Japanese {NAME} base game {BASE_VERSION} ({TITLE}). Choose its PKG, or a "
                         f"ZIP that contains it, in the {GAME_FIELD} field." + (f"\nNot usable:{extra}" if extra else ""))
    raise SetupError(f"Only the base game {BASE_VERSION} was found ({describe(base[0])}). Setup also needs the update "
                     f"{UPDATE_VERSION}: choose the update PKG in the {UPDATE_FIELD} field, or choose a ZIP that "
                     "contains both packages." + (f"\nNot usable:{extra}" if extra else ""))


# ---- the license

def read_license(path: Path) -> tuple:
    """(the 512-byte license, notes) from a .rif or work.bin file. Raises SetupError when it is not Nova's license."""
    if not path.is_file():
        raise SetupError(f"{LICENSE_FIELD}: the file was not found:\n{path}")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise SetupError(f"{LICENSE_FIELD}: {path} cannot be read ({error}).") from error
    if len(data) not in (RIF.RIF_SIZE, 2 * RIF.RIF_SIZE):
        raise SetupError(f"{LICENSE_FIELD}: {path} is {len(data)} bytes. A game license (work.bin or .rif) is "
                         f"{RIF.RIF_SIZE} bytes; NoNpDrm's work.bin may be {2 * RIF.RIF_SIZE}.")
    try:
        info = RIF.parse_rif(data[:RIF.RIF_SIZE])
    except ValueError as error:
        raise SetupError(f"{LICENSE_FIELD}: {path} is not a game license ({error}).") from error
    if not re.fullmatch(r"[A-Z]{4}[0-9]{5}", info.title_id):
        raise SetupError(f"{LICENSE_FIELD}: {path} is not a game license: it holds no readable content ID. Choose the "
                         "work.bin or .rif that belongs to this game.")
    if info.content_id != CONTENT:
        raise SetupError(f"{LICENSE_FIELD}: {path} is the license for {info.content_id}, not for "
                         f"{NAME} ({CONTENT}). Choose the work.bin or .rif of this game.")
    notes = []
    if info.aid != NoNpDrm_AID:
        notes.append(f"Note: {path.name} is tied to a PlayStation account, not a NoNpDrm license. If setup cannot decrypt "
                     "the game with it, use the work.bin that came with your dump.")
    return data[:RIF.RIF_SIZE], notes


def check_license(license_path: Path | None, base: Package) -> tuple:
    """(the license path or None, its sha256, notes). A PKG or ZIP base needs a license of its own or one chosen."""
    if license_path is not None:
        data, notes = read_license(license_path)
        return license_path.resolve(), hashlib.sha256(data).hexdigest(), notes
    if base.form in ("pkg", "zip") and not base.embedded_license:
        raise SetupError(f"The base game package {base.label} does not contain a game license. Choose your game's "
                         f"work.bin (or its .rif) in the {LICENSE_FIELD} field.")
    return None, "", []


def resolve(game, update, license_path) -> Sources:
    """The checked base, update and license for a selection. Raises SetupError, naming the file, for a wrong title,
    wrong version, damaged package, repeated package or missing license. Nothing is written."""
    if not game:
        raise SetupError(f"Select the Japanese {NAME} game: its base-game PKG ({GAME_FIELD}), or one ZIP that holds the "
                         "base game and the update.")
    game = game.resolve() if hasattr(game, "resolve") else Path(game)
    update = update.resolve() if update else None
    game_kind = classify(game, GAME_FIELD)
    update_kind = classify(update, UPDATE_FIELD) if update else None
    notes = []
    if game_kind == "folder" and update_kind in (None, "folder"):
        base_folder, update_folder = select_folders(game, update)
        base = Package("base", "folder", base_folder, version=BASE_VERSION, field=GAME_FIELD)
        patch = Package("update", "folder", update_folder, version=UPDATE_VERSION, field=UPDATE_FIELD)
    else:
        founds = []
        for path, kind, field_name, role in ((game, game_kind, GAME_FIELD, "base"), (update, update_kind, UPDATE_FIELD, "update")):
            if path is None:
                continue
            if kind == "pkg":
                founds.append(pkg_file_found(path, field_name))
            elif kind == "zip":
                members = zip_found(path, field_name)
                if not members:
                    raise SetupError(f"{field_name}: {path} contains no PKG files. Choose a ZIP that holds the game's "
                                     "base PKG and update PKG.")
                founds.extend(members)
            else:
                founds.append(folder_found(path, field_name, role))
        base, patch = assign(founds)
        for found in founds:
            if not found.ok and not found.explicit and found.package.form == "zip":
                notes.append(f"Skipped: {found.problem}")
    license_file, license_digest, license_notes = check_license(license_path, base)
    return Sources(base, patch, license_file, license_digest, notes + license_notes)


# ---- reading and unpacking the packages

def copy_hash(source, destination, total: int, report, label: str) -> str:
    """Read `source` to the end, hashing it and (when `destination` is given) writing it, and report 25% steps."""
    digest, done, mark = hashlib.sha256(), 0, 0
    while True:
        chunk = source.read(READ)
        if not chunk:
            break
        digest.update(chunk)
        if destination is not None:
            destination.write(chunk)
        done += len(chunk)
        if total and report and done * 4 // total > mark and done < total:
            mark = done * 4 // total
            report(f"{label}: {mark * 25}%")
    return digest.hexdigest()


def open_member(archive: zipfile.ZipFile, package: Package):
    return archive.open(archive.infolist()[package.index])


def damaged_zip(package: Package, error) -> SetupError:
    return SetupError(f"{package.label} could not be read from the ZIP ({error}). The ZIP is damaged or incomplete: copy or "
                      "download it again.")


def fingerprint(package: Package, report) -> str:
    """The SHA-256 of a PKG's bytes (a ZIP member's, after unzipping), which names the build. Raises SetupError when the
    ZIP's own checksum shows the member is damaged."""
    label = f"Reading {package.member or package.path.name} ({human(package.size)})"
    report(label)
    try:
        if package.form == "zip":
            with zipfile.ZipFile(package.path) as archive, open_member(archive, package) as stream:
                package.sha256 = copy_hash(stream, None, package.size, report, label)
        else:
            with package.path.open("rb") as stream:
                package.sha256 = copy_hash(stream, None, package.size, report, label)
    except (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError) as error:
        raise damaged_zip(package, error) from error
    return package.sha256


def stage_member(package: Package, destination: Path, report) -> Path:
    """Stream a ZIP member to `destination` (a fixed file name in setup's scratch folder) and check it is the bytes that
    were fingerprinted. Returns `destination`."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(destination.parent).free
    if free < package.size + 1024**3:
        raise SetupError(f"Setup needs {human(package.size + 1024**3)} of free space on the release drive to unpack "
                         f"{package.member} from the ZIP, and {human(free)} is available. Free up space and run setup again.")
    partial = destination.with_name(destination.name + ".part")
    label = f"Unpacking {package.member} ({human(package.size)})"
    report(label)
    try:
        with zipfile.ZipFile(package.path) as archive, open_member(archive, package) as stream, partial.open("wb") as output:
            digest = copy_hash(stream, output, package.size, report, label)
    except (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError) as error:
        partial.unlink(missing_ok=True)
        raise damaged_zip(package, error) from error
    if digest != package.sha256:
        partial.unlink(missing_ok=True)
        raise SetupError(f"{package.label} changed while setup was running. Run setup again.")
    partial.replace(destination)
    return destination
