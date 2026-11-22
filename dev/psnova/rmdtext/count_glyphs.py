"""Count the glyphs each translated message draws (2026-11-19). The game lays out at most 128 glyphs per message
(fn_817e8410 / the layouts stop at 0x80; seen in the game: English tutorial pages cut off after exactly 128 characters,
spaces included). usage: python count_glyphs.py <sheet.tsv> <ar.json> <out.json>
For English (the sheet's English column) and Arabic (ar.json, as built) it encodes every message like build_l10n.py
and lists those over 128 with their counts."""
import json, os, sys, io
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from encode_text import Encoder
from check_sheet import unesc

ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TEXT = os.path.join(ROOT, 'dump', 'psnova-l10n', 'text')
enc = Encoder(TEXT, os.path.join(TEXT, 'map'))
L = io.open(sys.argv[1], encoding='utf-8-sig').read().splitlines()
h = L[0].split('\t'); iE = h.index('English (fan rePatch, to revise)'); iJ = h.index('Japanese (original)')
ar = json.load(open(sys.argv[2], encoding='utf-8'))
over = {'en': {}, 'ar': {}}
for l in L[1:]:
    c = l.split('\t')
    s = unesc(c[iE]) if iE < len(c) else ''
    if s and s != unesc(c[iJ]):
        try:
            enc.encode(int(c[0]), s, 'en')
            if enc.last_drawn > 128: over['en'][c[0]] = enc.last_drawn
        except Exception:
            pass
for k, v in ar.items():
    try:
        enc.encode(int(k), v['text'], 'ar', arabic_mode=v.get('mode', 'phrase'), rtl=v.get('rtl', True))
        if enc.last_drawn > 128: over['ar'][k] = enc.last_drawn
    except Exception:
        pass
json.dump(over, open(sys.argv[3], 'w', encoding='utf-8'), indent=0)
print({k: len(v) for k, v in over.items()}, 'max', {k: max(v.values()) if v else 0 for k, v in over.items()})
