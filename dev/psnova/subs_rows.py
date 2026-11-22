"""Where are the burned-in subtitle lines? For each movie, sample every Nth frame, mark 'text-like' pixels
(near-white with a dark pixel within 2 px = outlined subtitle fill) and print which rows hold them.
Usage: python subs_rows.py movie.mp4 [...]   (written 2026-11-18, docs/psnova/localization-notes.md)"""
import sys, cv2, numpy as np
from multiprocessing import Pool

K = np.ones((5, 5), np.uint8)

def textlike(frame):
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    white = g > 215
    dark = cv2.erode(g, K) < 70          # a dark pixel within 2 px
    return white & dark

def analyze(path, step=15):
    c = cv2.VideoCapture(path)
    n = 0; used = 0
    rows = np.zeros(544, np.int64)       # frames in which the row has >= 10 text-like pixels
    while True:
        ok = c.grab()
        if not ok: break
        if n % step == 0:
            ok, f = c.retrieve()
            if ok:
                m = textlike(f)
                rows += (m.sum(axis=1) >= 10)
                used += 1
        n += 1
    return path, n, used, rows

if __name__ == '__main__':
    with Pool(4) as p:
        for path, n, used, rows in p.imap_unordered(analyze, sys.argv[1:]):
            # runs of rows above 5% of sampled frames
            thr = max(3, used * 0.05)
            runs = []; start = None
            for y in range(544):
                if rows[y] >= thr and start is None: start = y
                if (rows[y] < thr or y == 543) and start is not None:
                    runs.append((start, y - 1, int(rows[start:y].max()))); start = None
            print(f'{path.split("/")[-1]}: frames={n} sampled={used} runs(y0,y1,peak)={runs}', flush=True)
