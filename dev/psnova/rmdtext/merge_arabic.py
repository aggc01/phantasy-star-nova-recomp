"""Write checked Arabic results into the Arabic column of the text sheet (2026-11-19).
usage: python merge_arabic.py <sheet in .tsv> <out dir with batches/, results/, items.json> <sheet out prefix>
-> <prefix>.tsv and <prefix>.xlsx (same columns; Arabic filled for every id of each translated item; a note
"Arabic: Claude, menu pass 1" is added). Existing Arabic cells are kept (never overwritten)."""
import sys, os, json, glob, io
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from xlsxw import write_xlsx
from check_sheet import unesc

sheet, out, prefix = sys.argv[1:4]
items = json.load(open(os.path.join(out, 'items.json'), encoding='utf-8'))
ar_of = {}
for rp in glob.glob(os.path.join(out, 'results', 'b_*.json')):
    for k, ar in json.load(open(rp, encoding='utf-8')).items():
        if ar and ar.strip():
            for i in items[k]:
                ar_of[i] = ar.strip()
L = io.open(sheet, encoding='utf-8-sig').read().splitlines()
header = L[0].split('\t'); iA = header.index('Arabic'); iN = header.index('notes')
rows, filled = [], 0
for l in L[1:]:
    c = [unesc(x) for x in l.split('\t')]
    c += [''] * (len(header) - len(c))
    if c[0] in ar_of and not c[iA]:
        c[iA] = ar_of[c[0]]; filled += 1
        c[iN] = (c[iN] + '; ' if c[iN] else '') + 'Arabic: Claude, menu pass 1'
    rows.append(c)
write_xlsx(prefix + '.xlsx', [('messages', header, rows, [18, 11, 8, 6, 60, 60, 60, 34])])
with open(prefix + '.tsv', 'w', encoding='utf-8-sig', newline='') as f:
    f.write('\t'.join(header) + '\n')
    for row in rows:
        f.write('\t'.join(str(x).replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t') for x in row) + '\n')
print('rows', len(rows), 'Arabic filled', filled)
