"""Run Nova's original Vita dialog code in an isolated test build. Done by Codex."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
TITLE = ROOT / "dump" / "decrypted" / "PCSG00351"
STAGE = ROOT / "dump" / "codex-firmware-dialogs"
BASE_MODULES = ("libc", "libgxm_es4", "libgpu_es4", "libscemp4", "libsceavplayer")
PROFILES = {
    "save-client": ("game_firmware_probe", ("libcdlg",)),
    "save-start": ("game_firmware_start", ("libcdlg", "libcdlg_main")),
    "save-paf": ("game_firmware_paf", ("libcdlg", "libcdlg_main", "libpaf",
                                      "common_gui_dialog", "libcdlg_savedata")),
    "save-pvf": ("game_firmware_save", ("libpvf", "libcdlg", "libcdlg_main", "libpaf",
                                       "common_gui_dialog", "libcdlg_savedata")),
    "save-list": ("game_firmware_list", ("libSceFt2", "libpvf", "libcdlg", "libcdlg_main", "libpaf",
                                         "common_gui_dialog", "libcdlg_savedata")),
    "ime": ("game_firmware_ime", ("libime",)),
    "ime-service": ("game_firmware_paf", ("libshellsvc", "libime")),
}


def hashes(folder):
    return {file.relative_to(folder).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
            for file in folder.rglob("*") if file.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=PROFILES)
    parser.add_argument("--input", help="override the scripted guest input")
    parser.add_argument("--first-frame", type=int, help="capture from this frame, in steps of 100")
    parser.add_argument("--last-frame", type=int, help="stop on this captured frame")
    parser.add_argument("--skip-movies", action="store_true", help="skip startup playback during dialog tests")
    parser.add_argument("--unpaced-from", type=int, help="run unpaced after this frame")
    parser.add_argument("--capture-frame", type=int, help="capture one frame's graphics calls for replay")
    parser.add_argument("--capture-output", type=Path, help="write the graphics capture here")
    parser.add_argument("--trace-imports", help="log specific host imports, comma separated")
    parser.add_argument("--trace-module", help="add comma-separated prefixes for firmware export traces")
    parser.add_argument("--trace-imports-from", type=int, help="trace calls starting at this frame")
    args = parser.parse_args()
    probe, modules = PROFILES[args.profile]
    executable = STAGE / (probe + ".exe")
    naming = args.profile.startswith("ime")
    fs = STAGE / ("fs-ime" if naming else "fs")
    work = STAGE / "runs" / args.profile
    live_save = TITLE / "recomp" / "fs" / "savedata0"
    if not executable.is_file() or not (fs / "app0").is_dir():
        parser.error(f"prepare {executable} and {fs} first")
    saves = fs / "savedata0"
    saves.mkdir(exist_ok=True)
    if saves.resolve().is_relative_to(live_save.resolve()) or saves.is_symlink():
        parser.error("the test needs an independent savedata0 directory")
    if not naming and not (saves / ".slot1").is_file():
        parser.error("copy the test slots into the isolated savedata0 directory first")

    work.mkdir(parents=True, exist_ok=True)
    prefs = work / "prefs"
    prefs.mkdir(exist_ok=True)
    analysis = json.loads((TITLE / "analysis" / "eboot.data.json").read_text(encoding="utf-8"))
    entry = f"{analysis['functions']['module_start'] & ~1:x}"
    base_input = "1300-1340:8,1700-1740:8,2000-2015:2000,2100-2115:2000"
    last_frame = "2300"
    if args.profile in ("save-pvf", "save-list"):
        base_input = "1300-1340:8,1700-1740:8,2440-2465:2000"
        last_frame = "2700"
    if naming:
        path = ROOT / "dev" / "psnova" / "inputs" / "to-arena.txt"
        route = path.read_text(encoding="utf-8").strip().split(",")
        base_input = ",".join(key for key in route if int(key.split("-")[0]) <= 12350)
        base_input += ",12640-12652:40,12720-12732:40,12800-12815:2000"
        base_input += ",13250-13295:2000,13440-13460:10,13560-13580:10,13700-13740:2000"
        base_input += ",14080-14100:40,14200-14225:2000,14350-14380:2000,14500-14530:2000"
        last_frame = "14700"
    if args.last_frame is not None:
        if args.last_frame < 100 or args.last_frame % 100:
            parser.error("--last-frame must be a positive multiple of 100")
        last_frame = str(args.last_frame)
    env = {k: v for k, v in os.environ.items() if not k.startswith("RECOMP_")}
    env.update(
        ATIV_PREFS=str(prefs), RECOMP_TITLE="PCSG00351", RECOMP_HEADLESS="1",
        RECOMP_LANGUAGE="en", RECOMP_FS=fs.as_posix(), RECOMP_CLOCK="fixed",
        RECOMP_GFX="gpu", RECOMP_RENDER_SCALE="1", RECOMP_SHADER_PREP="0",
        RECOMP_GPU_PRESENT_NOSYNC="1", RECOMP_INPUT=base_input if args.input is None else args.input,
        RECOMP_MODULES=",".join(str(STAGE / (m + ".img")) for m in BASE_MODULES + modules),
        RECOMP_TRACE_MODULE="sceIme,SceIpmi" if naming else "sceSaveDataDialog",
        RECOMP_SHOT="100", RECOMP_SHOT_FROM=last_frame, RECOMP_SHOT_LAST=last_frame,
    )
    if naming:
        env["RECOMP_UNPACED"] = "2100"
        env["RECOMP_SHOT_FROM"] = str(max(100, int(last_frame) - 800))
    if args.first_frame is not None:
        if args.first_frame < 100 or args.first_frame % 100 or args.first_frame > int(last_frame):
            parser.error("--first-frame must be a positive multiple of 100 at or before --last-frame")
        env["RECOMP_SHOT_FROM"] = str(args.first_frame)
    if args.skip_movies:
        env["RECOMP_SKIP_MOVIES"] = "1"
    if args.unpaced_from is not None:
        if args.unpaced_from < 1:
            parser.error("--unpaced-from must be positive")
        env["RECOMP_UNPACED"] = str(args.unpaced_from)
    if args.capture_output is not None and args.capture_frame is None:
        parser.error("--capture-output requires --capture-frame")
    if args.capture_frame is not None:
        if not 1 <= args.capture_frame <= int(last_frame):
            parser.error("--capture-frame must be between 1 and --last-frame")
        capture = args.capture_output or work / f"frame_{args.capture_frame}.vfc"
        env.update(RECOMP_CAPTURE=str(args.capture_frame), RECOMP_CAPTURE_FILE=str(capture.resolve()))
    if args.trace_imports:
        env["RECOMP_LOG_IMPORTS"] = args.trace_imports
    if args.trace_module:
        env["RECOMP_TRACE_MODULE"] += "," + args.trace_module
    if args.trace_imports_from is not None:
        env.update(RECOMP_LOG_FROM="1", RECOMP_LOG_FROM_FRAME=str(args.trace_imports_from),
                   RECOMP_LOG_GXM="1")
    if args.profile == "save-list":
        env.update(RECOMP_FIRMWARE_SAVE_LIST_ONLY="1", RECOMP_SAVE_DIALOG="auto")
    live_before = hashes(live_save)
    copied_before = hashes(saves)
    log_path = work / "session.log"
    try:
        with log_path.open("wb") as log:
            result = subprocess.run(
                [str(executable), str(STAGE / "game.img"), entry, "100000000000"],
                cwd=work, env=env, stdout=log, stderr=log, timeout=180,
            )
    except subprocess.TimeoutExpired:
        print("Probe exceeded its three-minute limit.")
        return 124
    finally:
        if hashes(live_save) != live_before:
            raise RuntimeError("The live save directory changed during the probe")
        print(f"Copied saves {'match' if hashes(saves) == copied_before else 'changed'}")
        print(log_path)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
