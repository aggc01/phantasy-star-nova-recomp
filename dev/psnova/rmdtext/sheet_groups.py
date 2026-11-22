"""Group the sheet's rows by id range to find menus / short labels vs help texts vs dialogue.
usage: python sheet_groups.py <sheet.tsv> [out.json]
Prints per group: row count, how many have Japanese text, mean JP length, max JP lines, two samples."""
import sys, json, csv, collections, re

def jp_len(s):
    return len(re.sub(r'\{[^}]*\}', '', s).replace('\\n', ''))

def group_of(i):
    s = str(i)
    if len(s) >= 12:          # dialogue ids like 100010020040008
        return 'dlg:' + s[:5]
    return 'id:%d' % (i // 10000 * 10000)

rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8-sig'), delimiter='\t'))
G = collections.OrderedDict()
for r in rows:
    i = int(r['id'])
    g = G.setdefault(group_of(i), [])
    g.append(r)
out = {}
for g, rs in G.items():
    jp = [r for r in rs if r['Japanese (original)'].strip(' 　')]
    L = [jp_len(r['Japanese (original)']) for r in jp] or [0]
    lines = max(int(r['JP lines']) for r in rs)
    smp = [ (r['id'], r['Japanese (original)'][:30], r['English (fan rePatch, to revise)'][:40]) for r in jp[:: max(1, len(jp)//2)][:2]]
    out[g] = dict(n=len(rs), jp=len(jp), mean=round(sum(L)/len(L),1), maxlen=max(L), maxlines=lines, samples=smp)
    print('%-12s n=%5d jp=%5d mean=%5.1f max=%4d lines<=%d  %s' % (g, len(rs), len(jp), out[g]['mean'], max(L), lines,
          ' | '.join('%s %s / %s' % s for s in smp)))
if len(sys.argv) > 2:
    json.dump(out, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
