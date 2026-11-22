"""Draw an encoded message the way the game lays it out (left to right, glyph advances), for a quick visual check
(2026-11-19). usage: python preview_msg.py <out.png> <lang en|ar> <id> [<id> ...]   (texts from sheet v5 / ar_all.json)
Basic-table characters are drawn from BasicCharSet.rmd, own glyphs from the message's atlas; button icons as grey boxes."""
import csv, json, os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from encode_text import Encoder
from rmdlib import Rmd, LOCAL_BASE
from check_sheet import unesc

ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
T = os.path.join(ROOT, 'dump', 'psnova-l10n', 'text')
enc = Encoder(T, os.path.join(T, 'map'))
bc = Rmd(open([os.path.join(dp, f) for dp, dn, fs in os.walk(os.path.join(ROOT, 'dump', 'psnova-l10n')) for f in fs if f == 'BasicCharSet.rmd'][0], 'rb').read())
rows = {r['id']: r for r in csv.DictReader(open(os.path.join(ROOT, 'dump', 'psnova-l10n', 'sheet', 'psnova_text_v5.tsv'), encoding='utf-8-sig'), delimiter='\t')}
ar = json.load(open(os.path.join(ROOT, 'dump', 'psnova-l10n', 'ar', 'ar_all.json'), encoding='utf-8'))
out, lang = sys.argv[1], sys.argv[2]
blocks = []
for i in sys.argv[3:]:
    text = ar[i]['text'] if lang == 'ar' else unesc(rows[i]['English (fan rePatch, to revise)'])
    r = Rmd(enc.encode(int(i), text, lang, arabic_mode='phrase', rtl=True))
    lines = [[]]
    for t in r.tokens():
        if t[0] == 'nl':
            lines.append([])
        elif t[0] == 'c' and t[1] >= LOCAL_BASE:
            k = t[1] - LOCAL_BASE; g = r.glyph(k); lines[-1].append(g[:, :r.recs[k][0]])
        elif t[0] == 'c':
            true = (t[1] & 0x7f) | ((t[1] >> 8) << 7); g = bc.glyph(true - 1); lines[-1].append(g[:, :max(1, bc.recs[true - 1][0])])
        elif t[0] == 'ctl' and t[1] == 0x8099:
            lines[-1].append(np.full((21, 20), 90, np.uint8))
    W = max([sum(g.shape[1] for g in l) for l in lines if l] + [1])
    img = np.zeros((21 * len(lines) + 6, W + 8), np.uint8)
    for k, l in enumerate(lines):
        x = 4
        for g in l:
            img[k * 21 + 3:k * 21 + 24, x:x + g.shape[1]] = np.maximum(img[k * 21 + 3:k * 21 + 24, x:x + g.shape[1]], g[:21]); x += g.shape[1]
    blocks.append(img)
W = max(b.shape[1] for b in blocks)
im = np.vstack([np.hstack([b, np.zeros((b.shape[0], W - b.shape[1]), np.uint8)]) for b in blocks])
Image.fromarray(im).resize((im.shape[1] * 2, im.shape[0] * 2), Image.NEAREST).save(out)
print('wrote', out)
