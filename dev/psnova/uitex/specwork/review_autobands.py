"""review_autobands.py - per-row band erase for text labels, found automatically (2026-11-19 visual review).

usage: review_autobands.py <spec.json> <idx> [<idx> ...] [--thr 40] [--gap 2] [--w 10] [--pad 1] [--dry]
For each text label idx (its own clear inpaint/fill): finds the Japanese strokes in the ORIGINAL texture inside the
label's box with apply_spec's stroke mask (bright polarity, outline/shadow included), takes their bounding box (+pad),
and inserts erase labels before the text label: one fill per row, colour = median of the original pixels at
x in [bbox.x1 + gap, bbox.x1 + gap + w) on that row (just right of the text, same row). The text label's clear
becomes "keep". Indices are processed from the highest down, so give them as they are now.
Prints, per label, the bbox and the sample std (high std = the sample hit something: check that label by eye).
"""
import json, os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import apply_spec as A  # noqa: E402
a = sys.argv[1:]
def take(flag, d):
    if flag in a:
        i = a.index(flag); v = int(a[i + 1]); del a[i:i + 2]; return v
    return d
thr, gap, w, pad = take('--thr', 40), take('--gap', 2), take('--w', 10), take('--pad', 1)
dry = '--dry' in a
if dry: a.remove('--dry')
sp = a[0]; idxs = sorted(map(int, a[1:]), reverse=True)
spec = json.load(open(sp, encoding='utf-8'))
name = os.path.splitext(spec['texture'])[0]
R = os.path.join(A.RESEARCH, 'uitex', 'png')
p = os.path.join(R, spec.get('archive', 'base'), name + '.png')
if not os.path.exists(p): p = os.path.join(R, 'base', name + '.png')
im = np.array(Image.open(p).convert('RGBA'))
for i in idxs:
    L = spec['labels'][i]
    x0, y0, x1, y1 = [int(v) for v in L['box']]
    m = A._stroke_mask(im, (x0, y0, x1, y1), thr, 'bright', 2)
    ys, xs = np.nonzero(m)
    if not len(xs):
        print(i, 'no strokes found'); continue
    bx0, by0, bx1, by1 = max(x0, xs.min() - pad), max(0, ys.min() - pad), xs.max() + 1 + pad, ys.max() + 1 + pad
    sx0, sx1 = bx1 + gap, bx1 + gap + w
    new, sds = [], []
    for y in range(by0, by1):
        px = im[y, sx0:sx1, :3].astype(int)
        c = [int(v) for v in np.median(px, axis=0)]
        sds.append(float(px.std(axis=0).mean()))
        if new and new[-1]['fill_color'][:3] == c:
            new[-1]['box'][3] = y + 1
        else:
            new.append({'box': [int(bx0), y, int(bx1), y + 1], 'jp': L.get('jp', ''), 'en': '', 'ar': '',
                        'clear': 'fill', 'fill_color': c + [255], 'note': 'erase: per-row band (review, auto)'})
    print('%d %s bbox %s sample x %d-%d max std %.1f -> %d bands' % (i, L.get('en', ''), [int(bx0), int(by0), int(bx1), int(by1)], sx0, sx1, max(sds), len(new)))
    if not dry:
        L['clear'] = 'keep'
        for k in [k for k in L if k.startswith('inpaint') or k == 'fill_color']: del L[k]
        spec['labels'][i:i] = new
if not dry:
    json.dump(spec, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
