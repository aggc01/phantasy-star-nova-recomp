"""Remove the Japanese subtitle line burned into an ORIGINAL Phantasy Star Nova story movie (v3, written 2026-11-19).

Why v3: v2 (remove_jp_subs_v2.py) built its mask PER FRAME from pixels that are white in >= 8 of the 11 frames around the
frame. At the first and last 2-3 frames of every line (and during any fade) fewer than 8 of the 11 frames hold the text, so
the mask there was empty or partial and the text stayed: I saw "the Japanese subtitles showing for a split second"
(docs/psnova/localization-notes.md, "Movies v2 installed and tested", flaw 1). v2 also filled every mask with Telea, which
smears (flaw 2). Notes: docs/psnova/movie-cleaning-v3.md.

What v3 does:
1. Detection is v2's (top-hat 9x9 of the per-pixel MIN of B,G,R in rows y0-3..y1+3; persistent = above the threshold in
   >= 8 of 11 frames; tall vertical structures removed; presence = kept pixels (threshold 45) > --thr, smoothed, OR the fan
   copy's English line with --ref).
2. LINES: inside the present frames, the "core" frames (kept pixels > --thr) are split into lines where the persistent
   mask changes (a gap, or IoU of consecutive persistent masks < 0.5); lines of the same text split by a short gap are
   merged again. Present runs without any core frame (weak dots-only lines) become one line each.
3. One mask per line: pixels in the persistent mask (threshold 30) in >= 40 % of the line's core frames.
4. The mask is used for EVERY core frame and is extended outwards: as long as the mean whiteness inside the line mask
   stays above background + 15 % of the line's strength (fades), and at least --margin (8) frames each side; into another
   line's core frames at most --margin frames. Frames covered by two lines get the union of both masks.
4b. Background cut: mask pixels white in >= 80 % of the 15 frames before AND the 15 after the line's masked frames are
   still background (patterns, stars), not text; they leave the line mask and the safety net (--no-bgcut keeps them).
5. Fill (dilated 9x9 mask, clipped to rows y0-1..y1; the text lies inside y0..y1): for each frame, candidate background frames are the frames just
   outside the lines that cover it (up to 60 frames each side, every 2nd). Candidates whose band (outside both masks)
   matches this frame closely (mean abs diff of a 4x downsampled band < --static) are kept, at most 7, and each masked
   pixel takes the per-pixel median of the candidates that do not mask it (nor show a white thin pixel there), plus the region's colour offset (measured on a
   ring around the region). A mask region whose ring does not match the median (moving background), and pixels no
   candidate sees, are filled with Telea (radius 3), as in v2.
6. Output: frames raw to ffmpeg-static, libx264 CRF 19, preset medium, high, level 4.0, yuv420p, audio copied, faststart
   (the same settings as v2). Exit 1 unless frames in == frames out.

The process sets itself to IDLE priority (ffmpeg inherits it) unless --normal is given.

  python remove_jp_subs_v3.py in.mp4 out.mp4 --y0 470 --y1 497 [--thr 350] [--ref patched.mp4] [--lines out.npz]
"""
import argparse, ctypes, os, subprocess, sys, warnings
import cv2
import numpy as np

FFMPEG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', 'ffmpeg.exe')   # the project's own copy (ffmpeg-static 6.x: libx264, harfbuzz, fribidi)
W, H = 960, 544
KT = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
K9 = np.ones((9, 9), np.uint8)
K3 = np.ones((3, 3), np.uint8)
K5 = np.ones((5, 5), np.uint8)
KV = np.ones((26, 1), np.uint8)
KRING = np.ones((13, 13), np.uint8)
HALF = 5          # persistence window = 11 frames
TH_DET, TH_MASK = 45, 30
POOL, POOL_STEP, MAXC = 60, 2, 7


def idle():
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)   # IDLE_PRIORITY_CLASS
    except Exception:
        pass


def tophat(frame, y0, y1):
    m = frame[y0 - 3:y1 + 3].min(axis=2)
    return cv2.morphologyEx(m, cv2.MORPH_TOPHAT, KT)


def keep_pieces(pm):
    """persistent pixels minus tall vertical structures (v2's rule: a 26-px vertical opening finds legs, glow lines and edges)"""
    m = pm.astype(np.uint8)
    v = cv2.dilate(cv2.morphologyEx(m, cv2.MORPH_OPEN, KV), K3)
    return (m > 0) & (v == 0)


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
    """v2's: per frame of the original, is the fan patch's English line on screen (patched - original in rows 495..535)"""
    cb, cp = cv2.VideoCapture(base), cv2.VideoCapture(patched)
    P = []
    while True:
        ok, f = cp.read()
        if not ok: break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.int16)
        P.append((g[:430:4, ::4].copy(), g[495:535].copy()))
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


def runs_of(b):
    out = []; i = 0; n = len(b)
    while i < n:
        if b[i]:
            j = i
            while j < n and b[j]: j += 1
            out.append((i, j - 1)); i = j
        else:
            i += 1
    return out


def iou(a, b):
    u = np.count_nonzero(a | b)
    return np.count_nonzero(a & b) / u if u else 1.0


def read_all(path, y0, y1, keep_crop=True):
    """TH (n, rows y0-3..y1+3, W) uint8 and, if asked, CROP (n, rows y0-8..y1+8, W, 3) uint8"""
    c = cv2.VideoCapture(path)
    th, cr = [], []
    m0, m1 = y0 - 8, min(H, y1 + 8)
    while True:
        ok, f = c.read()
        if not ok: break
        th.append(tophat(f, y0, y1))
        if keep_crop: cr.append(f[m0:m1].copy())
    return np.array(th), (np.array(cr) if keep_crop else None)


def persistent(TH):
    """K30 (n,h,W) bool = kept pieces of the threshold-30 persistent mask; kc45 (n,) = kept pixels of the threshold-45 one"""
    n = len(TH)
    S30 = np.zeros(TH.shape[1:], np.int16); S45 = np.zeros(TH.shape[1:], np.int16)
    K30 = np.zeros(TH.shape, bool); kc = np.zeros(n, np.int64)
    lo, hi = 0, -1
    for k in range(n):
        a, b = max(0, k - HALF), min(n - 1, k + HALF)
        while hi < b:
            hi += 1; S30 += TH[hi] > TH_MASK; S45 += TH[hi] > TH_DET
        while lo < a:
            S30 -= TH[lo] > TH_MASK; S45 -= TH[lo] > TH_DET; lo += 1
        w = b - a + 1
        need = max(2, 8 * w // 11)
        K30[k] = keep_pieces(S30 >= need)
        kc[k] = int(keep_pieces(S45 >= need).sum())
    return K30, kc


def find_lines(TH, K30, kc, present, thr, margin=8, maxext=25, bgcut=True):
    """-> list of dicts: cs, ce (core frames), a, b (masked frames), mask (bool, TH rows)"""
    n = len(TH)
    core = (kc > thr) & present
    D3 = lambda m: cv2.dilate(m.astype(np.uint8), K3) > 0
    segs = []                                 # (cs, ce, weak)
    for (ps, pe) in runs_of(present):
        cr = [(s + ps, e + ps) for (s, e) in runs_of(core[ps:pe + 1])]
        if not cr:
            segs.append([ps, pe, True]); continue
        for (s, e) in cr:
            st = s
            for k in range(s + 1, e + 1):
                A_, B_ = K30[k - 1], K30[k]
                gone = np.count_nonzero(A_ & ~D3(B_)); new = np.count_nonzero(B_ & ~D3(A_))
                if gone > 0.3 * max(1, np.count_nonzero(A_)) or new > 0.3 * max(1, np.count_nonzero(B_)):
                    segs.append([st, k - 1, False]); st = k
            segs.append([st, e, False])
    vote = lambda s, e, weak: K30[s:e + 1].mean(axis=0) >= (0.3 if weak else 0.4)
    # short pieces (ramps at a line's start/end, flashes) join the neighbour whose mask contains theirs
    changed = True
    while changed:
        changed = False
        for i, S in enumerate(segs):
            if S[2] or S[1] - S[0] + 1 >= 6: continue
            ms = vote(*S); ns = max(1, np.count_nonzero(ms)); best = None
            for jn in (i - 1, i + 1):
                if 0 <= jn < len(segs) and not segs[jn][2]:
                    N = segs[jn]
                    if max(N[0], S[0]) - min(N[1], S[1]) > 3: continue      # gap > 2 frames
                    c = np.count_nonzero(ms & D3(vote(*N))) / ns
                    if c > 0.5 and (best is None or c > best[0]): best = (c, jn)
            if best:
                N = segs[best[1]]; N[0], N[1] = min(N[0], S[0]), max(N[1], S[1]); del segs[i]; changed = True; break
    # the same text split by a short gap (a flash, a dip under the threshold)
    merged = []
    for S in segs:
        if merged and not S[2] and not merged[-1][2] and S[0] - merged[-1][1] <= 6                 and iou(vote(*merged[-1]), vote(*S)) > 0.6:
            merged[-1][1] = S[1]; continue
        merged.append(S)
    lines = []
    for (s, e, weak) in merged:
        m = vote(s, e, weak)
        if m.sum(): lines.append(dict(cs=s, ce=e, mask=m, weak=weak))
    # extension: fades + margin
    for i, L in enumerate(lines):
        m = L['mask']; cs, ce = L['cs'], L['ce']
        lo_lim = lines[i - 1]['ce'] + 1 if i > 0 else 0
        hi_lim = lines[i + 1]['cs'] - 1 if i + 1 < len(lines) else n - 1
        j0, j1 = max(0, cs - maxext - 15), min(n - 1, ce + maxext + 15)
        s = {j: float(TH[j][m].mean()) for j in range(j0, j1 + 1)}
        s_core = float(np.median([s[j] for j in range(cs, ce + 1)]))
        before = [s[j] for j in range(j0, cs)]; after = [s[j] for j in range(ce + 1, j1 + 1)]
        bgs = [np.percentile(x, 20) for x in (before, after) if len(x) >= 5]
        s_bg = min(bgs) if bgs else 0.0
        s_t = s_bg + 0.15 * max(0.0, s_core - s_bg)
        fb = 0
        while fb < maxext and cs - fb - 1 >= j0 and s[cs - fb - 1] > s_t: fb += 1
        fa = 0
        while fa < maxext and ce + fa + 1 <= j1 and s[ce + fa + 1] > s_t: fa += 1
        L['fade_before'], L['fade_after'] = fb, fa
        # into a neighbour's core frames at most `margin` frames (those frames then get the union of both masks): a
        # neighbour can be a false line (background pieces) whose core starts while this line's text is still on screen
        L['a'] = max(cs - max(margin, fb + 2), min(lo_lim, cs - margin), 0)
        L['b'] = min(ce + max(margin, fa + 2), max(hi_lim, ce + margin), n - 1)
        L['s_core'], L['s_bg'] = s_core, s_bg
    # background cut: a mask pixel that is white in >= 80 % of the 15 frames before the line's masked frames AND of the 15
    # after is the still background (pattern, stars), not this line's text: it is taken out of the line's mask (and of
    # the per-frame safety net in the line's frames). In still scenes this kept 70 % of the band masked (one wide smear).
    for L in lines:
        if not bgcut:
            L['bg'] = np.zeros_like(L['mask']); continue
        bef = [j for j in range(L['a'] - 15, L['a']) if j >= 0]
        aft = [j for j in range(L['b'] + 1, L['b'] + 16) if j < n]
        if len(bef) >= 8 and len(aft) >= 8:
            L['bg'] = ((TH[bef] > TH_MASK).mean(axis=0) >= 0.8) & ((TH[aft] > TH_MASK).mean(axis=0) >= 0.8)
        else:
            L['bg'] = np.zeros_like(L['mask'])
        L['mask_full'] = L['mask']
        L['mask'] = L['mask'] & ~L['bg']
    return lines


def analyse(src, y0, y1, thr, ref=None, keep_crop=True, margin=8, log=print, bgcut=True):
    TH, CROP = read_all(src, y0, y1, keep_crop)
    n = len(TH)
    K30, kc = persistent(TH)
    cand = smooth(kc > thr)
    en = english_presence(src, ref) if ref else np.zeros(n, np.int64)
    enp = smooth(en > 150, fill=12, minrun=8, pad=2) if ref else np.zeros(n, bool)
    present = cand | enp
    lines = find_lines(TH, K30, kc, present, thr, margin=margin, bgcut=bgcut)
    log(f'{src}: {n} frames; present {int(present.sum())}, lines {len(lines)} '
        f'(weak {sum(L["weak"] for L in lines)}), masked frames {len(set(j for L in lines for j in range(L["a"], L["b"] + 1)))}')
    return dict(n=n, TH=TH, CROP=CROP, K30=K30, kc=kc, present=present, lines=lines, en=en)


class Filler:
    def __init__(self, A, y0, y1, static=4.0):
        self.A, self.y0, self.y1, self.static = A, y0, y1, static
        self.m0, self.m1 = y0 - 8, min(H, y1 + 8)
        hc = self.m1 - self.m0
        self.off = (y0 - 3) - self.m0           # TH row 0 in crop rows
        self.c0, self.c1 = (y0 - 1) - self.m0, (y1 + 1) - self.m0     # the mask is clipped to rows y0-1..y1 (v2: y0..y1-1)
        n = A['n']
        self.cover = [[] for _ in range(n)]
        self.incore = np.zeros(n, bool); self._pf = {}
        for L in A['lines']: self.incore[L['cs']:L['ce'] + 1] = True
        self.incore |= A['present']                # v2 cleaned every present frame with its own pieces: keep that
        self.shape = (hc, W)
        for i, L in enumerate(A['lines']):
            full = np.zeros((hc, W), np.uint8)
            full[self.off:self.off + L['mask'].shape[0]] = L['mask'].astype(np.uint8) * 255
            full = cv2.dilate(full, K9)
            full[:self.c0] = 0; full[self.c1:] = 0
            L['dil'] = full > 0
            L['dil4'] = cv2.resize(full, (W // 4, (hc + 3) // 4), interpolation=cv2.INTER_AREA) > 0
            for j in range(L['a'], L['b'] + 1): self.cover[j].append(i)
        C = A['CROP']
        self.DS = np.array([cv2.resize(C[k], (W // 4, (hc + 3) // 4), interpolation=cv2.INTER_AREA) for k in range(n)],
                           np.int16)
        self.stats = dict(frames=0, px=0, px_temporal=0, px_telea=0)

    def umask(self, k, key='dil'):
        """union of the dilated masks of the lines covering frame k; in a line's core frames also that frame's own
        persistent pieces (v2's per-frame mask), as a safety net for text the line vote missed"""
        cv = self.cover[k]
        if not cv and not (key == 'dil' and self.incore[k]): return None
        m = self.A['lines'][cv[0]][key].copy() if cv else np.zeros(self.shape, bool)
        for i in cv[1:]: m |= self.A['lines'][i][key]
        if key == 'dil' and self.incore[k]:
            if k not in self._pf:
                full = np.zeros(m.shape, np.uint8)
                K = self.A['K30'][k].copy()
                for i in cv: K &= ~self.A['lines'][i]['bg']
                full[self.off:self.off + K.shape[0]] = K.astype(np.uint8) * 255
                full = cv2.dilate(full, K9); full[:self.c0] = 0; full[self.c1:] = 0
                if len(self._pf) > 400: self._pf.clear()
                self._pf[k] = full > 0
            m |= self._pf[k]
        return m

    def textlike(self, j):
        """crop-sized mask of candidate frame j's white thin pixels (top-hat > 45, dilated 5x5) inside the mask rows"""
        t = np.zeros(self.shape, np.uint8)
        TH = self.A['TH'][j]
        t[self.off:self.off + TH.shape[0]] = (TH > TH_DET).astype(np.uint8)
        t = cv2.dilate(t, K5)
        t[:self.c0] = 0; t[self.c1:] = 0
        return t > 0

    def fill(self, k):
        """-> cleaned crop (rows y0-8..y1+8) for frame k, or None when no line covers frame k"""
        U = self.umask(k)
        if U is None or not U.any(): return None
        A, C, n = self.A, self.A['CROP'], self.A['n']
        crop = C[k]
        U4 = self.umask(k, 'dil4')
        if U4 is None:
            U4 = cv2.resize(U.astype(np.uint8) * 255, (W // 4, (U.shape[0] + 3) // 4), interpolation=cv2.INTER_AREA) > 0
        pool = set()
        for i in self.cover[k]:
            L = A['lines'][i]
            pool |= set(range(L['a'] - 1, max(-1, L['a'] - 1 - POOL), -POOL_STEP))
            pool |= set(range(L['b'] + 1, min(n, L['b'] + 1 + POOL), POOL_STEP))
        scored = []
        for j in pool:
            if j < 0 or j >= n: continue
            Uj4 = self.umask(j, 'dil4')
            ok = ~U4 if Uj4 is None else ~(U4 | Uj4)
            if ok.sum() < 200: continue
            d = np.abs(self.DS[k] - self.DS[j])[ok].mean()
            if d < self.static: scored.append((d, abs(j - k), j))
        scored.sort()
        chosen = [j for d, dist, j in scored[:MAXC]]
        out = crop.copy()
        hole = U.copy()
        npx = int(U.sum())
        self.stats['frames'] += 1; self.stats['px'] += npx
        if chosen:
            ncomp, lab = cv2.connectedComponents(U.astype(np.uint8), connectivity=8)
            ringall = cv2.dilate(U.astype(np.uint8), KRING) > 0
            sel = ringall                                  # ring pixels + mask pixels
            stack = np.empty((len(chosen), int(sel.sum()), 3), np.float32)
            for ci, j in enumerate(chosen):
                v = C[j][sel].astype(np.float32)
                Uj = self.umask(j)
                Uj = np.zeros(U.shape, bool) if Uj is None else Uj.copy()
                Uj |= self.textlike(j)                 # white thin pixels in a candidate may be text no line covers
                v[Uj[sel]] = np.nan
                stack[ci] = v
            cnt = np.zeros(U.shape, np.int32); cnt[sel] = np.isfinite(stack[..., 0]).sum(axis=0)
            bg = np.zeros(crop.shape, np.float32)
            with np.errstate(all='ignore'), warnings.catch_warnings():
                warnings.simplefilter('ignore')
                bg[sel] = np.nan_to_num(np.nanmedian(stack, axis=0))
            crf = crop.astype(np.float32)
            for r in range(1, ncomp):
                R = lab == r
                ring = (cv2.dilate(R.astype(np.uint8), KRING) > 0) & ~U & (cnt > 0)
                if ring.sum() < 30: continue
                dif = crf[ring] - bg[ring]
                offs = dif.mean(axis=0)
                resid = np.abs(dif - offs).mean()
                if resid > 6.0: continue                   # background not static here: Telea
                Rv = R & (cnt > 0)
                out[Rv] = np.clip(bg[Rv] + offs, 0, 255).astype(np.uint8)
                hole[Rv] = False
        nh = int(hole.sum())
        self.stats['px_telea'] += nh; self.stats['px_temporal'] += npx - nh
        if nh:
            out = cv2.inpaint(out, hole.astype(np.uint8) * 255, 3, cv2.INPAINT_TELEA)
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--y0', type=int, required=True); ap.add_argument('--y1', type=int, required=True)
    ap.add_argument('--thr', type=int, default=350)
    ap.add_argument('--ref', help='the fan-patched copy of the same movie (English line timing)')
    ap.add_argument('--crf', type=int, default=19)
    ap.add_argument('--margin', type=int, default=8)
    ap.add_argument('--static', type=float, default=4.0)
    ap.add_argument('--lines', help='write the line table (npz)')
    ap.add_argument('--no-bgcut', action='store_true', help='keep still-background pixels in the line masks')
    ap.add_argument('--normal', action='store_true', help='do not lower the process priority')
    a = ap.parse_args()
    if not a.normal: idle()
    cv2.setNumThreads(2)

    A = analyse(a.src, a.y0, a.y1, a.thr, a.ref, margin=a.margin, log=lambda s: print(s, flush=True), bgcut=not a.no_bgcut)
    print(f'background cut: {sum(int(L["bg"].sum()) for L in A["lines"])} mask pixels over {len(A["lines"])} lines '
          f'(line masks now {sum(int(L["mask"].sum()) for L in A["lines"])})', flush=True)
    n = A['n']
    Ls = A['lines']
    if a.lines:
        np.savez_compressed(a.lines, cs=[L['cs'] for L in Ls], ce=[L['ce'] for L in Ls], a=[L['a'] for L in Ls],
                            b=[L['b'] for L in Ls], weak=[L['weak'] for L in Ls], fb=[L['fade_before'] for L in Ls],
                            fa=[L['fade_after'] for L in Ls], masks=np.array([L['mask'] for L in Ls]),
                            kc=A['kc'], present=A['present'], en=A['en'], y0=a.y0, y1=a.y1)
    F = Filler(A, a.y0, a.y1, a.static)

    cap = cv2.VideoCapture(a.src); fps = cap.get(cv2.CAP_PROP_FPS)
    cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y',
           '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', f'{fps:.6f}', '-i', '-',
           '-i', a.src, '-map', '0:v', '-map', '1:a?',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', str(a.crf), '-pix_fmt', 'yuv420p',
           '-profile:v', 'high', '-level', '4.0', '-c:a', 'copy', '-movflags', '+faststart', a.dst]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    wrote = 0
    k = 0
    while True:
        ok, f = cap.read()
        if not ok: break
        res = F.fill(k) if k < n else None
        if res is not None:
            f = f.copy(); f[F.m0:F.m1] = res
        p.stdin.write(f.tobytes()); wrote += 1; k += 1
    p.stdin.close(); rc = p.wait()
    s = F.stats
    print(f'fill: {s["frames"]} frames, {s["px"]} px, temporal {100 * s["px_temporal"] / max(1, s["px"]):.0f}%, '
          f'Telea {100 * s["px_telea"] / max(1, s["px"]):.0f}%', flush=True)
    print(f'{a.dst}: wrote {wrote} frames (source {n}), ffmpeg rc {rc}', flush=True)
    sys.exit(0 if (rc == 0 and wrote == n) else 1)


if __name__ == '__main__':
    main()
