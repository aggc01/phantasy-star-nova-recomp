"""Measure Japanese subtitle text LEFT in cleaned Phantasy Star Nova story movies, per line and per frame, including the fade /
edge frames of each line (written 2026-11-19 for v3; docs/psnova/movie-cleaning-v3.md).

Reference = the ORIGINAL movie. Its lines are found with remove_jp_subs_v3's detector (same bands, thresholds and fan-copy
English timing as the cleaners). For every line:
  T    = the line's text pixels: white (top-hat of the min channel > 30) in >= 60 % of its core frames, inside the
         persistent mask, rows y0..y1-1 only;
  ring = pixels 2-6 px around T (the background right next to the text).
In each frame j from 20 frames before the line's core to 20 after:
  visible[j]  = (share of T white in the ORIGINAL) - (share of ring white in the ORIGINAL) > 0.25
                (the line's text is really on screen in the original at j: fades, edge frames; a bright background
                makes T and ring equally white and does not count);
  residue[j]  = number of T pixels white (> 25) in the CLEANED frame and unchanged (min-channel difference < 15)
                minus (share of ring white in the cleaned frame) x |T|    (the local background level, same frame);
  a frame has residue when visible[j] and residue[j] > max(40, 4 % of |T|).

Frames are reported as CORE (inside the line's core frames) or EDGE (before/after the core: the persistence window's
blind frames, fades, changes). Also reported: v2's own detector (persistent kept pixels > thr) run on the cleaned movie.

Pictures (--strips DIR): for a few lines per movie (the lines with the most edge residue in the FIRST cleaned file), the
band of frames cs-2, cs-1, cs, ce, ce+1, ce+2, as original / clean 1 / clean 2 ...; and the worst residue frames of the
LAST cleaned file.

  python check_sub_residue.py MP00_000_000 --clean dump/psnova-l10n/movies_clean_jp --clean dump/psnova-l10n/movies_clean_jp_v3
         [--strips dump/psnova-l10n/movies_v3_check] [--json out.json]
Runs at IDLE priority.
"""
import argparse, json, os, sys
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import remove_jp_subs_v3 as V3

ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
D = os.path.join(ROOT, 'dump', 'psnova-l10n')
BANDS = {'MP09_040_040': (464, 491, 700), 'MP00_000_000': (470, 497, 350), 'MP00_010_050': (470, 496, 350),
         'MP09_040_070': (470, 497, 350), 'MP06_030_070': (470, 497, 350), 'MP00_000_010': (472, 499, 350),
         'MP06_030_050': (470, 497, 350), 'MP06_030_040': (470, 497, 350)}
WIN = 20


def runs(frames):
    out = []
    for f in sorted(frames):
        if out and f == out[-1][1] + 1: out[-1][1] = f
        else: out.append([f, f])
    return [tuple(r) for r in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('--clean', action='append', required=True, help='folder of cleaned movies (repeat)')
    ap.add_argument('--strips'); ap.add_argument('--json')
    ap.add_argument('--nlines', type=int, default=3)
    a = ap.parse_args()
    V3.idle(); cv2.setNumThreads(2)
    y0, y1, thr = BANDS[a.name]
    src = os.path.join(D, 'movies_jp', a.name + '.mp4')
    ref = os.path.join(D, 'movies', a.name + '.mp4')
    ref_ok = os.path.exists(ref)
    A = V3.analyse(src, y0, y1, thr, ref if ref_ok else None, keep_crop=False, log=lambda s: None)
    n, TH, K30, lines = A['n'], A['TH'], A['K30'], A['lines']
    KR6, KR2 = np.ones((13, 13), np.uint8), np.ones((5, 5), np.uint8)
    for L in lines:
        cm = (K30[L['cs']:L['ce'] + 1].mean(axis=0) >= 0.25) | L['mask']
        T = cm & ((TH[L['cs']:L['ce'] + 1] > 30).mean(axis=0) >= 0.6)
        T[:3] = False; T[3 + (y1 - y0):] = False          # only rows y0..y1-1, where the text is
        ring = (cv2.dilate(T.astype(np.uint8), KR6) > 0) & ~(cv2.dilate(T.astype(np.uint8), KR2) > 0)
        ring[:3] = False; ring[3 + (y1 - y0):] = False
        L['T'], L['ring'], L['nT'] = T, ring, max(1, int(T.sum()))
        L['en'] = bool((A['en'][L['cs']:L['ce'] + 1] > 150).mean() > 0.3) if ref_ok else True
        L['rt'] = max(40.0, 0.04 * L['nT'])
    at = [[] for _ in range(n)]              # frame -> lines whose window holds it
    for i, L in enumerate(lines):
        if L['T'].sum() < 30 or L['ring'].sum() < 30: continue
        for j in range(max(0, L['cs'] - WIN), min(n, L['ce'] + WIN + 1)): at[j].append(i)

    wanted = set()                            # edge frames for the strips
    for L in lines:
        for j in (L['cs'] - 2, L['cs'] - 1, L['cs'], L['ce'], L['ce'] + 1, L['ce'] + 2):
            if 0 <= j < n: wanted.add(j)
    m0, m1 = y0 - 14, min(V3.H, y1 + 14)
    results, crops = [], {}
    for ci, folder in enumerate(a.clean):
        cln = os.path.join(folder, a.name + '.mp4') if os.path.isdir(folder) else folder
        co, cc = cv2.VideoCapture(src), cv2.VideoCapture(cln)
        res = {}                               # frame -> (line, residue-base, kind)
        extra = 0
        THc = []
        j = 0
        while True:
            ok1, fo = co.read(); ok2, fc = cc.read()
            if not (ok1 and ok2):
                extra = 1 if ok2 else 0
                break
            thc = V3.tophat(fc, y0, y1); THc.append(thc)
            if at[j]:
                mo = fo[y0 - 3:y1 + 3].min(axis=2).astype(np.int16); mc = fc[y0 - 3:y1 + 3].min(axis=2).astype(np.int16)
                same = np.abs(mo - mc) < 15
                wo, wc = TH[j] > 25, thc > 25
                for i in at[j]:
                    L = lines[i]; T, ring = L['T'], L['ring']
                    if wo[T].mean() - wo[ring].mean() <= 0.25: continue
                    r = np.count_nonzero(T & wc & same) - wc[ring].mean() * L['nT']
                    if r > L['rt'] and (j not in res or r > res[j][1]):
                        res[j] = (i, r, 'core' if L['cs'] <= j <= L['ce'] else 'edge')
            if j in wanted or j in res:
                crops.setdefault(j, {}).setdefault('orig', fo[m0:m1].copy())
                crops.setdefault(j, {})[ci] = fc[m0:m1].copy()
            j += 1
        nclean = j + extra + sum(1 for _ in iter(lambda: cc.read()[0], False))
        _, kcc = V3.persistent(np.array(THc))
        det = int((kcc > thr).sum())
        conf = lambda f: lines[res[f][0]]['en']
        edge = sorted(f for f in res if res[f][2] == 'edge'); core = sorted(f for f in res if res[f][2] == 'core')
        edge_en = [f for f in edge if conf(f)]; core_en = [f for f in core if conf(f)]
        lines_hit = sorted(set(res[f][0] for f in res))
        results.append(dict(clean=cln, frames=n, frames_clean=nclean, lines=len(lines),
                            lines_en=sum(L['en'] for L in lines), residue_frames=len(res),
                            edge_frames=len(edge), core_frames=len(core), edge_frames_en=len(edge_en),
                            core_frames_en=len(core_en), lines_with_residue=len(lines_hit),
                            max_residue=int(max([v[1] for v in res.values()], default=0)),
                            edge_runs=runs(edge_en)[:60], core_runs=runs(core_en)[:60],
                            other_runs=runs([f for f in res if not conf(f)])[:60], detector_frames=det,
                            per_line={i: sorted(f for f in res if res[f][0] == i) for i in lines_hit}))
        R = results[-1]
        tag = os.path.basename(os.path.dirname(cln))
        print(f'{a.name} [{tag}]: frames {n}/{nclean}, lines {len(lines)} ({R["lines_en"]} with English); residue frames on '
              f'English-confirmed lines: edge {len(edge_en)}, core {len(core_en)}; on other lines: '
              f'{len(res) - len(edge_en) - len(core_en)}; max {R["max_residue"]} px; v2-detector frames {det}', flush=True)
        print(f'   edge runs: {R["edge_runs"][:14]}', flush=True)
        print(f'   core runs: {R["core_runs"][:14]}', flush=True)
        print(f'   other-line runs: {R["other_runs"][:14]}', flush=True)
        if ci == 0: first = res
        last = res

    if a.strips:
        os.makedirs(a.strips, exist_ok=True)
        labels = ['orig'] + ['v2' if os.path.basename(os.path.normpath(c)) == 'movies_clean_jp' else
                             os.path.basename(os.path.normpath(c)).replace('movies_clean_jp_', '') for c in a.clean]

        def block(frames, title):
            rows = []
            for j in frames:
                if j not in crops: continue
                for key, lab in zip(['orig'] + list(range(len(a.clean))), labels):
                    if key not in crops[j]: continue
                    r = crops[j][key].copy()
                    cv2.putText(r, f'{j} {lab}', (4, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 0), 1)
                    rows.append(r)
                rows.append(np.zeros((4, V3.W, 3), np.uint8))
            if rows: cv2.imwrite(os.path.join(a.strips, title + '.png'), np.vstack(rows))

        score = {i: sum(1 for f in first if first[f][0] == i and first[f][2] == 'edge') for i in range(len(lines))}
        pick = sorted(range(len(lines)), key=lambda i: -score[i])[:a.nlines]
        for i in sorted(pick):
            L = lines[i]
            block([L['cs'] - 2, L['cs'] - 1, L['cs'], L['ce'], L['ce'] + 1, L['ce'] + 2],
                  f'{a.name}_line{i}_{L["cs"]}-{L["ce"]}')
        worst = sorted(last, key=lambda f: -last[f][1])[:6]
        if worst: block(sorted(worst), f'{a.name}_worst_{labels[-1]}')
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(dict(name=a.name, lines=[dict(cs=L['cs'], ce=L['ce'], a=L['a'], b=L['b'], fb=L['fade_before'],
                                                    fa=L['fade_after'], weak=bool(L['weak']), en=L['en']) for L in lines],
                           results=results), fh, indent=1, default=int)


if __name__ == '__main__':
    main()
