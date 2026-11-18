import os, sys
sys.path.insert(0, r'F:\Antigravity Proj\Recomp-decomp\Phantasy Star Nova Recomp\dev\psnova')
import cpk

TSV = r'F:\Antigravity Proj\Recomp-decomp\Phantasy Star Nova Recomp\dev\psnova\inventory\compare-patch105-vs-repatch.tsv'
JP = r'F:\Antigravity Proj\Recomp-decomp\Phantasy Star Nova Recomp\dump\decrypted\PCSG00351\patch0\NOVA_FileList_Vita_patch.cpk'
EN = r'F:\RECOMP GAMES\Phantasy Star Nova (v1.05)\rePatch\PCSG00351\NOVA_FileList_Vita_patch.cpk'
OUT = r'C:\Users\<user>\AppData\Local\Temp\claude\998bc63b0bafea56\b675f1be-9794-49d9-bad0-3237cb167afe\scratchpad\rmd-samples'

rows = []
with open(TSV, encoding='utf-8') as f:
    next(f)
    for line in f:
        c = line.rstrip('\n').split('\t')
        if c[0].startswith('msg_') and c[0].endswith('.rmd') and c[1] == 'changed':
            rows.append((c[0], int(c[5])))  # extract size in English (repatch)
rows.sort(key=lambda r: r[1])
print('changed msg files:', len(rows))
print('smallest:', rows[:3])
print('largest:', rows[-3:])
# 3 short, then 10 spread over the rest
pick = [rows[i] for i in (0, 1, 2)]
rest = rows[3:]
step = max(1, len(rest) // 10)
pick += [rest[i * step] for i in range(10)]
names = []
for n, _ in pick:
    if n not in names:
        names.append(n)
print('picked', len(names), names)

jp = cpk.Cpk(JP)
en = cpk.Cpk(EN)
jmap = {e['path']: e for e in jp.entries}
emap = {e['path']: e for e in en.entries}
os.makedirs(os.path.join(OUT, 'ja'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'en'), exist_ok=True)
for n in names:
    if n not in jmap or n not in emap:
        print('missing', n, n in jmap, n in emap)
        continue
    with open(os.path.join(OUT, 'ja', n), 'wb') as fo:
        fo.write(cpk.read_entry(jp, jmap[n]))
    with open(os.path.join(OUT, 'en', n), 'wb') as fo:
        fo.write(cpk.read_entry(en, emap[n]))
    print('wrote', n, len(cpk.read_entry(jp, jmap[n])), len(cpk.read_entry(en, emap[n])))
jp.close()
en.close()
