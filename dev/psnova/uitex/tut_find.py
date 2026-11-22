"""tut_find.py - find text boxes in a tutorial picture.
usage: tut_find.py <name> red                      -> clusters of red callout text (box padded for the white outline)
       tut_find.py <name> white x0,y0,x1,y1 ...     -> tight box of bright (white/near-white) pixels inside each region
       tut_find.py <name> rows x0,y0,x1,y1 [thr]    -> per-row runs of bright pixels inside region (find text lines)
       tut_find.py <name> sample x,y ...            -> pixel colours"""
import os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
R = os.path.join(PROJ, 'dump', 'psnova-l10n', 'scratch', 'research', 'uitex', 'png')
name, mode = sys.argv[1], sys.argv[2]
p = os.path.join(R, 'patch', name + '.png')
if not os.path.exists(p): p = os.path.join(R, 'base', name + '.png')
a = np.array(Image.open(p).convert('RGBA')).astype(int)
r, g, b = a[..., 0], a[..., 1], a[..., 2]
if mode == 'red':
    m = (r > 160) & (g < 110) & (b < 110) & (r - g > 90)
    def dil(x, k):
        o = x.copy()
        for _ in range(k):
            t = o.copy()
            t[1:] |= o[:-1]; t[:-1] |= o[1:]; t[:, 1:] |= o[:, :-1]; t[:, :-1] |= o[:, 1:]
            o = t
        return o
    big = dil(m, 4)
    H, W = m.shape
    seen = np.zeros_like(big)
    for sy in range(H):
        for sx in range(W):
            if not big[sy, sx] or seen[sy, sx]: continue
            st = [(sy, sx)]; seen[sy, sx] = True; pts = []
            while st:
                y, x = st.pop(); pts.append((y, x))
                for yy, xx in ((y+1, x), (y-1, x), (y, x+1), (y, x-1)):
                    if 0 <= yy < H and 0 <= xx < W and big[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True; st.append((yy, xx))
            pts = np.array(pts)
            sel = m[pts[:, 0], pts[:, 1]]
            if sel.sum() < 25: continue
            q = pts[sel]
            x0, x1 = q[:, 1].min(), q[:, 1].max() + 1; y0, y1 = q[:, 0].min(), q[:, 0].max() + 1
            print('red px box', [int(x0), int(y0), int(x1), int(y1)], 'padded', [int(x0) - 3, int(y0) - 3, int(x1) + 3, int(y1) + 3], 'n', int(sel.sum()))
elif mode in ('white', 'rows'):
    for reg in sys.argv[3:]:
        if ',' not in reg: continue
        x0, y0, x1, y1 = map(int, reg.split(','))
        thr = int(sys.argv[-1]) if ',' not in sys.argv[-1] else 175
        sub = (np.minimum(np.minimum(r, g), b) > thr)[y0:y1, x0:x1]
        if mode == 'white':
            yy, xx = np.nonzero(sub)
            if len(xx) == 0: print(reg, 'none'); continue
            print(reg, '->', [int(x0 + xx.min()), int(y0 + yy.min()), int(x0 + xx.max() + 1), int(y0 + yy.max() + 1)])
        else:
            rows = sub.any(1)
            y = 0
            while y < len(rows):
                if rows[y]:
                    s = y
                    while y < len(rows) and rows[y]: y += 1
                    band = sub[s:y]
                    cols = np.nonzero(band.any(0))[0]
                    print('  y %d-%d  x %d-%d' % (y0 + s, y0 + y, x0 + cols.min(), x0 + cols.max() + 1))
                else: y += 1
elif mode == 'sample':
    for s in sys.argv[3:]:
        x, y = map(int, s.split(','))
        print(s, a[y, x].tolist())
