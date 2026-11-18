import struct, sys, hashlib, os
D = 'F:/Antigravity Proj/Recomp-decomp/Phantasy Star Nova Recomp/dump/decrypted/PCSG00351/'
BASE = D + 'repatch0/NOVA_FileList_Vita_patch.cpk'
SRC = D + 'patch0/NOVA_FileList_Vita_patch.cpk'
OUT = D + 'merged/NOVA_FileList_Vita_patch.cpk'
SZ = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 8, 7: 8, 8: 4, 9: 8, 10: 4, 11: 8}
FM = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i', 6: 'Q', 7: 'q', 8: 'f', 9: 'd'}
res = []


def chk(name, ok, ev=''):
    res.append(ok)
    print(('PASS' if ok else 'FAIL'), name, ev)


def unscr(b):
    o = bytearray(b)
    m = 0x5f
    for i in range(len(o)):
        o[i] ^= m
        m = (m * 0x15) & 0xff
    return bytes(o)


class T:
    pass


def parse(buf, at):
    t = T()
    t.at = at
    scr = buf[at:at + 4] != b'@UTF'
    head = unscr(buf[at:at + 8]) if scr else buf[at:at + 8]
    assert head[:4] == b'@UTF'
    t.scr = scr
    ts = struct.unpack('>I', head[4:8])[0]
    t.tsize = ts
    raw = buf[at:at + 8 + ts]
    t.raw = unscr(raw) if scr else raw
    b = t.raw
    (_, ver, ro, so, do, no, nc, rw, nr) = struct.unpack_from('>IHHIIIHHI', b, 4)
    t.ver, t.ro, t.so, t.do, t.no, t.nc, t.rw, t.nr = ver, ro, so, do, no, nc, rw, nr
    t.strpool = b[8 + so:8 + do]
    t.cols = []
    p = 0x20

    def cs(o):
        s = 8 + so + o
        return b[s:b.index(b'\0', s)].decode()
    for _ in range(nc):
        fl = b[p]
        p += 1
        no_, = struct.unpack_from('>I', b, p)
        p += 4
        name = cs(no_)
        st = fl & 0xf0
        ty = fl & 15
        const = None
        if st in (0x30, 0x70):
            const = b[p:p + SZ[ty]]
            p += SZ[ty]
        t.cols.append((name, fl, const))
    t.colend = p
    t.rows = []

    def val(raw, ty):
        if ty in FM:
            return struct.unpack('>' + FM[ty], raw)[0]
        if ty == 10:
            return cs(struct.unpack('>I', raw)[0])
        return ('D',) + struct.unpack('>II', raw)
    for r in range(nr):
        q = 8 + ro + r * rw
        s = q
        row = {}
        for name, fl, const in t.cols:
            st = fl & 0xf0
            ty = fl & 15
            if st == 0x50:
                row[name] = val(b[q:q + SZ[ty]], ty)
                q += SZ[ty]
            elif st in (0x30, 0x70):
                row[name] = val(const, ty)
            else:
                row[name] = None
        assert q - s == rw
        t.rows.append(row)
    return t


def chunk(buf, off):
    h = buf[off:off + 0x10]
    fl, sz, z = struct.unpack('<IIi', h[4:])
    return h[:4], fl, sz, z


def load(path):
    buf = open(path, 'rb').read()
    a = T()
    a.buf = buf
    assert buf[:4] == b'CPK '
    a.chead = chunk(buf, 0)
    a.hdr = parse(buf, 0x10)
    a.h = a.hdr.rows[0]
    h = a.h
    a.toc = parse(buf, h['TocOffset'] + 0x10)
    a.etoc = parse(buf, h['EtocOffset'] + 0x10) if h.get('EtocOffset') else None
    return a


B = load(BASE)
O = load(OUT)
S = load(SRC)
bh, oh, sh = B.h, O.h, S.h
print('base hdr', bh)
print('out hdr', oh)
print('src hdr', sh)
fs = len(O.buf)
# 1 header
chk('1a header columns same (name,flags,const bytes except values)',
    [(c[0], c[1]) for c in B.hdr.cols] == [(c[0], c[1]) for c in O.hdr.cols], str([c[0] for c in B.hdr.cols]))
chk('1a2 header table size/layout same',
    (B.hdr.tsize, B.hdr.rw, B.hdr.nc, B.hdr.nr, B.hdr.scr, B.hdr.so, B.hdr.do) ==
    (O.hdr.tsize, O.hdr.rw, O.hdr.nc, O.hdr.nr, O.hdr.scr, O.hdr.so, O.hdr.do), 'tsize=%d scr=%s' % (O.hdr.tsize, O.hdr.scr))
chk('1a3 CPK chunk header', O.chead[0] == b'CPK ' and O.chead[1] == B.chead[1] and O.chead[2] == O.hdr.tsize + 8 and O.chead[3] == 0,
    'out=%s base=%s' % (O.chead, B.chead))
chk('1b Files == toc rows', oh['Files'] == O.toc.nr == 23034, '%s %s' % (oh['Files'], O.toc.nr))
tm = chunk(O.buf, oh['TocOffset'])
chk('1c TOC magic, chunk size = tsize+8', tm[0] == b'TOC ' and tm[2] == O.toc.tsize + 8, 'chunk=%s tsize+8=%d' % (tm, O.toc.tsize + 8))
bt = bh['TocSize'] - (B.toc.tsize + 8)
ot = oh['TocSize'] - (O.toc.tsize + 8)
chk('1c2 TocSize relation to tsize same as base', bt == ot, 'base TocSize-(tsize+8)=%d out=%d; TocSize out=%d base=%d' % (bt, ot, oh['TocSize'], bh['TocSize']))
chk('1d Toc end <= ContentOffset', oh['TocOffset'] + oh['TocSize'] <= oh['ContentOffset'],
    '%d <= %d; base end %d' % (oh['TocOffset'] + oh['TocSize'], oh['ContentOffset'], bh['TocOffset'] + bh['TocSize']))
chk('1e ContentOffset+ContentSize==EtocOffset', oh['ContentOffset'] + oh['ContentSize'] == oh['EtocOffset'],
    '%d vs %d; base %d vs %d' % (oh['ContentOffset'] + oh['ContentSize'], oh['EtocOffset'], bh['ContentOffset'] + bh['ContentSize'], bh['EtocOffset']))
chk('1f EtocOffset+EtocSize==file size', oh['EtocOffset'] + oh['EtocSize'] == fs,
    '%d vs %d; base %d vs %d' % (oh['EtocOffset'] + oh['EtocSize'], fs, bh['EtocOffset'] + bh['EtocSize'], len(B.buf)))
em = chunk(O.buf, oh['EtocOffset'])
chk('1g ETOC chunk magic/size', em[0] == b'ETOC' and em[2] == O.etoc.tsize + 8 and oh['EtocSize'] == em[2] + 0x10,
    '%s tsize+8=%d EtocSize=%d' % (em, O.etoc.tsize + 8, oh['EtocSize']))
for k in ('Itoc', 'Gtoc', 'Htoc'):
    chk('1h %s absent in base and out' % k, not bh.get(k + 'Offset') and not oh.get(k + 'Offset'), '%s %s' % (bh.get(k + 'Offset'), oh.get(k + 'Offset')))
align = oh['Align']
chk('1i Align same', oh['Align'] == bh['Align'], str(align))
chk('1j EtocOffset 8-aligned (base too?)', oh['EtocOffset'] % 8 == 0,
    'out%%8=%d out%%Align=%d base%%8=%d base%%Align=%d' % (oh['EtocOffset'] % 8, oh['EtocOffset'] % align, bh['EtocOffset'] % 8, bh['EtocOffset'] % align))
chg = [k for k in bh if bh[k] != oh.get(k)]
print('header changed fields', chg)
print('header fields', {k: (bh[k], oh[k]) for k in bh if k not in ('Comment',)})
sum_ex = sum(r['ExtractSize'] for r in O.toc.rows)
sum_fs = sum(r['FileSize'] for r in O.toc.rows)
bex = sum(r['ExtractSize'] for r in B.toc.rows)
bfs = sum(r['FileSize'] for r in B.toc.rows)
if 'EnabledPackedSize' in oh:
    chk('1k Enabled*Size formulas hold on base and out',
        (bh['EnabledPackedSize'], bh['EnabledDataSize']) == (2 * bex, bex + bfs) and
        (oh['EnabledPackedSize'], oh['EnabledDataSize']) == (2 * sum_ex, sum_ex + sum_fs),
        'base %s %s | %s %s' % (bh['EnabledPackedSize'], bh['EnabledDataSize'], 2 * bex, bex + bfs))
# alt formulas
print('alt: sumFS', bfs, bex, 'out', sum_fs, sum_ex)
# 2 tables
for nm, tb, to in (('TOC', B.toc, O.toc), ('ETOC', B.etoc, O.etoc)):
    chk('2a %s column defs identical' % nm, tb.cols == to.cols and (tb.rw, tb.nc, tb.scr, tb.ver) == (to.rw, to.nc, to.scr, to.ver),
        'cols=%s rw=%d scr=%s ver=%d' % ([c[0] for c in to.cols], to.rw, to.scr, to.ver))
    rows_end = to.ro + to.rw * to.nr
    ok = rows_end <= to.so <= to.do <= len(to.raw) - 8 and to.tsize + 8 == len(to.raw) and to.colend - 8 <= to.ro
    chk('2b %s layout rows_end<=strings<=data<=end, len==tsize+8' % nm, ok,
        'rows_end=%d so=%d do=%d len-8=%d | base ro=%d so=%d do=%d len-8=%d' % (rows_end, to.so, to.do, len(to.raw) - 8, tb.ro, tb.so, tb.do, len(tb.raw) - 8))
    chk('2c %s tsize%%8==0 like base' % nm, to.tsize % 8 == tb.tsize % 8, 'out %d base %d' % (to.tsize % 8, tb.tsize % 8))
    chk('2d %s table name string valid' % nm, to.raw[8 + to.so + to.no:].split(b'\0')[0] == tb.raw[8 + tb.so + tb.no:].split(b'\0')[0],
        to.raw[8 + to.so + to.no:].split(b'\0')[0].decode())
    # unused / trailing strings
    # check string pool minimal: every string referenced
chk('2e ETOC rows = TOC rows + 1 (terminator)', B.etoc.nr == B.toc.nr + 1 and O.etoc.nr == O.toc.nr + 1,
    'base toc %d etoc %d; out toc %d etoc %d' % (B.toc.nr, B.etoc.nr, O.toc.nr, O.etoc.nr))
# string pool references: every string offset in rows is within strpool and pool contains no orphan beyond growth
print('toc strpool len out/base', len(O.toc.strpool), len(B.toc.strpool))
# 3 base entries
base_off = min(bh['TocOffset'], bh['ContentOffset'])
out_off = min(oh['TocOffset'], oh['ContentOffset'])
chk('3a offset rule base same', base_off == out_off, '%d %d' % (base_off, out_off))
omap = {}
dup = False
for i, r in enumerate(O.toc.rows):
    if r['ID'] in omap:
        dup = True
    omap[r['ID']] = (i, r)
chk('3b IDs unique in out', not dup and len(omap) == 23034, '%d unique' % len(omap))
chk('3b2 IDs == 0..N-1', sorted(omap) == list(range(23034)), 'min %d max %d' % (min(omap), max(omap)))
keys = list(B.toc.rows[0])
print('toc keys', keys)
bad = badoff = hashbad = n = 0
for r in B.toc.rows:
    i, o = omap[r['ID']]
    for k in keys:
        if k != 'FileOffset' and r[k] != o[k]:
            bad += 1
    if r['FileOffset'] != o['FileOffset']:
        badoff += 1
    a = B.buf[base_off + r['FileOffset']:base_off + r['FileOffset'] + r['FileSize']]
    b = O.buf[out_off + o['FileOffset']:out_off + o['FileOffset'] + o['FileSize']]
    if a != b or len(b) != r['FileSize']:
        hashbad += 1
    n += 1
chk('3c base rows equal except FileOffset (by ID)', bad == 0, '%d diffs of %d rows' % (bad, n))
chk('3d FileOffset same and bytes identical', badoff == 0 and hashbad == 0, 'offset diffs %d, byte diffs %d' % (badoff, hashbad))
bn = {(r['DirName'], r['FileName']) for r in B.toc.rows}
on = {(r['DirName'], r['FileName']) for r in O.toc.rows}
chk('3e names unique and base subset', len(on) == 23034 and bn <= on, '%d unique; extra=%s' % (len(on), on - bn))
ents = sorted((out_off + r['FileOffset'], r['FileSize'], r['FileName']) for r in O.toc.rows)
ov = [(a, b) for a, b in zip(ents, ents[1:]) if a[0] + a[1] > b[0]]
chk('3f no overlap', not ov, '%d overlaps' % len(ov))
mis = [e for e in ents if e[0] % align]
bmis = [base_off + r['FileOffset'] for r in B.toc.rows if (base_off + r['FileOffset']) % align]
print('align', align, 'out misaligned', len(mis), 'base misaligned', len(bmis))
chk('3g only new entry may be misaligned beyond base', len(mis) - len(bmis) <= 1, 'out %d base %d; names %s' % (len(mis), len(bmis), [e[2] for e in mis if e[2] == 'tex_nova_ui_common.aif']))
chk('3h all within content area', all(oh['ContentOffset'] <= e[0] and e[0] + e[1] <= oh['ContentOffset'] + oh['ContentSize'] for e in ents),
    'max end %d content end %d' % (max(a + b for a, b, _ in ents), oh['ContentOffset'] + oh['ContentSize']))
print('base last file end', max(base_off + r['FileOffset'] + r['FileSize'] for r in B.toc.rows), 'base content end', bh['ContentOffset'] + bh['ContentSize'])
bc = B.buf[bh['ContentOffset']:bh['ContentOffset'] + bh['ContentSize']]
oc = O.buf[oh['ContentOffset']:oh['ContentOffset'] + len(bc)]
chk('3i old content area byte identical', bc == oc, '%d bytes' % len(bc))
gap = O.buf[oh['TocOffset'] + oh['TocSize']:oh['ContentOffset']]
bgap = B.buf[bh['TocOffset'] + bh['TocSize']:bh['ContentOffset']]
chk('3j gap TOC end..ContentOffset zero', set(gap) <= {0}, 'gap %d, base gap %d (base zero %s)' % (len(gap), len(bgap), set(bgap) <= {0}))
# bytes before TocOffset identical except header
chk('3k bytes 0x10+hdrtable..TocOffset identical to base', O.buf[0x10 + 8 + O.hdr.tsize:oh['TocOffset']] == B.buf[0x10 + 8 + B.hdr.tsize:bh['TocOffset']], 'TocOffset %d' % oh['TocOffset'])
# header diff
d = [i for i in range(0x10 + 8 + O.hdr.tsize) if O.buf[i] != B.buf[i]]
print('header byte diffs', len(d), d[:3], d[-3:])
# 4 new entry
new = [r for r in O.toc.rows if r['FileName'] == 'tex_nova_ui_common.aif']
srow = [r for r in S.toc.rows if r['FileName'] == 'tex_nova_ui_common.aif']
chk('4a one new row, one source row', len(new) == 1 and len(srow) == 1)
nr_ = new[0]
sr = srow[0]
sbase = min(sh['TocOffset'], sh['ContentOffset'])
nb = O.buf[out_off + nr_['FileOffset']:out_off + nr_['FileOffset'] + nr_['FileSize']]
sb = S.buf[sbase + sr['FileOffset']:sbase + sr['FileOffset'] + sr['FileSize']]
chk('4b bytes equal source, sha1, len', nb == sb and hashlib.sha1(nb).hexdigest() == '96f8f6244d1ff087e9488e2b70b5ac35d0ab4182' and len(nb) == 1049056, hashlib.sha1(nb).hexdigest())
print('new row', nr_)
print('src row', sr)
chk('4c row values match source except FileOffset/ID', all(nr_[k] == sr[k] for k in nr_ if k not in ('FileOffset', 'ID')), 'ID new %s src %s' % (nr_['ID'], sr['ID']))
print('new offset', out_off + nr_['FileOffset'], '%align', (out_off + nr_['FileOffset']) % align, '%8', (out_off + nr_['FileOffset']) % 8, 'end', out_off + nr_['FileOffset'] + nr_['FileSize'], 'etoc', oh['EtocOffset'])
idx = [i for i, r in enumerate(O.toc.rows) if r is nr_][0]
names = [(r['DirName'] or '', r['FileName']) for r in O.toc.rows]
bnames = [(r['DirName'] or '', r['FileName']) for r in B.toc.rows]
print('row idx', idx, 'neighbors', names[idx - 1], names[idx + 1])


def srt(L, key):
    return all(key(a) <= key(b) for a, b in zip(L, L[1:]))


for nm, key in (('upper dir,name', lambda x: (x[0].upper(), x[1].upper())), ('raw', lambda x: x), ('lower', lambda x: (x[0].lower(), x[1].lower())),
                ('upper name only', lambda x: x[1].upper()), ('lower name only', lambda x: x[1].lower())):
    print('order', nm, 'base', srt(bnames, key), 'out', srt(names, key))
chk('4d some ordering rule holding in base also holds in out',
    any(srt(bnames, k) and srt(names, k) for k in (lambda x: (x[0].upper(), x[1].upper()), lambda x: x[1].upper(), lambda x: (x[0].lower(), x[1].lower()), lambda x: x[1].lower(), lambda x: x)))
be = B.etoc.rows
oe = O.etoc.rows
print('etoc keys', [c[0] for c in O.etoc.cols], 'new row', oe[idx])
chk('4e ETOC others equal base shifted', oe[:idx] == be[:idx] and oe[idx + 1:] == be[idx:], 'idx %d' % idx)
chk('4f ETOC terminator all zero', all(not v for v in oe[-1].values()), str(oe[-1]))
sidx = [i for i, r in enumerate(S.toc.rows) if r['FileName'] == 'tex_nova_ui_common.aif'][0]
print('src etoc row', S.etoc.rows[sidx], 'out', oe[idx])
chk('4g ETOC new row == source ETOC row', S.etoc.rows[sidx] == oe[idx])
print('base etoc first/last2', be[0], be[-2], be[-1])
# etoc dates monotone in base?
print('etoc sample around idx', oe[idx - 1], oe[idx], oe[idx + 1])
# ETOC correlation: does base etoc row i correspond to toc row i? check LocalDir/UpdateDateTime vs ordering
print('overall', all(res), 'fails', res.count(False))
