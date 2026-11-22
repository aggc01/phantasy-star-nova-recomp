"""check_sheet.py - automatic check of the decoded text sheet against the game's own message dictionary: the first line of
every message (tags and furigana removed) must equal the dictionary entry at the next id (+1 / +10000 / +0).
Written 2026-11-18.  python check_sheet.py <sheet .tsv> <mdic>   -> counts, the kinds of differences, examples
"""
import collections, io, json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rmdlib import read_mdic


def unesc(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            out.append({'n': '\n', 't': '\t', '\\': '\\'}.get(s[i + 1], s[i + 1])); i += 2
        else:
            out.append(s[i]); i += 1
    return ''.join(out)


def main():
    tsv, mdic = sys.argv[1:3]
    D, _ = read_mdic(mdic)
    L = io.open(tsv, encoding='utf-8-sig').read().splitlines()
    hdr = L[0].split('\t'); iJ = hdr.index('Japanese (original)')
    res = collections.Counter(); bad = []
    for l in L[1:]:
        c = l.split('\t'); mid = int(c[0]); jp = unesc(c[iJ])
        first = re.sub(r'\{ruby:[^}]*\}|\{/ruby\}', '', jp).split('\n')[0]
        first = re.sub(r'\{[0-9a-f]{4}(:[0-9a-f]+)?\}', '', first)
        cand = [D.get(mid + s) for s in (1, 10000, 0)]
        cand = [x for x in cand if x is not None]
        if not cand:
            res['no dictionary entry'] += 1; continue
        if first in cand:
            res['exact'] += 1
        elif any(first.replace('　', '').strip() == x.replace('　', '').strip() for x in cand):
            res['differs only in spaces'] += 1
        else:
            res['differs'] += 1; bad.append((mid, first, cand))
    print(dict(res))
    same_len = collections.Counter()
    for mid, a, cs in bad:
        b = min(cs, key=lambda x: abs(len(x) - len(a)))
        if len(a) == len(b):
            for x, y in zip(a, b):
                if x != y:
                    same_len[(x, y)] += 1
        else:
            same_len['different length'] += 1
    print('character differences (decoded, dictionary):', same_len.most_common(25))
    for mid, a, cs in bad[:15]:
        print(mid, '|', a, '|', ' / '.join(cs))
    json.dump([[m, a, c] for m, a, c in bad], open(os.path.splitext(tsv)[0] + '_check_differs.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)


if __name__ == '__main__':
    main()
