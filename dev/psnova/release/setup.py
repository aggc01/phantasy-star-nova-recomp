"""Windows release installer for Phantasy Star Nova Recomp. Done by Codex."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import setup_sources  # noqa: E402
from setup_sources import CONTENT, TITLE, SetupError  # noqa: E402,F401
ENGINE = ROOT / "engine"
DATA = ROOT / "NovaData"
PLAYER = DATA / "Player"
PYTHON = ENGINE / "python/python.exe"
PIPELINE = ENGINE / "pipeline/vitarecomp.py"
LOCALIZATION = ROOT / "localization"
BRIDGE = ENGINE / "release/Play Nova.exe"
GAME_EXE = ROOT / "Phantasy Star Nova.exe"
FFMPEG = ENGINE / "release/ffmpeg.exe"
ENGINE_SOURCES = ("decrypt", "dev", "packs", "pipeline", "recompiler", "runtime", "third_party")
FONT_NAME = "glenthregular.ttf"
DEFAULT_FONT = LOCALIZATION / "fonts" / FONT_NAME
# The Glenth Regular 1.004 TrueType file the English text, UI art and subtitles were built and checked with.
FONT_SHA256 = "eb9bf6e6c482e82307a6b505c58a3e70499c137dfddb98c7a53fc404d3745e0f"
FONT_URL = "https://elements.envato.com/glenth-classic-display-serif-font-9ZK6SWW"
SONY_FIRMWARE = "https://www.playstation.com/en-us/support/hardware/psvita/system-software/"
PUP_SHA256 = "6ef6dc8da6db026f28647713e473486d770087a605c52a8d751bfca7478386cf"
BASE = "NOVA_FileList_Vita.cpk"
MOVIE = "NOVA_FileList_Vita_movie.cpk"
PATCH = "NOVA_FileList_Vita_patch.cpk"
FIRMWARE_MODULES = (
    "os0/us/libgxm_es4.suprx.elf", "os0/us/libgpu_es4.suprx.elf",
    "vs0/sys/external/libc.suprx.elf", "vs0/sys/external/libscemp4.suprx.elf",
    "vs0/sys/external/libsceavplayer.suprx.elf",
)
BASE_FILES = {
    "eboot.bin.elf": "f4b3a669b53cf5ac8a2ecb26b3686011011129d8db7930c88a578e1463592542",
    BASE: "ad85c330c3258b0f18f57dcf77736f9fbea89c40b66dfef3fbb5c4daeff77e7a",
    MOVIE: "b006fcbf06008c1271b47b3999798e042243c6c99de570a6e069188ec971a01e",
}
PATCH_FILES = {
    "eboot.bin.elf": "abb45e179726d3021de144a900f912534fa6879061e068228cc0cd55286edcf3",
    PATCH: "ddd82122dd8cb6436566266879251b85c0b41cd758791bfd4f1e16239d9f9ba9",
}
LAYERED_FILES = {
    "sce_module/libc.suprx.elf": "b782bcdfd4ad9b019d82b88c03be0d1595b8c54ef60a799bf784c21df83abd87",
    "disc1/f00000.bin": "2279ffb66f388f46b4e611f90d31e5d7ec94dcb849a97fddf7b6ff5c9880f42f",
    "disc1/f00001.bin": "f58ef308d7e7213ab80f5ef05e325e01dd01beb4578471ac5bcb90226cfbeff0",
    "disc1/f00002.bin": "f34627d1493555cb7bf8497ab99d75b9f2e31b751f7a0cc5788cb6e2f698ebcb",
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def atomic_text(path, text):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as file:
        file.write(text)
        file.flush()
        os.fsync(file.fileno())
    temporary.replace(path)


def json_file(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def check_paths(paths):
    missing = [str(path) for path in paths if not path.is_file() or not path.stat().st_size]
    if missing:
        raise SetupError("Missing or empty required files:\n" + "\n".join(missing))


def original_files(packages, license_given):
    """Check the extracted-folder inputs (the PKG and ZIP forms are checked by their headers and by hash after import)
    and yield (name, path) for every file in them, to fingerprint."""
    folders = [package for package in packages if package.form == "folder"]
    required = []
    for package in folders:
        folder = package.path
        archives = (BASE, MOVIE) if package.role == "base" else (PATCH,)
        required.extend(folder / name for name in (*archives, "eboot.bin"))
        pfs = folder / "sce_pfs"
        if pfs.exists():
            required.extend(pfs / name for name in ("files.db", "unicv.db", "pflist"))
        if pfs.exists() and package.role == "base" and not license_given:
            required.append(folder / "sce_sys/package/work.bin")
    if len(folders) == 2:   # (a PKG carries these files inside it: the layered hashes check them after import)
        base, update = (package.path for package in sorted(folders, key=lambda package: package.role != "base"))
        for name in LAYERED_FILES:
            name = name.removesuffix(".elf")
            if not any((folder / name).is_file() for folder in (base, update)):
                required.append(update / name)
    check_paths(required)
    for package in folders:
        license_file = package.path / "sce_sys/package/work.bin"
        encrypted = (package.path / "sce_pfs").is_dir()
        if package.role == "base" and encrypted and not license_given and license_file.stat().st_size not in (512, 1024):
            raise SetupError(f"Invalid game license size. Supply your original work.bin at {license_file}.")
    for package in folders:
        for path in sorted(package.path.rglob("*")):
            if path.is_symlink() or path.is_junction():
                raise SetupError(f"Copy the linked file or folder into your game dump first: {path}")
            if path.is_file():
                yield f"{package.role}/{path.relative_to(package.path).as_posix()}", path


def check_hashes(folder, expected, package=None):
    check_paths(folder / name for name in expected)
    for name, sha256 in expected.items():
        if digest(folder / name) != sha256:
            if package is not None and package.form != "folder":
                raise SetupError(f"The {package.role} package {package.label} produced a {name} that differs from the "
                                 "supported unmodified Japanese game. The download or copy is damaged, or the package has "
                                 "been modified. Get the original base game 1.00 and update 1.05 packages again. "
                                 "Use packages from before any fan patch.")
            raise SetupError(f"{folder / name} differs from the supported unmodified Japanese game. "
                             "Replace it with the matching file from your 1.00 base game or 1.05 update. "
                             "Use the original archives before applying a fan patch.")


@contextmanager
def setup_lock():
    import msvcrt
    DATA.mkdir(exist_ok=True)
    with (DATA / "setup.lock").open("a+b") as handle:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise SetupError("Another setup process is using this folder. Close it before trying again.") from error
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def remove_superseded_installs(current, report):
    """Delete generated builds that a finished setup replaced. Saves and settings live in NovaData/Player."""
    def make_writable(function, path, error):
        os.chmod(path, stat.S_IWRITE)
        function(path)

    for path in sorted((DATA / "installs").iterdir()):
        if (path.name != current and re.fullmatch(r"[0-9a-f]{24}", path.name) and path.is_dir()
                and not path.is_symlink() and not path.is_junction()):
            report(f"Removing the replaced build {path.name[:8]}")
            try:
                shutil.rmtree(path, onexc=make_writable)
            except OSError as error:
                report(f"Could not remove the replaced build {path.name[:8]} ({error}). Setup will try again next time.")


def stage_environment(library):
    prefixes = ("RECOMP_", "ATIV_", "PYTHON", "BUILD_EXTRA_ENV", "NATIV_")
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith(prefixes)}
    for key in ("ANALYZER", "FORCE", "TARGET", "JOBS", "CPU", "CC", "CXX", "EXTRA_ENV"):
        env.pop(key, None)
    env.update(ATIV_DUMP=str(library), ATIV_WIN_TOOLCHAIN=str(ENGINE / "toolchain"),
               PYTHONUTF8="1", PYTHONNOUSERSITE="1", PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1",
               RECOMP_NO_REPATCH="1", RECOMP_NO_OVERLAY="1", TARGET="windows", RECOMP_CPU="generic")
    return env


def remember_inputs(args):
    """Keep what the player selected, so the setup window can reopen it after a stop or a failure. Only a font the
    player chose is remembered: the font bundled in the release is found again by its own path."""
    chosen = {key: str(getattr(args, key).resolve()) if getattr(args, key, None) else ""
              for key in ("game", "update", "license", "firmware", "font")}
    DATA.mkdir(exist_ok=True)
    atomic_text(DATA / "setup-inputs.json", json.dumps(chosen, indent=2) + "\n")


def prepare_install(args, report):
    if not args.game:
        raise SetupError("Select the Japanese Phantasy Star Nova game: its base-game PKG, or one ZIP that holds the "
                         "base game and the update.")
    remember_inputs(args)
    sources = setup_sources.resolve(args.game, args.update, getattr(args, "license", None))
    for note in sources.notes:
        report(note)
    for package in (sources.base, sources.update):
        report(f"{package.role.capitalize()}: {package.label} ({'ZIP member' if package.form == 'zip' else package.form}, "
               f"version {package.version})")
    if not args.firmware:
        raise SetupError("Select Sony's Vita system software 3.74 file (PSVUPDAT.PUP).")
    firmware = args.firmware.resolve()
    font = args.font.resolve() if args.font else DEFAULT_FONT
    if not font.is_file():
        which = f"The selected font file was not found:\n{font}" if args.font else (
            f"This release does not include the Glenth Regular font ({FONT_NAME}).")
        raise SetupError(f"{which}\n\nSetup uses Glenth Regular by OWPictures for the English text, UI art and movie "
                         f"subtitles. Get your own licensed copy:\n{FONT_URL}\nThen either choose {FONT_NAME} in the "
                         f"Font field, or copy it to:\n{DEFAULT_FONT}")
    required = [PYTHON, PIPELINE, ENGINE / "version.txt", firmware, font]
    required.extend((BRIDGE, FFMPEG, LOCALIZATION / "build_text.py", LOCALIZATION / "build_movies.py"))
    check_paths(required)
    report("Checking the game, update, firmware, and font...")
    if digest(firmware) != PUP_SHA256:
        raise SetupError(f"{firmware} is not the supported Sony Vita 3.74 update file. Download PSVUPDAT.PUP from Sony.\n"
                         + SONY_FIRMWARE)
    from PIL import ImageFont
    try:
        family, style = ImageFont.truetype(str(font), 18).getname()
    except OSError as error:
        raise SetupError(f"The selected font cannot be opened: {font}") from error
    if family.lower() != "glenth":
        raise SetupError(f"{font} is the font {family} {style}, not Glenth Regular. Choose {FONT_NAME}.\n{FONT_URL}")
    if digest(font) != FONT_SHA256:
        report(f"Note: this {family} {style} file is not the Glenth Regular 1.004 TrueType file the English layout was "
               "checked with. Setup will continue, but text spacing may differ slightly.")

    fingerprint = hashlib.sha256()
    fingerprint.update((ENGINE / "version.txt").read_bytes())
    fingerprint.update(f"\n{PUP_SHA256}\n{digest(font)}\n".encode())
    for path in sorted(LOCALIZATION.rglob("*")):
        if path.is_file() and "fonts" not in path.relative_to(LOCALIZATION).parts and path.suffix != ".pyc":
            fingerprint.update(f"{path.relative_to(LOCALIZATION).as_posix()}\0{digest(path)}\n".encode())
    # Any change to the recompiler, runtime, patches or pipeline must rebuild the game, even if version.txt is unchanged.
    for folder in ENGINE_SOURCES:
        for path in sorted((ENGINE / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                fingerprint.update(f"engine/{path.relative_to(ENGINE).as_posix()}\0{digest(path)}\n".encode())
    packages = (sources.base, sources.update)
    for name, path in original_files(packages, sources.license is not None):
        fingerprint.update(f"{name}\0{digest(path)}\n".encode())
    for package in packages:   # a PKG, or a PKG inside a ZIP: the hash of the package's own bytes
        if package.form != "folder":
            fingerprint.update(f"{package.role}-package\0{setup_sources.fingerprint(package, report)}\n".encode())
    if sources.license_sha256:
        fingerprint.update(f"license\0{sources.license_sha256}\n".encode())
    full_id = fingerprint.hexdigest()
    generation = full_id[:24]
    install = DATA / "installs" / generation
    library = install / "library"
    title = library / "decrypted" / TITLE
    recomp = title / "recomp"
    logs = install / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    os.environ["NOVA_SETUP_LOGS"] = str(logs)
    env = stage_environment(library)

    def command(name, argv):
        log = logs / f"{name}.log"
        with log.open("w", encoding="utf-8") as output:
            result = subprocess.run([str(x) for x in argv], cwd=ENGINE, env=env,
                                    stdout=output, stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-16:])
            raise SetupError(f"{name} failed (exit {result.returncode}).\nLog: {log}\n\n{tail}")

    def pipeline(name, *argv):
        command(name, [PYTHON, "-s", "-B", PIPELINE, *argv])

    state = install / "progress.json"
    journal = json_file(state)
    if journal and journal.get("inputs") != full_id:
        raise SetupError(f"The install record is inconsistent. Use a fresh release folder.\n{install}")
    completed = journal.setdefault("stages", [])
    journal["inputs"] = full_id

    def stage(name, label, work, outputs):
        if name in completed and all(path.is_file() and path.stat().st_size for path in outputs):
            report(f"{label} - already complete")
            return
        report(label)
        if name in completed:
            del completed[completed.index(name):]
            atomic_text(state, json.dumps(journal, indent=2) + "\n")
        work()
        check_paths(outputs)
        completed.append(name)
        atomic_text(state, json.dumps(journal, indent=2) + "\n")

    if "firmware" not in completed and shutil.disk_usage(ROOT).free < 14 * 1024**3:
        raise SetupError("Setup needs 14 GB of available space on the release drive to build the game.")
    fw = library / "firmware/3.74"
    stage("firmware", "Preparing Vita firmware modules", lambda: pipeline("firmware", "firmware", firmware),
          [fw / name for name in FIRMWARE_MODULES])

    scratch = DATA / "scratch"   # unpacked ZIP members live here, on the release drive, only while one import runs

    def clear_import_scratch(announce=False):
        """Remove what an interrupted or finished import leaves behind: an unpacked ZIP member, and the half-written
        decrypt folders (.add*) that a stopped `vitarecomp add` never cleans up."""
        def make_writable(function, path, error):
            os.chmod(path, stat.S_IWRITE)
            function(path)

        leftovers = [scratch] if scratch.exists() else []
        decrypted = library / "decrypted"
        leftovers.extend(decrypted.glob(".add*") if decrypted.is_dir() else [])
        if leftovers and announce:
            report("Removing what an interrupted import left behind")
        for path in leftovers:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path, onexc=make_writable)
            else:
                path.unlink(missing_ok=True)

    def install_input(name, package, destination, expected):
        clear_import_scratch(announce=True)
        license_args = ["--license", sources.license] if sources.license else []
        try:
            source = package.path
            if package.form == "zip":
                source = setup_sources.stage_member(package, scratch / "imports" / f"{name}.pkg", report)
            try:
                pipeline(name, "add", source, "--no-build", *license_args)
            except SetupError as error:
                if package.form == "folder":
                    raise
                lines = (logs / f"{name}.log").read_text(encoding="utf-8", errors="replace").splitlines()
                cause = next((line for line in reversed(lines) if line.strip()), "")
                hint = ("The game license did not decrypt this package: it belongs to another copy of the game, or the "
                        "package is damaged." if "klicensee" in cause else
                        "The package may be damaged, or the game license may not match it.")
                raise SetupError(f"Importing the {name} package {package.label} failed.\n{hint}\n\nCause: {cause}\n\n"
                                 f"{error}") from error
            check_hashes(destination, expected, package)
        finally:
            clear_import_scratch()

    stage("base", "Importing and checking the base game",
          lambda: install_input("base", sources.base, title / "app0", BASE_FILES), [title / "app0" / name for name in BASE_FILES])
    stage("update", "Importing and checking update 1.05",
          lambda: install_input("update", sources.update, title / "patch0", PATCH_FILES), [title / "patch0" / name for name in PATCH_FILES])
    def import_game():
        pipeline("import", "import", TITLE)
        check_hashes(recomp / "fs/app0", LAYERED_FILES)

    stage("import", "Preparing the patched game", import_game,
          [title / "version", recomp / "fs/app0" / BASE] + [recomp / "fs/app0" / name for name in LAYERED_FILES])
    stage("analyze", "Analyzing the game and firmware modules", lambda: pipeline("analyze", "analyze", TITLE),
          [title / "analysis/eboot.data.json"])

    def recompile():
        pipeline("recompile", "recompile", TITLE)
        command("labels", [PYTHON, "-I", "-B", ENGINE / "dev/psnova/check_labels.py", recomp, "game"])

    image_files = [recomp / "game.img"] + [recomp / (Path(name).name.split(".")[0] + ".img") for name in FIRMWARE_MODULES]
    stage("recompile", "Recompiling Vita code and checking generated labels", recompile,
          image_files + [recomp / ".recompile_inputs", recomp / "game_part99.c"])
    stage("build", "Building the Windows game executable", lambda: pipeline("build", "build", TITLE),
          [recomp / "game_host.exe", recomp / "SDL3.dll", recomp / ".built_version"])
    game_data = recomp / "fs/app0"
    english = recomp / "fs/lang/en"
    english.mkdir(parents=True, exist_ok=True)
    stage("english-text", "Building English menus and dialogue",
          lambda: command("english-text", [PYTHON, "-I", "-B", "-u", LOCALIZATION / "build_text.py", game_data / BASE,
                                           game_data / PATCH, english / PATCH, "--font", font]), [english / PATCH])
    stage("english-movies", "Building the English movie subtitles",
          lambda: command("english-movies", [PYTHON, "-I", "-B", "-u", LOCALIZATION / "build_movies.py", game_data / MOVIE,
                                             english / MOVIE, "--font", font, "--ffmpeg", FFMPEG,
                                             "--work", install / "movie-work"]), [english / MOVIE])
    shutil.rmtree(install / "movie-work", ignore_errors=True)   # scratch frames from the subtitle build
    report("Installing the English language and game launcher")
    atomic_text(english / "language.txt", "English\n")
    atomic_text(english.parent / "default.txt", "en\n")
    data = json.loads((title / "analysis/eboot.data.json").read_text(encoding="utf-8"))
    atomic_text(recomp / "entry.txt", f"{data['functions']['module_start'] & ~1:x}\n")
    (PLAYER / "savedata0").mkdir(parents=True, exist_ok=True)
    (PLAYER / "captures").mkdir(exist_ok=True)
    settings = PLAYER / "settings.ini"
    if not settings.exists():
        try:
            with settings.open("x", encoding="utf-8", newline="\n") as file:
                file.write("# Phantasy Star Nova Recomp\ninput_mode = auto\nrender_scale = 4\n"
                           "frame_rate = 60\nsharpen = 0.507067\nfullscreen = 0\n")
        except FileExistsError:
            pass
    if not GAME_EXE.is_file() or digest(GAME_EXE) != digest(BRIDGE):
        tmp = GAME_EXE.with_suffix(".exe.tmp")
        shutil.copyfile(BRIDGE, tmp)
        try:
            tmp.replace(GAME_EXE)
        except PermissionError as error:
            tmp.unlink(missing_ok=True)
            raise SetupError(f"Close {GAME_EXE.name} and run setup again to finish the update.") from error
    atomic_text(DATA / "current.txt", generation + "\n")
    remove_superseded_installs(generation, report)
    report(f"Setup complete. Start {GAME_EXE.name} from the release folder.")


def install(args, report):
    with setup_lock():
        prepare_install(args, report)


def main():
    parser = argparse.ArgumentParser(description="Phantasy Star Nova Recomp setup")
    parser.add_argument("--game", type=Path, help="the base-game PKG, a ZIP that holds the base game and the update, "
                        "or an extracted game folder")
    parser.add_argument("--update", type=Path, help="the update PKG, or an extracted update folder. Not needed when --game "
                        "is a ZIP with both packages or a folder that has patch\\PCSG00351")
    parser.add_argument("--license", type=Path, help="the game's work.bin or .rif, when the PKG has no license inside it")
    parser.add_argument("--firmware", type=Path, help="Sony's Vita system software 3.74 file (PSVUPDAT.PUP)")
    parser.add_argument("--font", type=Path, help="Glenth Regular, when it is not in localization\\fonts")
    args = parser.parse_args()
    if len(sys.argv) == 1:
        from setup_ui import show
        show(install, SetupError, ROOT, DATA, GAME_EXE, SONY_FIRMWARE, FONT_URL)
        return 0
    try:
        install(args, lambda message: print(message, flush=True))
    except (SetupError, OSError) as error:
        print(f"Setup could not finish.\n{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
