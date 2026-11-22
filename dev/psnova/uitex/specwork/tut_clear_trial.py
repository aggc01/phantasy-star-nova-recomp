"""tut_clear_trial.py - compare apply_spec clear settings on chosen boxes of a tutorial picture (no text drawn).
usage: tut_clear_trial.py <name> x0,y0,x1,y1 [...]   -> dump/psnova-l10n/uitex/crops/tut/trial_<name>_<i>.png
Each output: original on top, then one row per variant (see VARIANTS), 6x nearest."""
import os, sys, json
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'dev', 'psnova', 'uitex'))
sys.path.insert(0, os.path.join(ROOT, 'dev', 'psnova', 'rmdtext'))
import apply_spec, aiftex  # noqa: E402

VARIANTS = [
    dict(clear='inpaint'),                                                     # telea, thr 40, dilate 1
    dict(clear='inpaint', inpaint_dilate=2),
    dict(clear='inpaint', inpaint_threshold=25, inpaint_dilate=2),
    dict(clear='inpaint', inpaint_method='median', inpaint_window=61, inpaint_dilate=2),
    dict(clear='inpaint', inpaint_method='ns', inpaint_dilate=2),
    dict(clear="inpaint", inpaint_mask="box", inpaint_method="telea"),
    dict(clear="inpaint", inpaint_mask="box", inpaint_method="ns"),
    dict(clear="inpaint", inpaint_mask="box", inpaint_method="telea", inpaint_radius=1),
]
name = sys.argv[1]
src = os.path.join(ROOT, 'dump', 'psnova-l10n', 'scratch', 'research', 'base', name + '.aif')
d = open(src, 'rb').read()
W, H, fmt, tid = aiftex.info(d)
orig = aiftex.decode(d[0x1e0:], W, H, fmt)
for i, b in enumerate(sys.argv[2:]):
    box = [int(v) for v in b.split(',')]
    m = 6
    X0, Y0, X1, Y1 = max(0, box[0] - 6), max(0, box[1] - 4), min(W, box[2] + 6), min(H, box[3] + 4)
    rows = [orig[Y0:Y1, X0:X1, :3]]
    for v in VARIANTS:
        img = orig.copy()
        lab = dict(box=box, **v)
        apply_spec.clear_box(img, lab, 'en')
        rows.append(img[Y0:Y1, X0:X1, :3])
    sep = np.full((2, X1 - X0, 3), (255, 0, 255), np.uint8)
    pic = np.concatenate(sum([[r, sep] for r in rows], [])[:-1], 0)
    im = Image.fromarray(pic).resize(((X1 - X0) * m, pic.shape[0] * m), Image.NEAREST)
    out = os.path.join(ROOT, 'dump', 'psnova-l10n', 'uitex', 'crops', 'tut', 'trial_%s_%d.png' % (name, i))
    im.save(out); print(out)
