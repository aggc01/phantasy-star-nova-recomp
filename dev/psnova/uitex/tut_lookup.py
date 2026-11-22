"""tut_lookup.py - find sheet rows (Japanese/English/Arabic) whose Japanese contains each query (helper for specs)."""
import csv, sys, unicodedata, os
HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, '..', '..', '..', 'dump', 'psnova-l10n', 'sheet', 'psnova_text_v5.tsv')
sys.stdout.reconfigure(encoding='utf-8')
rows = list(csv.reader(open(S, encoding='utf-8-sig'), delimiter='\t'))
norm = lambda s: unicodedata.normalize('NFKC', s)
for q in sys.argv[1:]:
    exact = q.startswith('=')
    q2 = norm(q.lstrip('='))
    hits = [r for r in rows[1:] if len(r) > 6 and ((norm(r[4]) == q2) if exact else (q2 in norm(r[4])))]
    hits.sort(key=lambda r: (len(r[4]), not r[6]))
    print('==', q, len(hits))
    for r in hits[:4]:
        print('  ', r[0], '|', r[4].replace('\n', '\n'), '|', r[5].replace('\n', '\n'), '|', r[6].replace('\n', '\n'))
