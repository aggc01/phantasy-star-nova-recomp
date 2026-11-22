"""Export the sheet's Arabic column for build_l10n.py --arabic (2026-11-19).
usage: python export_arabic.py <sheet.tsv> <out.json> [mode=phrase]
Every row with Arabic -> {id: {"text", "mode", "rtl"}}; rtl is false for the ids listed in ltr_ids.txt (beside this
script: labels that must keep their box's own alignment, e.g. names beside an icon), true otherwise (the encoder then
starts the message with the 0x8095 mark and the pack's psn_rtl hooks right-align it)."""
import io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from check_sheet import unesc

sheet, out = sys.argv[1], sys.argv[2]
mode = sys.argv[3] if len(sys.argv) > 3 else 'phrase'
ltr = []
for line in open(os.path.join(HERE, 'ltr_ids.txt'), encoding='utf-8'):
    line = line.split('#', 1)[0].strip()
    if not line:
        continue
    r = line.split()[0]
    a, _, b = r.partition('-')
    ltr.append((int(a), int(b or a)))
L = io.open(sheet, encoding='utf-8-sig').read().splitlines()
h = L[0].split('\t'); iA = h.index('Arabic')
o, nl = {}, 0
for l in L[1:]:
    c = l.split('\t')
    if len(c) > iA and c[iA]:
        i = int(c[0]); rtl = not any(a <= i <= b for a, b in ltr)
        nl += not rtl
        # Japanese corner brackets do not mirror in right-to-left text (seen in the game, 2026-11-19: 『...』 in a quest
        # banner faced the wrong way): Arabic uses its own quotes « » (mirrored correctly by the bidi step)
        t = unesc(c[iA]).translate(str.maketrans({'「': '«', '『': '«', '」': '»', '』': '»'}))
        o[c[0]] = {'text': t, 'mode': mode, 'rtl': rtl}
json.dump(o, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
print('Arabic rows', len(o), 'kept left-aligned', nl)
