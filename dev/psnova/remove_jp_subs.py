"""Remove the Japanese subtitle line burned into a Phantasy Star Nova story movie (written 2026-11-18).

Why: the English fan patch burned its subtitles into the movies *under* Sega's burned-in Japanese line.
Notes: docs/psnova/localization-notes.md ("Native English").

How: pass 1 counts, per frame, the strong thin strokes (|gray - 9x9 median| > 28) inside the Japanese band;
frames over a threshold hold subtitle text, smoothed in time (gaps filled, specks dropped, a few frames added
each side for fades). Pass 2 inpaints those strokes (mask dilated) with OpenCV Telea inside the band only, and pipes raw frames
to ffmpeg (libx264, audio stream copied from the original).

  python remove_jp_subs.py in.mp4 out.mp4 --y0 470 --y1 497 [--thr 700] [--preview prefix]

The band must stay clear of the English line (check docs). --preview writes before/after strips of a few
subtitle frames (prefix_N.png) and does not encode.
"""
import argparse, os, subprocess, sys
import cv2
import numpy as np

FFMPEG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', 'ffmpeg.exe')   # the project's own copy (ffmpeg-static 6.x: libx264, harfbuzz, fribidi)   # has libx264 + mp4 (the metroidprimeport one has not)
W, H = 960, 544


def strokes(band, thr):
    g = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    d = cv2.absdiff(g, cv2.medianBlur(g, 9))
    return d > thr


D3 = np.ones((3, 3), np.uint8)


def persist(cur, other):
    """strokes of this frame that sit (within 1 px) on strokes of a neighbouring frame: burned-in text does not move,
    scene detail does (added after the first run damaged moving backgrounds, see notes)."""
    return cur & (cv2.dilate(other.astype(np.uint8), D3) > 0)


K5 = np.ones((5, 5), np.uint8)


def textlike(band):
    """white fill with a black outline within 2 px: the English subtitle (always white on black, any background)"""
    g = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    return (g > 205) & (cv2.erode(g, K5) < 80)


def count_pass(path, y0, y1, e0, e1):
    """per frame: (persistent strokes in the Japanese band y0..y1, persistent English-like text pixels in e0..e1).
    The English line is burned in at the same times as the Japanese one, so it tells when Japanese text exists."""
    c = cv2.VideoCapture(path)
    S, E = [], []
    while True:
        ok, f = c.read()
        if not ok:
            break
        S.append(strokes(f[y0:y1], 20))
        E.append(textlike(f[e0:e1]))
    n = len(S)
    jp = np.zeros(n, np.int64)
    en = np.zeros(n, np.int64)
    for k in range(n):
        for A, out in ((S, jp), (E, en)):
            nb = np.zeros_like(A[k])
            if k > 0:
                nb |= A[k - 1]
            if k + 1 < n:
                nb |= A[k + 1]
            out[k] = int(persist(A[k], nb).sum())
    return jp, en


def smooth(present, fill=8, minrun=10, pad=4):
    p = present.copy()
    n = len(p)
    # fill short gaps between present frames
    i = 0
    while i < n:
        if not p[i]:
            j = i
            while j < n and not p[j]:
                j += 1
            if i > 0 and j < n and (j - i) <= fill:
                p[i:j] = True
            i = j
        else:
            i += 1
    # drop short runs
    i = 0
    while i < n:
        if p[i]:
            j = i
            while j < n and p[j]:
                j += 1
            if (j - i) < minrun:
                p[i:j] = False
            i = j
        else:
            i += 1
    # pad each side (fades)
    out = p.copy()
    for k in range(1, pad + 1):
        out[k:] |= p[:-k]
        out[:-k] |= p[k:]
    return out


def clean(frame, y0, y1, nb_frames=()):
    m0 = max(0, y0 - 8)
    m1 = y1                       # nothing below the band is used: the English line's black outline must not bleed in
    crop = frame[m0:m1].copy()
    s = strokes(crop, 12)
    if nb_frames:                      # keep only strokes that also exist in a neighbouring frame
        nb = np.zeros_like(s)
        for g in nb_frames:
            nb |= strokes(g[m0:m1], 12)
        s = persist(s, nb)
    s[:y0 - m0] = False        # only inside the band
    s[y1 - m0:] = False
    mask = cv2.dilate(s.astype(np.uint8) * 255, np.ones((9, 9), np.uint8))
    mask[:y0 - m0] = 0
    mask[y1 - m0:] = 0
    res = cv2.inpaint(crop, mask, 3, cv2.INPAINT_TELEA)
    out = frame.copy()
    out[m0:m1] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--y0', type=int, required=True)
    ap.add_argument('--y1', type=int, required=True)
    ap.add_argument('--thr', type=int, default=150, help='min persistent Japanese-band strokes')
    ap.add_argument('--en0', type=int, help='first row of the English line search (default y1+6)')
    ap.add_argument('--enthr', type=int, default=150, help='min persistent English text pixels')
    ap.add_argument('--crf', type=int, default=19)
    ap.add_argument('--preview')
    ap.add_argument('--counts', action='store_true', help='print per-15th-frame persistent stroke counts and stop')
    a = ap.parse_args()

    e0 = a.en0 if a.en0 else a.y1 + 6
    jp, en = count_pass(a.src, a.y0, a.y1, e0, 541)
    if a.counts:
        print('jp', list(map(int, jp[::15]))); print('en', list(map(int, en[::15]))); return
    present = smooth((en > a.enthr) & (jp > a.thr))
    n = len(jp)
    print(f'{a.src}: {n} frames, text frames {int(present.sum())} ({100*present.mean():.0f}%)', flush=True)

    c = cv2.VideoCapture(a.src)
    fps = c.get(cv2.CAP_PROP_FPS)

    if a.preview:
        idx = np.flatnonzero(present)
        pick = idx[np.linspace(0, len(idx) - 1, 6).astype(int)] if len(idx) else []
        rows = []
        for k in pick:
            c.set(cv2.CAP_PROP_POS_FRAMES, int(k) - 1)
            _, f0 = c.read(); _, f = c.read(); _, f2 = c.read()
            rows.append(np.vstack([f[440:544], clean(f, a.y0, a.y1, (f0, f2))[440:544]]))
        if rows:
            cv2.imwrite(a.preview + '.png', np.vstack(rows))
        print('preview written')
        return

    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y',
           '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps:.6f}', '-i', '-',
           '-i', a.src, '-map', '0:v', '-map', '1:a?',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', str(a.crf), '-pix_fmt', 'yuv420p',
           '-profile:v', 'high', '-level', '4.0', '-c:a', 'copy', '-movflags', '+faststart', a.dst]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    k = 0
    prev = None
    ok, cur = c.read()
    while ok:
        ok2, nxt = c.read()
        out = cur
        if k < n and present[k]:
            out = clean(cur, a.y0, a.y1, tuple(g for g in (prev, nxt if ok2 else None) if g is not None))
        p.stdin.write(out.tobytes())
        prev, cur, ok = cur, nxt, ok2
        k += 1
    p.stdin.close()
    rc = p.wait()
    print(f'{a.dst}: wrote {k} frames (source {n}), ffmpeg rc {rc}', flush=True)
    sys.exit(0 if (rc == 0 and k == n) else 1)


if __name__ == '__main__':
    main()
