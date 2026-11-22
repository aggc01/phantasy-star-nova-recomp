"""review_bands.py - turn erase labels of a spec into per-row fill bands sampled from the original texture
(2026-11-19 visual review). For panel bars/rows whose background is uniform along x and shaded along y, a per-row
median taken just beside the text is a cleaner erase than one flat fill or a 2-D inpaint.

usage: review_bands.py <spec.json> <label index> <sx0> <sx1> [--rows y0 y1] [--x x0 x1] [--lerp xl] [--dry]
  replaces label <index> (its box, any clear mode) by one fill label per run of equal-coloured rows; each row's colour
  = median of the ORIGINAL texture's pixels at x in [sx0, sx1) on that row. --rows/--x override the erased area.
  --lerp xl: for bars shaded along x too: each row runs linearly from the original pixel at column xl (left of the
  text) to the right-hand median, written as runs of equal colour (more labels).
  The new labels keep jp, get en/ar "" and note "erase: per-row band (review)". Prints the colours and the row std.
"""
import json, os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
R = os.path.join(PROJ, 'dump', 'psnova-l10n', 'scratch', 'research', 'uitex', 'png')
a = sys.argv[1:]
dry = '--dry' in a
if dry: a.remove('--dry')
def take(flag):
    if flag in a:
        i = a.index(flag); v = (int(a[i + 1]), int(a[i + 2])); del a[i:i + 3]; return v
rows, xs = take('--rows'), take('--x')
lerp = None
if '--lerp' in a:
    i = a.index('--lerp'); lerp = int(a[i + 1]); del a[i:i + 2]
sp, idx, sx0, sx1 = a[0], int(a[1]), int(a[2]), int(a[3])
spec = json.load(open(sp, encoding='utf-8'))
name = os.path.splitext(spec['texture'])[0]
p = os.path.join(R, 'patch', name + '.png')
if spec.get('archive') == 'base' or not os.path.exists(p): p = os.path.join(R, 'base', name + '.png')
im = np.array(Image.open(p).convert('RGBA')).astype(int)
L = spec['labels'][idx]
x0, y0, x1, y1 = L['box']
if rows: y0, y1 = rows
if xs: x0, x1 = xs
new = []
for y in range(y0, y1):
    px = im[y, sx0:sx1, :3]
    c = [int(v) for v in np.median(px, axis=0)]
    sd = float(px.std(axis=0).mean())
    print('row %d colour %s std %.1f' % (y, c, sd))
    if lerp is not None:
        cl = im[y, lerp, :3]
        for x in range(x0, x1):
            t = (x - lerp) / float(sx0 - lerp)
            cx = [int(round(cl[k] + (c[k] - cl[k]) * t)) for k in range(3)]
            if new and new[-1]['box'][1] == y and new[-1]['fill_color'][:3] == cx:
                new[-1]['box'][2] = x + 1
            else:
                new.append({'box': [x, y, x + 1, y + 1], 'jp': L.get('jp', ''), 'en': '', 'ar': '', 'clear': 'fill',
                            'fill_color': cx + [255], 'note': 'erase: per-row gradient (review)'})
        continue
    if new and new[-1]['fill_color'][:3] == c:
        new[-1]['box'][3] = y + 1
    else:
        new.append({'box': [x0, y, x1, y + 1], 'jp': L.get('jp', ''), 'en': '', 'ar': '', 'clear': 'fill',
                    'fill_color': c + [255], 'note': 'erase: per-row band (review)'})
if L.get('en') or L.get('ar'):
    sys.exit('label %d draws text; erase labels only' % idx)
print('label %d %s -> %d bands' % (idx, L['box'], len(new)))
if not dry:
    spec['labels'][idx:idx + 1] = new
    with open(sp, 'w', encoding='utf-8') as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
