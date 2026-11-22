"""Frame-rate report from a timing run's log (RECOMP_METRICS, RECOMP_GPU_STATS, RECOMP_WAIT_STATS=300).
Per 300-frame window: fps, draws/frame, readbacks/frame, the renderer's host time per frame and its biggest parts,
and the busiest game thread. Usage: python dev/psnova/timing_report.py <test.log> [window=300]"""
import re, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
path = sys.argv[1]; W = int(sys.argv[2]) if len(sys.argv) > 2 else 300
re_frame = re.compile(r"gpu stats: frame (\d+): (\d+) draws on the GPU.*?(\d+) readbacks")
re_time = re.compile(r"gpu time: ([\d.]+) ms = (.*)")
re_part = re.compile(r"([a-z][a-z ]*?) ([\d.]+)(?= |\(|\[|$)")
re_shot = re.compile(r"frame (\d+): \d+x\d+ at 0x[0-9a-f]+, ([\d.]+) s")
re_wait = re.compile(r"waits: 300 presents in ([\d.]+) s \(([\d.]+) fps\)")
re_thr = re.compile(r"waits:\s+(\S.*?)\s+([\d.]+)% \|\s+([\d.]+)\s+([\d.]+) \|\s+([\d.]+) \|\s+([\d.]+)\s+([\d.]+),\s+([\d.]+)\s+([\d.]+)")

win = defaultdict(lambda: {"n": 0, "draws": 0, "rb": 0, "t": 0.0, "parts": defaultdict(float)})
times = {}
waits = []   # (fps, [(thread, busy, blocked_ms, held_ms)])
cur = None; cur_w = None
for line in open(path, encoding="utf-8", errors="replace"):
    m = re_frame.search(line)
    if m:
        cur = int(m.group(1)); w = win[cur // W]; w["n"] += 1; w["draws"] += int(m.group(2)); w["rb"] += int(m.group(3)); continue
    m = re_time.search(line)
    if m and cur is not None:
        w = win[cur // W]; w["t"] += float(m.group(1))
        body = m.group(2)
        for key in ("texture binding", "target sync", "upload", "shaders", "pipelines", "vertex fetch", "vertex upload",
                    "scene target upload", "submit", "pass", "hash"):
            mm = re.search(r"(?<![a-z])" + key + r" ([\d.]+)", body)
            if mm: w["parts"][key] += float(mm.group(1))
        continue
    m = re_shot.search(line)
    if m: times[int(m.group(1))] = float(m.group(2)); continue
    m = re_wait.search(line)
    if m: cur_w = (float(m.group(2)), cur, []); waits.append(cur_w); continue
    m = re_thr.search(line)
    if m and cur_w is not None:
        cur_w[2].append((m.group(1).strip(), float(m.group(2)), float(m.group(4)), float(m.group(8))))

print(f"{'frames':>13} {'fps':>5} {'draws':>6} {'rb/f':>5} {'host ms/f':>9}  biggest parts (ms/frame)")
for k in sorted(win):
    w = win[k]
    if not w["n"]: continue
    a, b = k * W, (k + 1) * W
    fps = (b - a) / (times[b] - times[a]) if a in times and b in times and times[b] > times[a] else float("nan")
    n = w["n"]
    parts = sorted(((v / n, p) for p, v in w["parts"].items()), reverse=True)[:4]
    print(f"{a:6d}-{b:6d} {fps:5.1f} {w['draws']/n:6.0f} {w['rb']/n:5.1f} {w['t']/n:9.1f}  " + ", ".join(f"{p} {v:.1f}" for v, p in parts))

print("\nwaits (every 300 presents): fps | busiest threads: busy% blocked-ms/f lock-held-ms/f")
for fps, fr, thr in waits:
    top = sorted(thr, key=lambda t: -t[1])[:3]
    print(f"~frame {fr}: {fps:5.1f} fps | " + " ; ".join(f"{t[0]} {t[1]:.0f}% {t[2]:.1f} {t[3]:.1f}" for t in top))
