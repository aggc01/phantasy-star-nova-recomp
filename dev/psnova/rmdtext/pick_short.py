"""Pick the menu / short-label rows of the sheet (the rows translated into Arabic; dialogue and long help texts
are left to the user). usage: python pick_short.py <sheet.tsv> <out.json> [maxlen=24]

A row is picked when: its id is not a dialogue id (fewer than 12 digits), it has one Japanese line, at most maxlen
characters of Japanese (tags not counted), and it is not a developer dummy (ダミー / 削除予定 / 予備 / テスト) or only
digits and punctuation. Each picked row keeps the Japanese, the fan English and the tags it contains (they must survive
translation). Rows are grouped by id range (group = id // 10000 * 10000) so a batch shares one kind of label."""
import sys, json, csv, re, collections

MAXLEN = int(sys.argv[3]) if len(sys.argv) > 3 else 24
DUMMY = re.compile(r'ダミー|削除予定|予備|テスト|仮|dummy|test|placeholder|解説文|^//|【\d+】|^操作説明\d|^ガチャNPC', re.I)
# groups of short spoken lines (left to the user with the dialogue) and the staff credits (names; later)
SPOKEN = {260000, 530000, 620000, 730000}
CREDITS = {750000}
TAG = re.compile(r'\{[^}]*\}')
PUNCT_ONLY = re.compile(r'^[\s　0-9０-９()（）+/:：★*「」×%\-～.,!?！？・…ー－=＝\[\]#]*$')

def jp_len(s):
    return len(TAG.sub('', s).replace('\\n', ''))

rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8-sig'), delimiter='\t'))
picked, skipped = [], collections.Counter()
for r in rows:
    i = int(r['id']); jp = r['Japanese (original)']
    core = TAG.sub('', jp).strip(' 　')
    if len(r['id']) >= 12: skipped['dialogue'] += 1; continue
    if not core: skipped['empty'] += 1; continue
    if i // 10000 * 10000 in SPOKEN: skipped['spoken lines'] += 1; continue
    if i // 10000 * 10000 in CREDITS: skipped['credits'] += 1; continue
    if int(r['JP lines']) != 1 or '\\n' in jp: skipped['multi-line'] += 1; continue
    if jp_len(jp) > MAXLEN: skipped['long'] += 1; continue
    if DUMMY.search(jp): skipped['dummy'] += 1; continue
    if PUNCT_ONLY.match(core): skipped['digits/punct'] += 1; continue
    picked.append(dict(id=r['id'], group=i // 10000 * 10000, jp=jp, en=r['English (fan rePatch, to revise)'],
                       tags=TAG.findall(jp), notes=r['notes']))
json.dump(picked, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
g = collections.Counter(p['group'] for p in picked)
print('picked', len(picked), 'skipped', dict(skipped))
print('distinct Japanese texts', len({p['jp'] for p in picked}))
print('groups', len(g), ' '.join('%d:%d' % kv for kv in sorted(g.items())))
