"""tut_ba.py - before / after-en / after-ar zoom of one region of a tutorial picture (check renders from
dump/psnova-l10n/uitex/crops/tut/check/{en,ar}/preview/).
usage: tut_ba.py <name> x0,y0,x1,y1 [scale]  -> dump/psnova-l10n/uitex/crops/tut/ba_<name>_<x0>_<y0>.png"""
import os, sys
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
C = os.path.join(ROOT, 'dump', 'psnova-l10n', 'uitex', 'crops', 'tut')
name = sys.argv[1]
box = [int(v) for v in sys.argv[2].split(',')]
s = int(sys.argv[3]) if len(sys.argv) > 3 else 4
ims = [Image.open(os.path.join(ROOT, 'dump', 'psnova-l10n', 'scratch', 'research', 'uitex', 'png', 'base', name + '.png'))]
ims += [Image.open(os.path.join(C, 'check', l, 'preview', name + '.png')) for l in ('en', 'ar')]
w, h = box[2] - box[0], box[3] - box[1]
out = Image.new('RGB', (w * s, (h * s + 3) * 3), (255, 0, 255))
for i, im in enumerate(ims):
    out.paste(im.convert('RGB').crop(box).resize((w * s, h * s), Image.NEAREST), (0, i * (h * s + 3)))
p = os.path.join(C, 'ba_%s_%d_%d.png' % (name, box[0], box[1]))
out.save(p); print(p)
