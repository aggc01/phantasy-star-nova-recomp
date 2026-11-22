"""Join the core term table of docs/psnova/arabic-style.md with the agent-made term list into one glossary (2026-11-19).
usage: python make_glossary.py <arabic-style.md> <glossary_terms.json> <out glossary.json>
Core terms win over the term list. Table cells with several terms ("Fire / Ice / ...") are paired by position."""
import sys, json, re

md = open(sys.argv[1], encoding='utf-8').read().split('## Core terms', 1)[1]
core = []
for line in md.splitlines():
    c = [x.strip() for x in line.strip().strip('|').split('|')]
    if len(c) != 3 or c[0] in ('English (fan)', '---') or '...' in c[0] or set(c[0]) <= set('-'):
        continue
    ens = [e.strip() for e in c[0].split('/')]
    ars = [a.strip() for a in c[2].split('/')]
    if len(ens) == len(ars):
        pairs = zip(ens, ars)
    elif len(ars) == 1:
        pairs = [(e, ars[0]) for e in ens]
    else:
        continue
    for e, a in pairs:
        for e2 in [x.strip() for x in re.split(r'\s+or\s+', e)]:
            core.append(dict(en=e2, ar=a, kind='core'))
terms = json.load(open(sys.argv[2], encoding='utf-8'))
have = {c['en'] for c in core}
out = core + [t for t in terms if t['en'] not in have]
json.dump(out, open(sys.argv[3], 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('core', len(core), 'terms', len(terms), 'glossary', len(out))
