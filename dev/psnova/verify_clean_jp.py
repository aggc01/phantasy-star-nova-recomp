"""Verify the v2-cleaned movies (written 2026-11-18 evening): frame count, duration, audio stream copy, and RESIDUE: the
detector of remove_jp_subs_v2.py run again on the cleaned movie; frames still over the threshold are listed as runs and a
before/after sheet of the first frames of the worst runs is written (residue_<name>.png).
  python verify_clean_jp.py   (4 processes; run from anywhere)"""
import os, re, subprocess, sys
import cv2, numpy as np
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import remove_jp_subs_v2 as V
D = os.path.join(HERE, '..', '..', 'dump', 'psnova-l10n')
bands = {'MP00_000_000': (470, 497, 350), 'MP00_000_010': (472, 499, 350), 'MP00_010_050': (470, 496, 350),
         'MP06_030_040': (470, 497, 350), 'MP06_030_050': (470, 497, 350), 'MP06_030_070': (470, 497, 350),
         'MP09_040_040': (464, 491, 700), 'MP09_040_070': (470, 497, 350)}


def info(p):
    t = subprocess.run([V.FFMPEG, '-hide_banner', '-i', p], capture_output=True, text=True).stderr
    return re.search(r'Duration: (\S+),', t).group(1), ('Audio: aac' in t)


def job(n):
    y0, y1, thr = bands[n]
    a, b = os.path.join(D, 'movies_jp', n + '.mp4'), os.path.join(D, 'movies_clean_jp', n + '.mp4')
    ca, cb = cv2.VideoCapture(a), cv2.VideoCapture(b)
    fa, fb = int(ca.get(7)), int(cb.get(7))
    ia, ib = info(a), info(b)
    kc = np.array([int(V.keep_pieces(p45).sum()) for k, f, p30, p45 in V.scan(b, y0, y1)])
    before = np.load(os.path.join(D, f'c2_{n}.npz'))
    res = kc > thr
    runs = []; k = 0
    while k < len(res):
        if res[k]:
            j = k
            while j < len(res) and res[j]: j += 1
            if j - k >= 6: runs.append((k, j - 1, int(kc[k:j].max())))
            k = j
        else:
            k += 1
    # sheet: first frame of up to 10 residue runs, original on top of cleaned
    rows = []
    for (s, e, m) in sorted(runs, key=lambda r: -(r[1] - r[0]))[:10]:
        k = (s + e) // 2
        ca.set(1, k); cb.set(1, k); _, A = ca.read(); _, B = cb.read()
        crop = np.vstack([A[y0 - 20:y1 + 30], B[y0 - 20:y1 + 30]])
        cv2.putText(crop, f'{k} run {s}-{e}', (4, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        rows.append(crop)
    if rows: cv2.imwrite(os.path.join(D, f'residue_{n}.png'), np.vstack(rows))
    present = before['present']
    return (n, fa, fb, ia, ib, int(present.sum()), int(res.sum()), runs)


if __name__ == '__main__':
    with Pool(4) as p:
        for n, fa, fb, ia, ib, pres, resid, runs in p.imap_unordered(job, list(bands)):
            print(f'{n}: frames {fa}/{fb} {"OK" if fa == fb else "MISMATCH"}, duration {ia[0]}/{ib[0]}, audio {ia[1]}/{ib[1]}, '
                  f'cleaned frames {pres}, residue frames {resid}, residue runs>=6: {len(runs)} {runs[:8]}', flush=True)
