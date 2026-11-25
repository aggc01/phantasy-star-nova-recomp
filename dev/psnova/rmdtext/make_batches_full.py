"""Batches of every message still without English, for the full translation pass (2026-11-19, me: "Yes, translate them").
usage: python make_batches_full.py <sheet.tsv> <out dir> [items per batch=80]

A row is taken when it has Japanese text, its English is empty / identical to the Japanese / still holds Japanese, and
it is not a developer dummy (ダミー 削除予定 予備 テスト 仮 解説文 placeholder //... 【number】 操作説明N ガチャNPC ---)
or only digits/punctuation. Each item: id, jp, fan_en (if any), jp_lines, need_ar (false when the Arabic column already
has a translation: then only English is wanted), and context: the Japanese/English of the two rows before and after it
in id order (dialogue scenes are partly translated by the fan patch; neighbours give the story). Batches follow id order
inside one id group (group = id // 10000 * 10000, dialogue = first 9 digits of the id: one scene). The names table
(group 30000 and the character entries, JP/EN/AR) goes into every batch.
Writes <out>/batches/f_NNN.json and <out>/index.json."""
import csv, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from check_sheet import unesc

DUMMY = re.compile(r'ダミー|削除予定|予備|テスト|仮|解説文|placeholder|^//|【\d+】|^操作説明\d|ガチャNPC|^-+$', re.I)
JPC = re.compile(r'[぀-ヿ一-鿿]')
TAG = re.compile(r'\{[^}]*\}')
PUNCT = re.compile(r'^[\s　0-9０-９()（）+/:：★*「」『』×%\-～.,!?！？・…ー－=＝\[\]#]*$')

sheet, out = sys.argv[1], sys.argv[2]
size = int(sys.argv[3]) if len(sys.argv) > 3 else 80
R = list(csv.DictReader(open(sheet, encoding='utf-8-sig'), delimiter='\t'))
J, E, A = 'Japanese (original)', 'English (fan rePatch, to revise)', 'Arabic'
pos = {r['id']: k for k, r in enumerate(R)}


def group(i):
    return 'dlg:' + i[:9] if len(i) >= 12 else str(int(i) // 10000 * 10000)


def ctx(k):
    out = []
    for d in (-2, -1, 1, 2):
        if 0 <= k + d < len(R) and group(R[k + d]['id']) == group(R[k]['id']):
            r = R[k + d]
            out.append({'id': r['id'], 'jp': unesc(r[J])[:300], 'en': unesc(r[E])[:300]})
    return out


items = []
for k, r in enumerate(R):
    jp = unesc(r[J]); en = unesc(r[E])
    core = TAG.sub('', jp).strip(' 　\n')
    if not core or DUMMY.search(jp) or PUNCT.match(core):
        continue
    if en.strip() and en != jp and not JPC.search(TAG.sub('', en)):
        continue
    items.append({'id': r['id'], 'group': group(r['id']), 'jp': jp, 'fan_en': en if (en.strip() and en != jp) else '',
                  'jp_lines': jp.count('\n') + 1, 'need_ar': not r[A].strip(), 'context': ctx(k)})
names = [{'id': r['id'], 'jp': unesc(r[J]), 'en': unesc(r[E]), 'ar': unesc(r[A])} for r in R
         if r['id'].isdigit() and 30000 <= int(r['id']) < 40000 and r[J].strip(' 　-')]
os.makedirs(os.path.join(out, 'batches'), exist_ok=True)
batches, cur, cg = [], [], None
for it in items:
    g = it['group'].split(':')[0] if it['group'].startswith('dlg') else it['group']
    if cur and (len(cur) >= size or (g != cg and len(cur) >= size // 3)):
        batches.append(cur); cur = []
    cur.append(it); cg = g
if cur:
    batches.append(cur)
for n, b in enumerate(batches):
    json.dump({'batch': n, 'names': names, 'items': b}, open(os.path.join(out, 'batches', 'f_%03d.json' % n), 'w',
              encoding='utf-8', newline='\n'), ensure_ascii=False, indent=1)
json.dump({'items': len(items), 'batches': len(batches), 'need_ar': sum(i['need_ar'] for i in items)},
          open(os.path.join(out, 'index.json'), 'w', encoding='utf-8'))
import collections
c = collections.Counter(i['group'].split(':')[0] if i['group'].startswith('dlg') else i['group'] for i in items)
print('items', len(items), 'batches', len(batches), 'need Arabic too', sum(i['need_ar'] for i in items))
print(sorted(c.items(), key=lambda x: -x[1])[:25])
