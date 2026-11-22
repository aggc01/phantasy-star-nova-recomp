"""tut_detect.py - list candidate text-line boxes in a rendered tutorial picture (helper for writing specs).
Usage: tut_detect.py <name> [kind]   kind: white (default) | red | green | any
Prints [x0, y0, x1, y1) boxes of bright text-like strokes grouped into lines, and writes a 3x crop with the boxes
drawn to dump/psnova-l10n/uitex/crops/<name>_det_<kind>.png.
"""
import os, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PNG = os.path.join(PROJ, 'dump', 'psnova-l10n', 'scratch', 'research', 'uitex', 'png')
CROPS = os.path.join(PROJ, 'dump', 'psnova-l10n', 'uitex', 'crops')


def load(name):
    for a in ('patch', 'base'):
        p = os.path.join(PNG, a, name + '.png')
        if os.path.exists(p):
            return np.array(Image.open(p).convert('RGBA'))
    raise SystemExit('no png for ' + name)


def mask_of(a, kind):
    r, g, b = [a[..., i].astype(int) for i in range(3)]
    if kind == 'white':
        return (np.minimum(np.minimum(r, g), b) > 165) & (np.max(a[..., :3], axis=2) - np.min(a[..., :3], axis=2) < 60)
    if kind == 'red':
        return (r > 180) & (g < 90) & (b < 90)
    if kind == 'green':
        return (g > 170) & (r < 160) & (b < 120)
    return np.max(a[..., :3], axis=2) > 170


def main():
    name = sys.argv[1]
    kind = sys.argv[2] if len(sys.argv) > 2 else 'white'
    a = load(name)
    m = mask_of(a, kind).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
    d = cv2.dilate(m, k)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(d, 8)
    boxes = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if h < 5 or h > 18 or w < 5 or w > 300:
            continue
        sub = m[y:y + h, x:x + w]
        if sub.sum() < 8:
            continue
        boxes.append((y, x, x + w, y + h))
    boxes.sort()
    for y, x0, x1, y1 in boxes:
        print([int(x0), int(y), int(x1), int(y1)])
    im = Image.fromarray(a).convert('RGB').resize((a.shape[1] * 3, a.shape[0] * 3), Image.NEAREST)
    dr = ImageDraw.Draw(im)
    for y, x0, x1, y1 in boxes:
        dr.rectangle([x0 * 3, y * 3, x1 * 3 - 1, y1 * 3 - 1], outline=(255, 0, 255))
        dr.text((x0 * 3, y * 3 - 10), '%d,%d' % (x0, y), fill=(255, 255, 0))
    os.makedirs(CROPS, exist_ok=True)
    im.save(os.path.join(CROPS, '%s_det_%s.png' % (name, kind)))


if __name__ == '__main__':
    main()
