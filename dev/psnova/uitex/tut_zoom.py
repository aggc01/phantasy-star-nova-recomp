"""tut_zoom.py - zoomed crops of a tutorial picture with a pixel grid, for finding label boxes by eye.
usage: tut_zoom.py <name> <x0> <y0> <x1> <y1> [scale] [boxes as x0,y0,x1,y1 ...]
writes dump/psnova-l10n/uitex/crops/tut/<name>_<x0>_<y0>.png (grid line every 10 px, labelled every 50)."""
import os, sys
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
R = os.path.join(PROJ, 'dump', 'psnova-l10n', 'scratch', 'research', 'uitex', 'png')
name = sys.argv[1]; x0, y0, x1, y1 = map(int, sys.argv[2:6])
s = int(sys.argv[6]) if len(sys.argv) > 6 else 4
p = os.path.join(R, 'patch', name + '.png')
if not os.path.exists(p): p = os.path.join(R, 'base', name + '.png')
im = Image.open(p).convert('RGBA')
bg = Image.new('RGBA', im.size, (255, 0, 255, 255)); bg.alpha_composite(im)
c = bg.crop((x0, y0, x1, y1)).resize(((x1 - x0) * s, (y1 - y0) * s), Image.NEAREST).convert('RGB')
d = ImageDraw.Draw(c)
for x in range(x0 - x0 % 10, x1 + 1, 10):
    if x < x0: continue
    col = (0, 255, 0) if x % 50 == 0 else (0, 110, 0)
    d.line([((x - x0) * s, 0), ((x - x0) * s, c.height)], fill=col)
    if x % 50 == 0: d.text(((x - x0) * s + 2, 2), str(x), fill=(255, 255, 0))
for y in range(y0 - y0 % 10, y1 + 1, 10):
    if y < y0: continue
    col = (0, 255, 0) if y % 50 == 0 else (0, 110, 0)
    d.line([(0, (y - y0) * s), (c.width, (y - y0) * s)], fill=col)
    d.text((2, (y - y0) * s + 2), str(y), fill=(255, 255, 0))
for b in sys.argv[7:]:
    a = list(map(int, b.split(',')))
    d.rectangle([(a[0] - x0) * s, (a[1] - y0) * s, (a[2] - x0) * s - 1, (a[3] - y0) * s - 1], outline=(0, 200, 255))
out = os.path.join(PROJ, 'dump', 'psnova-l10n', 'uitex', 'crops', 'tut', '%s_%d_%d.png' % (name, x0, y0))
c.save(out); print(out)
