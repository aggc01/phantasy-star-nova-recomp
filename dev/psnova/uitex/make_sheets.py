"""make_sheets.py [lang...] [--out-root DIR] - one contact sheet per language of every before/after preview.

Reads <out-root>/<lang>/preview/*_ba.png (written by apply_spec.py; default out-root dump/psnova-l10n/uitex/out)
and writes <out-root>/sheet_<lang>.png: the previews stacked in columns (each at its own 2x size, scaled down only
when wider than the column), each under its texture name. Default languages: en ar.
"""
import argparse, glob, os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
COL_W = 900          # column width px
MAX_H = 6000         # start a new column after this height
BG, FG = (30, 30, 40), (235, 225, 120)


def label_font():
    for f in (os.path.join(ROOT, 'tools', 'fonts', 'segoeuib.ttf'), 'arial.ttf'):
        try:
            return ImageFont.truetype(f, 15)
        except OSError:
            pass
    return ImageFont.load_default()


def sheet(files, out, title):
    font = label_font()
    tiles = []
    for f in files:
        im = Image.open(f).convert('RGB')
        if im.width > COL_W:
            im = im.resize((COL_W, round(im.height * COL_W / im.width)), Image.LANCZOS)
        tiles.append((os.path.basename(f)[:-7], im))
    cols, cur, h = [], [], 0
    for t in tiles:
        th = t[1].height + 24
        if cur and h + th > MAX_H:
            cols.append((cur, h)); cur, h = [], 0
        cur.append(t); h += th
    if cur:
        cols.append((cur, h))
    W = len(cols) * (COL_W + 12) + 12
    H = max(h for _, h in cols) + 40
    pic = Image.new('RGB', (W, H), BG)
    dr = ImageDraw.Draw(pic)
    dr.text((12, 8), title, fill=(255, 255, 255), font=font)
    for ci, (col, _) in enumerate(cols):
        x, y = 12 + ci * (COL_W + 12), 32
        for name, im in col:
            dr.text((x, y), name, fill=FG, font=font)
            pic.paste(im, (x, y + 20))
            y += im.height + 24
    pic.save(out)
    return pic.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('langs', nargs='*', default=['en', 'ar'])
    ap.add_argument('--out-root', default=os.path.join(ROOT, 'dump', 'psnova-l10n', 'uitex', 'out'))
    a = ap.parse_args()
    for lang in a.langs or ['en', 'ar']:
        files = sorted(glob.glob(os.path.join(a.out_root, lang, 'preview', '*_ba.png')))
        if not files:
            print('%s: no previews' % lang); continue
        out = os.path.join(a.out_root, 'sheet_%s.png' % lang)
        size = sheet(files, out, 'UI textures [%s]: before (top) / after (bottom) - %d textures' % (lang, len(files)))
        print('%s: %d previews -> %s %s' % (lang, len(files), out, size))


if __name__ == '__main__':
    main()
