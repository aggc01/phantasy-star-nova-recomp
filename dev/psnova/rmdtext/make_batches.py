"""Split the picked short rows into translation batches for subagents (2026-11-19).
usage: python make_batches.py <short_rows.json> <glossary.json> <out dir> [batch size=230]

Rows with the same (Japanese, English) pair become one item (key k); items stay in id order inside their id group so a
batch holds one kind of label. Each batch file carries the glossary entries whose English term occurs in its items, so a
translator needs only its batch file and docs/psnova/arabic-style.md.
  out/batches/b_NN.json = {"batch": NN, "glossary": [{en, ar}], "items": [{k, ids, jp, en, tags}]}
  out/items.json        = {k: [ids]}  (to spread results back to every id)"""
import sys, os, json, re, collections

rows = json.load(open(sys.argv[1], encoding='utf-8'))
gl = json.load(open(sys.argv[2], encoding='utf-8'))
out = sys.argv[3]; size = int(sys.argv[4]) if len(sys.argv) > 4 else 230
os.makedirs(os.path.join(out, 'batches'), exist_ok=True)

items, key = [], {}
for r in rows:
    pair = (r['jp'], r['en'])
    if pair not in key:
        key[pair] = len(items)
        items.append(dict(k=len(items), ids=[], group=r['group'], jp=r['jp'], en=r['en'],
                          tags=[t for t in r['tags'] if not t.startswith('{ruby') and t != '{/ruby}']))
    items[key[pair]]['ids'].append(r['id'])

# glossary: phrase entries (core table) first, longest first, then single tokens
gl_by_en = {}
for g in gl:
    gl_by_en.setdefault(g['en'], g['ar'])
def terms_in(text):
    found = []
    for en, ar in gl_by_en.items():
        if re.search(r'(?<![A-Za-z])' + re.escape(en) + r'(?![A-Za-z])', text):
            found.append(dict(en=en, ar=ar))
    return found

byg = collections.OrderedDict()
for it in items:
    byg.setdefault(it['group'], []).append(it)
batches, cur = [], []
for g, its in byg.items():
    for it in its:
        cur.append(it)
        if len(cur) >= size:
            batches.append(cur); cur = []
if cur:
    batches.append(cur)
for n, b in enumerate(batches):
    text = '\n'.join(it['en'] for it in b)
    seen, glos = set(), []
    for t in terms_in(text):
        if t['en'] not in seen:
            seen.add(t['en']); glos.append(t)
    json.dump(dict(batch=n, glossary=glos,
                   items=[dict(k=it['k'], ids=it['ids'][:3], jp=it['jp'], en=it['en'], tags=it['tags']) for it in b]),
              open(os.path.join(out, 'batches', 'b_%02d.json' % n), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
json.dump({it['k']: it['ids'] for it in items}, open(os.path.join(out, 'items.json'), 'w', encoding='utf-8'))
print('items', len(items), 'batches', len(batches), 'sizes', [len(b) for b in batches])
