"""review_split_erase.py <spec> <idx> - insert an erase-only copy of label <idx> before it (same box and clear, en/ar
"") and set the text label's clear to "keep", so review_bands.py can replace the erase (2026-11-19 review)."""
import copy, json, sys
sp, i = sys.argv[1], int(sys.argv[2])
s = json.load(open(sp, encoding='utf-8')); L = s['labels'][i]
e = {k: copy.deepcopy(v) for k, v in L.items() if k in ('box', 'jp', 'clear') or k.startswith('inpaint') or k == 'fill_color'}
e['en'] = ''; e['ar'] = ''; e['note'] = 'erase (split from the text label, review)'
L['clear'] = 'keep'
for k in [k for k in L if k.startswith('inpaint') or k == 'fill_color']: del L[k]
s['labels'].insert(i, e)
json.dump(s, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2); print('split', i)
