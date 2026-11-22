"""Remove the Japanese subtitle line burned into an ORIGINAL Phantasy Star Nova story movie (v2, written 2026-11-18 evening).

Why v2: v1 (remove_jp_subs.py) keyed on the English line the fan patch burned in under Sega's Japanese line; the Japanese-only
build has no English line, and v1's white-with-dark-outline test misses the text on bright backgrounds (it has only a soft
shadow there). Notes and the lessons: docs/psnova/localization-notes.md ("v2").

What the subtitle looks like: near-white (desaturated), thin strokes (glyphs <= ~22 px), pixel-static for the whole line (it
appears and disappears with a short fade), with a soft shadow. Backgrounds can be golden/red glow lines (saturated, so not
"white") or white costume parts (large, so not thin).

Signal: top-hat (9x9 ellipse) of the per-pixel MIN of B,G,R ("whiteness") in the band y0-3..y1+3. A pixel is "persistent" when
it is above the threshold in >= 8 of the 11 frames around the frame; persistent pixels are grouped in connected pieces and
tall vertical structures (a 26-px vertical opening: legs, glow lines, edges) are removed from them. Detection uses threshold 45, the cleaning mask threshold 30.

Presence per frame = the kept pixel count (threshold 45) is over --thr (300), smoothed in time (gaps <= 8 frames filled, runs
< 12 dropped, 4 frames added each side), OR (with --ref) the fan-patched copy of the movie shows its burned-in English line
(patched minus original in rows 495..535 > 45 in > 150 pixels, aligned per frame over -1/0/+1 because the fan encode has one
frame more or less): the English line is only there when the Japanese one is. A wrong "present" costs little: the mask only
holds white, glyph-sized, static pieces.

Cleaning: per present frame the mask is the kept pieces (threshold 30) dilated 9x9, clipped to y0..y1; cv2 Telea inpaint
(radius 3) on the crop y0-8..y1+8 (the original has no second line below); frames go raw to ffmpeg-static (libx264 CRF 19,
high, level 4.0, audio copied). Exit 1 unless frames in == frames out.

  python remove_jp_subs_v2.py in.mp4 out.mp4 --y0 470 --y1 497 [--ref patched.mp4] [--preview prefix] [--counts out.npz]
"""
import argparse, os, subprocess, sys
import cv2
import numpy as np

FFMPEG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', 'ffmpeg.exe')   # the project's own copy (ffmpeg-static 6.x: libx264, harfbuzz, fribidi)
W, H = 960, 544
KT = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
K9 = np.ones((9, 9), np.uint8)
HALF = 5          # window = 11 frames
TH_DET, TH_MASK = 45, 30


def tophat(frame, y0, y1):
    m = frame[y0 - 3:y1 + 3].min(axis=2)
    return cv2.morphologyEx(m, cv2.MORPH_TOPHAT, KT)


KV = np.ones((26, 1), np.uint8)
K3 = np.ones((3, 3), np.uint8)


def keep_pieces(pm):
    """persistent pixels minus tall vertical structures: a 26-px vertical opening finds legs, glow lines and edges that cross
    the whole 33-row crop; a glyph (<= ~22 px tall) cannot hold one. (Whole-piece filtering by size dropped text that had
    merged with such a structure, 2026-11-18.)"""
    m = pm.astype(np.uint8)
    v = cv2.dilate(cv2.morphologyEx(m, cv2.MORPH_OPEN, KV), K3)
    return (m > 0) & (v == 0)


def scan(path, y0, y1):
    """yields (k, frame, persistent30, persistent45): windows of 11 frames centred on k (shorter at the ends)"""
    c = cv2.VideoCapture(path)
    buf = {}                     # k -> (frame, th)
    S30 = S45 = None
    nread = [0]

    def readone():
        ok, f = c.read()
        if not ok: return False
        th = tophat(f, y0, y1)
        buf[nread[0]] = (f, th); nread[0] += 1
        return True

    def add(k, sign):
        nonlocal S30, S45
        th = buf[k][1]
        a, b = (th > TH_MASK).astype(np.int16), (th > TH_DET).astype(np.int16)
        if S30 is None: S30 = np.zeros_like(a); S45 = np.zeros_like(b)
        S30 += sign * a; S45 += sign * b

    for _ in range(HALF + 1):
        if not readone(): break
    for k in range(nread[0]): add(k, 1)
    lo, hi = 0, nread[0] - 1
    k = 0
    while k < nread[0]:
        w = hi - lo + 1
        need = max(2, 8 * w // 11)
        yield k, buf[k][0], S30 >= need, S45 >= need
        k += 1
        # slide the window to [k-HALF, k+HALF]
        if readone():
            add(nread[0] - 1, 1); hi = nread[0] - 1
        if k - HALF - 1 >= lo and (k - HALF - 1) in buf:
            add(k - HALF - 1, -1); lo = k - HALF
        for j in [j for j in buf if j < k - HALF - 1]: del buf[j]


def smooth(present, fill=8, minrun=12, pad=4):
    p = present.copy(); n = len(p)
    i = 0
    while i < n:
        if not p[i]:
            j = i
            while j < n and not p[j]: j += 1
            if i > 0 and j < n and (j - i) <= fill: p[i:j] = True
            i = j
        else:
            i += 1
    i = 0
    while i < n:
        if p[i]:
            j = i
            while j < n and p[j]: j += 1
            if (j - i) < minrun: p[i:j] = False
            i = j
        else:
            i += 1
    out = p.copy()
    for k in range(1, pad + 1):
        out[k:] |= p[:-k]; out[:-k] |= p[k:]
    return out


def english_presence(base, patched):
    """per frame of the original: is the fan patch's English line on screen (patched - original in rows 495..535)"""
    cb, cp = cv2.VideoCapture(base), cv2.VideoCapture(patched)
    P = []
    while True:
        ok, f = cp.read()
        if not ok: break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.int16)
        P.append((g[:430:4, ::4].copy(), g[495:535].copy()))      # (alignment sample, English rows): all frames would be GBs
    en = []
    k = 0
    while True:
        ok, f = cb.read()
        if not ok: break
        b = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.int16)
        best = None
        for o in (-1, 0, 1):
            j = min(max(k + o, 0), len(P) - 1)
            e = np.abs(P[j][0] - b[:430:4, ::4]).mean()
            if best is None or e < best[0]: best = (e, j)
        d = np.abs(P[best[1]][1] - b[495:535])
        en.append(int((d > 45).sum()))
        k += 1
    return np.array(en)


def clean(frame, y0, y1, pm30):
    m0, m1 = y0 - 8, min(H, y1 + 8)
    kept = keep_pieces(pm30)                     # rows y0-3 .. y1+3
    full = np.zeros((m1 - m0, W), np.uint8)
    full[(y0 - 3) - m0:(y0 - 3) - m0 + kept.shape[0]] = kept.astype(np.uint8) * 255
    full = cv2.dilate(full, K9)
    full[:y0 - m0] = 0; full[y1 - m0:] = 0
    crop = frame[m0:m1].copy()
    res = cv2.inpaint(crop, full, 3, cv2.INPAINT_TELEA)
    out = frame.copy(); out[m0:m1] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst', nargs='?')
    ap.add_argument('--y0', type=int, required=True); ap.add_argument('--y1', type=int, required=True)
    ap.add_argument('--thr', type=int, default=300)
    ap.add_argument('--ref', help='the fan-patched copy of the same movie (English line timing)')
    ap.add_argument('--crf', type=int, default=19)
    ap.add_argument('--preview'); ap.add_argument('--counts')
    a = ap.parse_args()

    kc = []
    for k, f, p30, p45 in scan(a.src, a.y0, a.y1):
        kc.append(int(keep_pieces(p45).sum()))
    kc = np.array(kc); n = len(kc)
    cand = smooth(kc > a.thr)
    en = english_presence(a.src, a.ref) if a.ref else np.zeros(n, np.int64)
    enp = smooth(en > 150, fill=12, minrun=8, pad=2) if a.ref else np.zeros(n, bool)
    present = cand | enp
    if a.counts: np.savez(a.counts, kc=kc, en=en, cand=cand, present=present)
    print(f'{a.src}: {n} frames; detector {int(cand.sum())}, English line {int(enp.sum())}, union {int(present.sum())} '
          f'({100 * present.mean():.0f}%)', flush=True)

    if a.preview:
        pick = set()
        idx = np.flatnonzero(present)
        if len(idx): pick |= set(idx[np.linspace(0, len(idx) - 1, 7).astype(int)].tolist())
        edges = [k for k in range(1, n) if present[k] != present[k - 1]]
        pick |= set(edges[:3]) | {min(n - 1, e + 5) for e in edges[:2]}
        rows = []
        for k, f, p30, p45 in scan(a.src, a.y0, a.y1):
            if k in pick:
                after = clean(f, a.y0, a.y1, p30) if present[k] else f
                lab = np.vstack([f[440:544], after[440:544]])
                cv2.putText(lab, f'{k} {"T" if present[k] else "-"}', (5, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                rows.append(lab)
        cv2.imwrite(a.preview + '.png', np.vstack(rows))
        print('preview written', flush=True)
        return

    cap = cv2.VideoCapture(a.src); fps = cap.get(cv2.CAP_PROP_FPS)
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y',
           '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps:.6f}', '-i', '-',
           '-i', a.src, '-map', '0:v', '-map', '1:a?',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', str(a.crf), '-pix_fmt', 'yuv420p',
           '-profile:v', 'high', '-level', '4.0', '-c:a', 'copy', '-movflags', '+faststart', a.dst]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    wrote = 0
    for k, f, p30, p45 in scan(a.src, a.y0, a.y1):
        out = clean(f, a.y0, a.y1, p30) if present[k] else f
        p.stdin.write(out.tobytes()); wrote += 1
    p.stdin.close(); rc = p.wait()
    print(f'{a.dst}: wrote {wrote} frames (source {n}), ffmpeg rc {rc}', flush=True)
    sys.exit(0 if (rc == 0 and wrote == n) else 1)


if __name__ == '__main__':
    main()
