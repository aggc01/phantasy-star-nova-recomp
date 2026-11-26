"""route.py: repeatable save-based gameplay routes for Phantasy Star Nova (PCSG00351).

A route is a TOML file in dev/psnova/routes/: a save fixture, the slot to load, scripted pad input by frame, the frames
to screenshot and the windows to measure. Every run starts from the same bytes (a fresh copy of the fixture), runs the
installed build (dump/decrypted/PCSG00351/recomp/game_host.exe) in its own folder, and leaves a summary that can be
compared with earlier runs of the same route.

  route.py fixture <name> [--from <savedata0 folder>]   copy a savedata0 (default: your live one, read only)
                                                       into dump/saves/route-fixtures/<name>/ with its SHA-256 list
  route.py run <route> [--note text]                   one run: dump/routes/<route>/<YYYYmmdd-HHMMSS>/
        [--end N] [--shot-every N] [--env K=V ...]     an exploration run (finding a route's frames): marked as
                                                       such, and left out of compare
  route.py report <run folder>                         re-read a run's game.log and rewrite its summary
  route.py compare <route> [-n 4]                      the last n runs side by side, and the newest shots vs the run before
  route.py list                                        routes, fixtures and how many runs each route has

A run folder holds: fs/ (app0 and lang as junctions to the game's own, removed after the run; savedata0 a copy of the
fixture), settings.ini, shader_cache/ (a copy of yours, so every run starts equally warm), game.log (stderr),
shot_NNNNN.ppm/.png, summary.json and summary.txt.

Safety: your live saves are hashed before and after (a change fails the run); the fixture is hashed against
its fixture.json before it is copied (a changed fixture refuses to run); the game never sees either folder.

Frames are the runtime's presented-frame counter from boot (display.c), the one RECOMP_INPUT and RECOMP_SHOT use.
metrics lines carry no frame number: each is placed between the frame-numbered lines around it (psn clock every 300
frames, hitches, the last shot), so a metrics sample's frame is approximate (about one second either way).
With the real clock (the default, as you run it) frame numbers drift a little run to run: load times vary, so
inputs keyed to frames land a few frames apart. clock = "fixed" makes a run deterministic but is not real-time.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ROUTES = HERE / "routes"
FIXTURES = REPO / "dump" / "saves" / "route-fixtures"
RUNS = REPO / "dump" / "routes"
TITLE = "PCSG00351"
sys.path.insert(0, str(REPO / "pipeline"))
import vitarecomp as V  # noqa: E402  (the Game object: install folder, modules, entry, RUN_ENV)

# The settings every route starts with: no first-run hints, a window. A route's [settings] table adds to these.
BASE_SETTINGS = {"menu_hint_shown": 1, "touch_intro_shown": 1, "fullscreen": 0, "language": "en"}
# Telemetry on in every run (the same family the launcher turns on for Nova): metrics every second, the GPU fence and
# per-thread waits, the game's own clock every 300 frames, hitches over 35 ms.
TELEMETRY = {"RECOMP_METRICS": "1", "RECOMP_GPU_FENCE_STATS": "1", "RECOMP_WAIT_STATS": "300",
             "RECOMP_PSN_FPS_TRACE": "1", "RECOMP_HITCH_LOG": "35"}


def sha_dir(p):
    p = Path(p)
    return {x.name: hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(p.iterdir()) if x.is_file()}


def sha_file(p, limit=None):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def git_head():
    try: return subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError: return "?"


def die(msg):
    print("route: " + msg, file=sys.stderr); sys.exit(1)


# ---------------------------------------------------------------------------------------------------------- fixtures
def cmd_fixture(a):
    g = V.Game(TITLE, "run")
    src = Path(a.from_ or Path(g.OUT) / "fs" / "savedata0")
    if not (src / "system.bin").is_file(): die(f"{src}: not a savedata0 folder (no system.bin)")
    dst = FIXTURES / a.name
    if dst.exists(): die(f"{dst} exists; fixtures are never overwritten (pick another name)")
    before = sha_dir(src)
    shutil.copytree(src, dst / "savedata0")
    if sha_dir(src) != before: die(f"{src} changed while it was copied (is the game running?); delete {dst} and retry")
    files = sha_dir(dst / "savedata0")
    if files != before: die("the copy differs from the source")
    info = {"name": a.name, "source": str(src), "made": datetime.datetime.now().isoformat(timespec="seconds"),
            "files": files, "slots": sorted(int(x.name[5:]) for x in src.iterdir() if re.fullmatch(r"\.slot\d+", x.name))}
    (dst / "fixture.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    print(f"fixture {a.name}: {len(files)} files, slots {info['slots']} -> {dst}")
    print("  the slot list (title, level, place) shows in a run's summary once a route loads it")


def check_fixture(name):
    d = FIXTURES / name
    try: info = json.loads((d / "fixture.json").read_text(encoding="utf-8"))
    except OSError: die(f"no fixture {name} ({d}); make it with: route.py fixture {name}")
    now = sha_dir(d / "savedata0")
    if now != info["files"]: die(f"fixture {name} changed since it was made ({d}); make a new one instead")
    return d / "savedata0", info


# ------------------------------------------------------------------------------------------------------------ routes
def load_route(name):
    p = ROUTES / (name if name.endswith(".toml") else name + ".toml")
    if not p.is_file(): die(f"no route {p}")
    r = tomllib.loads(p.read_text(encoding="utf-8"))
    for k in ("fixture", "end"):
        if k not in r: die(f"{p.name}: '{k}' is required")
    r["_name"] = p.stem; r["_path"] = p
    return r


def joined(v, sep):
    if isinstance(v, str): return v.strip()
    return sep.join(s.strip() for s in v if s.strip())


def shot_env(shots):
    """RECOMP_SHOT takes every n-th frame in a window: the gcd of the asked frames, extra shots deleted afterwards"""
    if not shots: return {}
    step = 0
    for s in shots: step = math.gcd(step, s)
    return {"RECOMP_SHOT": str(step), "RECOMP_SHOT_FROM": str(min(shots)), "RECOMP_SHOT_TO": str(max(shots))}


def make_junction(link, target):
    import _winapi
    _winapi.CreateJunction(str(target), str(link))


def remove_junction(link):
    if os.path.lexists(link):
        try: os.rmdir(link)   # a junction: removes the link only, never the target's contents
        except OSError as e: print(f"  could not remove the junction {link}: {e}")


def cmd_run(a):
    r = load_route(a.route)
    g = V.Game(TITLE, "run")
    out = Path(g.OUT)
    live = out / "fs" / "savedata0"
    fixture, finfo = check_fixture(r["fixture"])
    if "fixture_sha" in r and r["fixture_sha"] != fixture_digest(finfo): die("the route names another version of its fixture")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    run = RUNS / r["_name"] / (stamp + ("-explore" if (a.end or a.shot_every or a.env) else ""))
    run.mkdir(parents=True)
    shutil.copy2(r["_path"], run / "route.toml")
    fs = run / "fs"; fs.mkdir()
    make_junction(fs / "app0", out / "fs" / "app0")
    if (out / "fs" / "lang").is_dir(): make_junction(fs / "lang", out / "fs" / "lang")
    shutil.copytree(fixture, fs / "savedata0")
    if (out / "shader_cache").is_dir(): shutil.copytree(out / "shader_cache", run / "shader_cache")
    settings = dict(BASE_SETTINGS); settings.update(r.get("settings", {}))
    (run / "settings.ini").write_text("".join(f"{k} = {v}\n" for k, v in settings.items()), encoding="utf-8")

    clock = r.get("clock", "real"); gfx = r.get("gfx", "gpu")
    explore = bool(a.end or a.shot_every or a.env)
    if a.end: r["end"] = a.end; r["windows"] = [w for w in r.get("windows", []) if int(w["to"]) <= a.end]
    end = int(r["end"]); shots = sorted(set(int(s) for s in r.get("shots", []) if int(s) <= end) | {end})
    if a.shot_every: shots = sorted(set(range(a.shot_every, end, a.shot_every)) | {end})
    env = {k: v for k, v in os.environ.items() if not k.startswith("RECOMP_")}
    env.update(w.split("=", 1) for w in g.RUN_ENV.split() if "=" in w)
    env.update(TELEMETRY)
    env.update({
        "ATIV_PREFS": str(run / "prefs"), "RECOMP_SETTINGS": str(run / "settings.ini"), "RECOMP_FS": str(fs),
        "RECOMP_LANGUAGE": str(settings.get("language", "en")), "RECOMP_TITLE": TITLE, "RECOMP_GAME_NAME": g.NAME,
        "RECOMP_MODULES": ",".join(str(out / (m + ".img")) for m in g.MODS),
        "RECOMP_GFX": gfx, "RECOMP_CLOCK": clock, "RECOMP_LOG": "0",
        "RECOMP_SAVE_DIALOG": "auto", "RECOMP_SAVE_DIALOG_ROW": str(r.get("save_row", 0)),
        "RECOMP_INPUT": joined(r.get("buttons", ""), ","), "RECOMP_INPUT_STICKS": joined(r.get("sticks", ""), ";"),
        "RECOMP_SHOT_LAST": str(end),
        "PATH": str(out) + os.pathsep + str(REPO / "toolchain" / "llvm-mingw" / "bin") + os.pathsep + env.get("PATH", ""),
    })
    if "render_scale" in settings: env["RECOMP_RENDER_SCALE"] = str(settings["render_scale"])
    if r.get("headless"): env["RECOMP_HEADLESS"] = "1"
    shipped = REPO / "packs" / TITLE / "shaders.txt"
    if shipped.is_file(): env["RECOMP_SHADER_RECIPES_SHIPPED"] = str(shipped)
    env.update(shot_env(shots))
    env.update({k: str(v) for k, v in r.get("env", {}).items()})
    env.update(kv.split("=", 1) for kv in (a.env or []))
    timeout = int(r.get("timeout", 90 + end / (20 if clock == "real" else 4)))

    exe = out / g.EXE
    meta = {"route": r["_name"], "run": stamp, "note": a.note or "", "git": git_head(), "exe": str(exe),
            "exe_size": exe.stat().st_size, "exe_mtime": datetime.datetime.fromtimestamp(exe.stat().st_mtime).isoformat(timespec="seconds"),
            "exe_sha256": sha_file(exe), "fixture": r["fixture"], "fixture_digest": fixture_digest(finfo),
            "save_row": r.get("save_row", 0), "explore": explore, "clock": clock, "gfx": gfx, "end": end, "shots": shots,
            "env": {k: v for k, v in env.items() if k.startswith(("RECOMP_", "ATIV_"))}}
    (run / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")

    live_before = sha_dir(live) if live.is_dir() else {}
    print(f"route {r['_name']}: run {stamp}, slot row {meta['save_row']} of fixture {r['fixture']}, to frame {end} "
          f"({gfx}, {clock} clock, timeout {timeout} s)\n  {run}", flush=True)
    rc = None
    try:
        with open(run / "game.log", "wb") as log:
            p = subprocess.Popen([str(exe), str(out / (g.BASE + ".img")), g.entry(), "100000000000"],
                                 cwd=run, env=env, stdout=log, stderr=log)
            try: rc = p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                p.kill(); p.wait(); rc = "timeout"
            except KeyboardInterrupt:
                p.kill(); p.wait(); rc = "interrupted"
    finally:
        remove_junction(fs / "app0"); remove_junction(fs / "lang")
        live_changed = live.is_dir() and sha_dir(live) != live_before
    meta["exit"] = rc; meta["live_save_unchanged"] = not live_changed
    (run / "meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    keep_shots(run, shots)
    s = summarise(run, r, meta)
    print((run / "summary.txt").read_text(encoding="utf-8"))
    if live_changed: print("!! YOUR LIVE SAVE CHANGED DURING THE RUN (another game window?)")
    return 0 if s["ok"] else 1


def fixture_digest(info):
    return hashlib.sha256(json.dumps(info["files"], sort_keys=True).encode()).hexdigest()[:16]


def keep_shots(run, shots):
    want = {f"shot_{s:05d}.ppm" for s in shots}
    for p in run.glob("shot_*.ppm"):
        if p.name not in want: p.unlink(); continue
        try:
            from PIL import Image
            Image.open(p).save(p.with_suffix(".png"))
        except Exception as e: print(f"  {p.name}: no PNG ({e})")


# --------------------------------------------------------------------------------------------------------- log parse
RE_FRAME = [re.compile(r"^\s+psn clock: frame (\d+) target (\d+)"), re.compile(r"^\s+hitch \d+: frame (\d+) took ([\d.]+) ms"),
            re.compile(r"frame (\d+) shot: the last one"), re.compile(r"^\s+psn frame rate: \d+ fps \(frame (\d+)\)")]
RE_METRICS = re.compile(r"^\s+metrics: ([\d.]+) fps \(frame ([\d.]+)/([\d.]+)/([\d.]+) ms avg/max/1%low\).*?render ([\d.]+) ms"
                        r".*?cpu (\d+)%.*?audio (\d+) ms queued \((\d+) ports\), (\d+) underruns")
RE_FENCE = re.compile(r"^\s+gpu fence \([^)]*\): (\d+) frames done, gpu busy ([\d.]+) ms/frame \(max ([\d.]+)\)")
RE_WAITS = re.compile(r"^\s+waits: (\d+) presents in ([\d.]+) s \(([\d.]+) fps\)")
RE_SLOT = re.compile(r"^\s+(>?)\s*slot (\d+): (.*)$")
RE_PICK = re.compile(r"save dialog: list -> picked \(slot (\d+)\)")


def parse_log(path):
    """the samples in order, each with a frame: exact for frame-numbered lines, interpolated for metrics/fence/waits"""
    ev, slots, picked, hitches = [], {}, None, []
    with open(path, "rb") as f:
        for raw in f:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            m = None
            for rx in RE_FRAME:
                m = rx.search(line)
                if m: ev.append(("frame", int(m.group(1)))); break
            if m:
                if rx is RE_FRAME[1]: hitches.append((int(m.group(1)), float(m.group(2))))
                continue
            if (m := RE_METRICS.search(line)):
                ev.append(("metrics", dict(fps=float(m[1]), avg=float(m[2]), max=float(m[3]), low=float(m[4]), render=float(m[5]),
                                           cpu=int(m[6]), audio=int(m[7]), underruns=int(m[9]))))
            elif (m := RE_FENCE.search(line)): ev.append(("fence", dict(busy=float(m[2]), busy_max=float(m[3]))))
            elif (m := RE_WAITS.search(line)): ev.append(("waits", dict(fps=float(m[3]))))
            elif (m := RE_PICK.search(line)): picked = int(m[1])
            elif "save dialog" not in line and (m := RE_SLOT.match(line)) and len(line) < 300: slots[int(m[2])] = m[3].strip()
    # interpolate: samples between two frame markers share the span evenly (markers are monotonic; drop any that go back)
    marks = [(i, v) for i, (k, v) in enumerate(ev) if k == "frame"]
    clean, last = [], -1
    for i, v in marks:
        if v >= last: clean.append((i, v)); last = v
    samples = []
    for i, (k, v) in enumerate(ev):
        if k == "frame": continue
        prev = max((c for c in clean if c[0] < i), default=None, key=lambda c: c[0])
        nxt = min((c for c in clean if c[0] > i), default=None, key=lambda c: c[0])
        if prev and nxt and nxt[0] > prev[0]: fr = prev[1] + (nxt[1] - prev[1]) * (i - prev[0]) / (nxt[0] - prev[0])
        elif prev: fr = prev[1]
        elif nxt: fr = 0
        else: fr = None
        samples.append(dict(kind=k, frame=None if fr is None else round(fr), **v))
    return samples, slots, picked, hitches


def window_stats(samples, hitches, lo, hi):
    ms = [s for s in samples if s["kind"] == "metrics" and s["frame"] is not None and lo <= s["frame"] <= hi]
    fe = [s for s in samples if s["kind"] == "fence" and s["frame"] is not None and lo <= s["frame"] <= hi]
    hs = [h for h in hitches if lo <= h[0] <= hi]
    st = {"from": lo, "to": hi, "samples": len(ms)}
    if ms:
        st.update(fps_mean=round(sum(s["fps"] for s in ms) / len(ms), 2), fps_min=min(s["fps"] for s in ms),
                  frame_max_ms=max(s["max"] for s in ms), render_ms=round(sum(s["render"] for s in ms) / len(ms), 2),
                  underruns=ms[-1]["underruns"] - ms[0]["underruns"])
    if fe: st["gpu_busy_ms"] = round(sum(s["busy"] for s in fe) / len(fe), 2)
    st["hitches"] = len(hs); st["hitch_max_ms"] = max((h[1] for h in hs), default=0)
    return st


def summarise(run, r, meta):
    samples, slots, picked, hitches = parse_log(run / "game.log")
    end = meta["end"]
    windows = [dict(name=w.get("name", f"{w['from']}-{w['to']}"), **window_stats(samples, hitches, int(w["from"]), int(w["to"])))
               for w in r.get("windows", [])]
    whole = window_stats(samples, hitches, 0, end)
    checks = []
    checks.append(("exited at the last frame", meta.get("exit") == 0 and (run / f"shot_{end:05d}.ppm").exists(), f"exit {meta.get('exit')}"))
    if "expect_slot" in r: checks.append(("loaded the expected slot", picked == r["expect_slot"], f"picked {picked}, expected {r['expect_slot']}"))
    checks.append(("player's live save unchanged", meta.get("live_save_unchanged", True), ""))
    for w in windows:
        if "min_fps" in r and w.get("samples"):
            checks.append((f"window {w['name']}: mean fps >= {r['min_fps']}", w["fps_mean"] >= r["min_fps"], f"{w.get('fps_mean')}"))
        if w.get("samples", 0) == 0: checks.append((f"window {w['name']}: has samples", False, "none (run ended early?)"))
    ok = all(c[1] for c in checks)
    s = {"ok": ok, "checks": [dict(name=n, ok=o, detail=d) for n, o, d in checks], "picked_slot": picked, "slots": slots,
         "windows": windows, "whole_run": whole, "hitches": hitches[:200], "meta": meta,
         "fps_trace": [(s["frame"], s["fps"]) for s in samples if s["kind"] == "metrics"]}
    (run / "summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    L = [f"{meta['route']} {meta['run']}  {'PASS' if ok else 'FAIL'}  (git {meta['git']}, exe {meta['exe_mtime']}, "
         f"fixture {meta['fixture']}, {meta['gfx']}/{meta['clock']})"]
    if meta.get("note"): L.append(f"  note: {meta['note']}")
    for n, o, d in checks: L.append(f"  [{'ok' if o else 'FAIL'}] {n}" + (f": {d}" if d else ""))
    for k in sorted(slots): L.append(f"  {'>' if k == picked else ' '} slot {k}: {slots[k]}")
    L.append(f"  {'window':<22}{'frames':>13}{'fps mean':>10}{'fps min':>9}{'max ms':>8}{'gpu ms':>8}{'hitches':>9}")
    for w in windows + [dict(name="(whole run)", **whole)]:
        L.append(f"  {w['name']:<22}{str(w['from']) + '-' + str(w['to']):>13}{w.get('fps_mean', '-'):>10}{w.get('fps_min', '-'):>9}"
                 f"{w.get('frame_max_ms', '-'):>8}{w.get('gpu_busy_ms', '-'):>8}{w['hitches']:>5} {w['hitch_max_ms']:>.0f}")
    (run / "summary.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    return s


def cmd_report(a):
    run = Path(a.run).resolve()
    meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
    r = tomllib.loads((run / "route.toml").read_text(encoding="utf-8"))
    summarise(run, r, meta)
    print((run / "summary.txt").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------------------ compare
def read_ppm(p):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)


def cmd_compare(a):
    d = RUNS / a.route
    runs = sorted(p for p in d.iterdir() if (p / "summary.json").is_file() and not p.name.endswith("-explore")) if d.is_dir() else []
    if not runs: die(f"no runs of {a.route} yet")
    runs = runs[-a.n:]
    S = [json.loads((p / "summary.json").read_text(encoding="utf-8")) for p in runs]
    print(f"{a.route}: {len(S)} runs")
    for s in S:
        m = s["meta"]
        print(f"  {m['run']}  {'PASS' if s['ok'] else 'FAIL'}  git {m['git']}  exe {m['exe_mtime']} {m['exe_sha256'][:8]}  {m.get('note', '')}")
    names = [w["name"] for w in S[-1]["windows"]] + ["(whole run)"]
    for key, label in (("fps_mean", "fps mean"), ("fps_min", "fps min"), ("frame_max_ms", "worst frame ms"),
                       ("gpu_busy_ms", "gpu busy ms"), ("hitches", "hitches")):
        print(f"\n  {label:<22}" + "".join(f"{s['meta']['run'][4:]:>14}" for s in S))
        for n in names:
            row = []
            for s in S:
                w = s["whole_run"] if n == "(whole run)" else next((x for x in s["windows"] if x["name"] == n), {})
                row.append(w.get(key, "-"))
            print(f"  {n:<22}" + "".join(f"{str(v):>14}" for v in row))
    if len(runs) >= 2:
        try:
            import numpy as np
            print("\n  shots, newest vs the run before (mean / max channel difference, % of pixels off by > 8):")
            for p in sorted(runs[-1].glob("shot_*.ppm")):
                q = runs[-2] / p.name
                if not q.exists(): print(f"    {p.name}: not in the run before"); continue
                x, y = read_ppm(p), read_ppm(q)
                if x.shape != y.shape: print(f"    {p.name}: sizes differ"); continue
                dd = np.abs(x - y).max(axis=2)
                print(f"    {p.name}: {dd.mean():.2f} / {dd.max()}  {100 * (dd > 8).mean():.1f}%")
        except ImportError: print("  (numpy/PIL missing: no shot comparison)")


def cmd_list(a):
    print("routes:")
    for p in sorted(ROUTES.glob("*.toml")):
        r = tomllib.loads(p.read_text(encoding="utf-8"))
        n = len([x for x in (RUNS / p.stem).glob("*/summary.json") if not x.parent.name.endswith("-explore")]) if (RUNS / p.stem).is_dir() else 0
        print(f"  {p.stem:<24} fixture {r.get('fixture')}, row {r.get('save_row', 0)}, to {r.get('end')}, {n} runs  {r.get('description', '')[:70]}")
    print("fixtures:")
    for p in sorted(FIXTURES.glob("*/fixture.json")):
        i = json.loads(p.read_text(encoding="utf-8"))
        print(f"  {i['name']:<24} slots {i['slots']}, made {i['made']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    f = sp.add_parser("fixture"); f.add_argument("name"); f.add_argument("--from", dest="from_")
    r = sp.add_parser("run"); r.add_argument("route"); r.add_argument("--note")
    r.add_argument("--end", type=int); r.add_argument("--shot-every", type=int); r.add_argument("--env", action="append")
    p = sp.add_parser("report"); p.add_argument("run")
    c = sp.add_parser("compare"); c.add_argument("route"); c.add_argument("-n", type=int, default=4)
    sp.add_parser("list")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except AttributeError: pass
    return {"fixture": cmd_fixture, "run": cmd_run, "report": cmd_report, "compare": cmd_compare, "list": cmd_list}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
