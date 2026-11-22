"""Per-frame Japanese-subtitle evidence for the ORIGINAL Japanese story movies (written 2026-11-18, evening).

Why: the first cleaner (remove_jp_subs.py) keyed on the English line the fan patch burned in; the base movies have none.
For each movie this computes, from the ORIGINAL movie only, per frame: tl = persistent text-like pixels (white fill with a
dark outline within 2 px) in the Japanese band, st = persistent strokes (|gray - 9x9 median| > 20) in the band. As a check
(not a dependency) it also computes the old detector's presence mask on the fan-patched copy of the same movie.
Result: dump/psnova-l10n/presence/<name>.npz (tl, st, old_present); prints the agreement for a few thresholds.

  python jp_presence.py NAME Y0 Y1 [NAME Y0 Y1 ...]      (4 processes)
"""
import os, sys
import numpy as np, cv2
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import remove_jp_subs as R

ROOT = r"F:\Antigravity Proj\Recomp-decomp\Phantasy Star Nova Recomp\dump\psnova-l10n"


def base_counts(path, y0, y1):
    c = cv2.VideoCapture(path)
    T, S = [], []
    while True:
        ok, f = c.read()
        if not ok:
            break
        band = f[y0:y1]
        T.append(R.textlike(band))
        S.append(R.strokes(band, 20))
    n = len(T)
    tl = np.zeros(n, np.int64); st = np.zeros(n, np.int64)
    for k in range(n):
        for A, out in ((T, tl), (S, st)):
            nb = np.zeros_like(A[k])
            if k > 0: nb |= A[k - 1]
            if k + 1 < n: nb |= A[k + 1]
            out[k] = int(R.persist(A[k], nb).sum())
    return tl, st


def job(a):
    name, y0, y1 = a
    tl, st = base_counts(os.path.join(ROOT, "movies_jp", name + ".mp4"), y0, y1)
    jp, en = R.count_pass(os.path.join(ROOT, "movies", name + ".mp4"), y0, y1, y1 + 6, 541)
    old = R.smooth((en > 20) & (jp > 150))
    os.makedirs(os.path.join(ROOT, "presence"), exist_ok=True)
    np.savez(os.path.join(ROOT, "presence", name + ".npz"), tl=tl, st=st, old=old)
    return name, len(tl), len(old), int(old.sum())


if __name__ == "__main__":
    v = sys.argv[1:]
    jobs = [(v[i], int(v[i + 1]), int(v[i + 2])) for i in range(0, len(v), 3)]
    with Pool(4) as p:
        for r in p.imap_unordered(job, jobs):
            print(r, flush=True)
