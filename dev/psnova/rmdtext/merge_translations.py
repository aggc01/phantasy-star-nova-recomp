"""Write a translation pass ({id: {"en", "ar"}} files) into the text sheet (2026-11-19).
usage: python merge_translations.py <sheet in .tsv> <out prefix> <note> <results.json> [...]
English goes into the English column (replacing the fan text: these passes translate from the Japanese and were reviewed),
Arabic into the Arabic column; the note (e.g. "EN+AR: tutorial pass") is added to the notes column.
Writes <prefix>.tsv and <prefix>.xlsx."""
import io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from xlsxw import write_xlsx
from check_sheet import unesc

sheet, prefix, note = sys.argv[1:4]
tr = {}
for p in sys.argv[4:]:
    tr.update(json.load(open(p, encoding='utf-8')))
L = io.open(sheet, encoding='utf-8-sig').read().splitlines()
header = L[0].split('\t'); iE = header.index('English (fan rePatch, to revise)'); iA = header.index('Arabic'); iN = header.index('notes')
rows, ne, na = [], 0, 0
for l in L[1:]:
    c = [unesc(x) for x in l.split('\t')]
    c += [''] * (len(header) - len(c))
    t = tr.get(c[0])
    if t:
        if t.get('en', '').strip():
            c[iE] = t['en'].replace('\\n', '\n'); ne += 1
        if t.get('ar', '').strip():
            c[iA] = t['ar'].replace('\\n', '\n'); na += 1
        c[iN] = (c[iN] + '; ' if c[iN] else '') + note
    rows.append(c)
write_xlsx(prefix + '.xlsx', [('messages', header, rows, [18, 11, 8, 6, 60, 60, 60, 34])])
with open(prefix + '.tsv', 'w', encoding='utf-8-sig', newline='') as f:
    f.write('\t'.join(header) + '\n')
    for row in rows:
        f.write('\t'.join(str(x).replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t') for x in row) + '\n')
print('rows', len(rows), 'English set', ne, 'Arabic set', na)
