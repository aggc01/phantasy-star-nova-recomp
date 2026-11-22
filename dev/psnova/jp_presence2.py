"""Stronger base-only presence: pixels that are text-like (white fill + dark outline) in >= K of the 2W+1 frames around
each frame. Burned-in text is static for seconds, scene detail moves. Saves w11 counts into presence/<name>.npz as 'win'.
  python jp_presence2.py NAME Y0 Y1 [...]"""
import os, sys
import numpy as np, cv2
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import remove_jp_subs as R
ROOT = r"F:\Antigravity Proj\Recomp-decomp\Phantasy Star Nova Recomp\dump\psnova-l10n"
W = 5

def job(a):
    name, y0, y1 = a
    c = cv2.VideoCapture(os.path.join(ROOT, "movies_jp", name + ".mp4"))
    T = []
    while True:
        ok, f = c.read()
        if not ok: break
        T.append(R.textlike(f[y0:y1]).astype(np.uint8))
    T = np.array(T)                      # n x h x w
    n = len(T)
    cs = np.concatenate([np.zeros((1,) + T.shape[1:], np.int16), np.cumsum(T, axis=0, dtype=np.int16)])
    win = np.zeros((n, 3), np.int64)     # pixels present in >= 6, 8, 10 of 11 frames
    for k in range(n):
        a0, a1 = max(0, k - W), min(n, k + W + 1)
        s = cs[a1] - cs[a0]
        need = lambda q: q * (a1 - a0) // 11
        win[k] = [(s >= max(2, need(6))).sum(), (s >= max(2, need(8))).sum(), (s >= max(2, need(10))).sum()]
    d = dict(np.load(os.path.join(ROOT, "presence", name + ".npz")))
    d["win"] = win
    np.savez(os.path.join(ROOT, "presence", name + ".npz"), **d)
    return name, n

if __name__ == "__main__":
    v = sys.argv[1:]
    jobs = [(v[i], int(v[i + 1]), int(v[i + 2])) for i in range(0, len(v), 3)]
    with Pool(4) as p:
        for r in p.imap_unordered(job, jobs): print(r, flush=True)
