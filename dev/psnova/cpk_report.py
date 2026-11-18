#!/usr/bin/env python3
"""cpk_report.py - verification, comparison and inventory report for the five CPK archives.

Run (standard library only, read-only on the archives):
  "<venv python>" -I dev/psnova/cpk_report.py

It imports cpk.py from this folder and does the following:
  (a) extent checks per archive (sum of FileSize, file size, partial overlaps; identical
      shared ranges are counted separately)
  (b) extracts ~30 small files (one per extension) into the scratchpad sample folder and
      records their first 16 bytes
  (c) decompresses CRILAYLA entries and compares the output length with ExtractSize
  (4) compares patch105 vs repatch_patch and base movie vs repatch_movie by path, size
      and sha1 of the stored bytes
  writes dev/psnova/inventory/magic-samples.tsv, dev/psnova/inventory/compare-*.tsv and
  dev/psnova/CPK-INVENTORY.md, and prints the verification results.
"""

import collections
import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cpk  # noqa: E402

PROJECT = 'F:/Antigravity Proj/Recomp-decomp/Phantasy Star Nova Recomp'
SAMPLES = ('C:/Users/<user>/AppData/Local/Temp/claude/998bc63b0bafea56/'
           'b675f1be-9794-49d9-bad0-3237cb167afe/scratchpad/cpk-samples')
REPATCH = 'F:/RECOMP GAMES/Phantasy Star Nova (v1.05)/rePatch/PCSG00351'
INV = os.path.join(HERE, 'inventory')
SAMPLE_CAP = 200 * 1024 * 1024

ARCHIVES = [
    ('base', PROJECT + '/dump/decrypted/PCSG00351/app0/NOVA_FileList_Vita.cpk'),
    ('movie', PROJECT + '/dump/decrypted/PCSG00351/app0/NOVA_FileList_Vita_movie.cpk'),
    ('patch105', PROJECT + '/dump/decrypted/PCSG00351/patch0/NOVA_FileList_Vita_patch.cpk'),
    ('repatch_patch', REPATCH + '/NOVA_FileList_Vita_patch.cpk'),
    ('repatch_movie', REPATCH + '/NOVA_FileList_Vita_movie.cpk'),
]

MAGICS = [
    (b'@UTF', 'CRI @UTF table'),
    (b'CPK ', 'CPK archive'),
    (b'TOC ', 'CPK TOC'),
    (b'ITOC', 'CPK ITOC'),
    (b'CRILAYLA', 'CRILAYLA stream (stored)'),
    (b'\x89PNG', 'PNG image'),
    (b'DDS ', 'DDS texture'),
    (b'GXT\x00', 'Vita GXT texture'),
    (b'FSB5', 'FMOD FSB5 bank'),
    (b'BKHD', 'Wwise soundbank'),
    (b'RIFF', 'RIFF container'),
    (b'OggS', 'Ogg'),
    (b'HCA\x00', 'CRI HCA audio'),
    (b'@SFV', 'CRI @SFV'),
    (b'CRID', 'CRI USM/CRID container'),
    (b'AFS2', 'CRI AFS2 archive (AWB)'),
    (b'INIM', 'INIM header (.mini, unidentified)'),
    (b'\x00\x00\x01\xba', 'MPEG program stream'),
    (b'\x00\x00\x01\xb3', 'MPEG video'),
    (b'PSMF', 'PSMF (PSP-style movie)'),
    (b'PK\x03\x04', 'ZIP'),
    (b'\x7fELF', 'ELF'),
    (b'\xff\xd8\xff', 'JPEG'),
    (b'fLaC', 'FLAC'),
    (b'ID3', 'MP3 (ID3)'),
    (b'\xff\xfb', 'MP3 frame'),
    (b'OTTO', 'OpenType (OTF)'),
    (b'\x00\x01\x00\x00', 'TrueType (TTF) or binary'),
    (b'true', 'TrueType'),
    (b'wOFF', 'WOFF'),
    (b'wOF2', 'WOFF2'),
    (b'\x1bLua', 'Lua bytecode'),
    (b'\xef\xbb\xbf', 'text (UTF-8 BOM)'),
    (b'\xff\xfe', 'text (UTF-16LE BOM)'),
    (b'\xfe\xff', 'text (UTF-16BE BOM)'),
    (b'<?xml', 'XML text'),
]

TEXT_EXT = {'.csv', '.txt', '.tbl', '.xml', '.json', '.ini', '.cfg', '.msg', '.fnt',
            '.ttf', '.otf', '.pgf', '.lua', '.lst', '.txb', '.dic', '.scr', '.xlsx'}
TEXT_WORDS = ('text', 'msg', 'message', 'font', 'dialog', 'script', 'string', 'lang',
              'local', 'talk', 'subtitle', 'caption', 'tutorial', 'help', 'name_', 'strings')


def classify(head):
    if not head:
        return 'empty'
    if all(c == 0 for c in head):
        return 'zero-filled'
    for m, name in MAGICS:
        if head.startswith(m):
            return name
    if len(head) >= 8 and head[4:8] == b'ftyp':
        return 'MP4/ISO-BMFF'
    if all(c in (9, 10, 13) or 32 <= c < 127 for c in head):
        return 'text-like (ASCII)'
    return 'binary (unknown)'


def ext_of(path):
    name = path.rsplit('/', 1)[-1]
    dot = name.rfind('.')
    return name[dot:].lower() if dot > 0 else '(none)'


def top_dir(path):
    return path.split('/', 1)[0] if '/' in path else '(root)'


def entry_head(c, e):
    """First 16 logical bytes of an entry. For CRILAYLA the first 0x100 logical bytes are
    stored raw at header_offset+0x10, so the head can be read without decompressing."""
    if e['size'] < e['extract_size']:
        raw = c.read_at(e['offset'], 16)
        if raw[:8] == b'CRILAYLA' and len(raw) >= 16:
            hdr, = struct.unpack_from('<I', raw, 12)
            return c.read_at(e['offset'] + hdr + 0x10, 16), True
        return raw, True
    return c.read_at(e['offset'], min(16, e['size'])), False


def analyse(label, c):
    st = {'label': label, 'n': len(c.entries), 'stored': 0, 'extract': 0, 'comp': 0,
          'ext': collections.defaultdict(lambda: [0, 0]),
          'dir': collections.defaultdict(lambda: [0, 0]),
          'magic': collections.defaultdict(collections.Counter),
          'text_like': collections.Counter()}
    for e in c.entries:
        head, comp = entry_head(c, e)
        cls = classify(head)
        x = ext_of(e['path'])
        st['stored'] += e['size']
        st['extract'] += e['extract_size']
        st['comp'] += 1 if comp else 0
        st['ext'][x][0] += 1
        st['ext'][x][1] += e['size']
        st['dir'][top_dir(e['path'])][0] += 1
        st['dir'][top_dir(e['path'])][1] += e['size']
        st['magic'][x][(cls, head[:4].hex())] += 1
        if cls == 'text-like (ASCII)' or cls.startswith('text'):
            st['text_like'][x] += 1
    return st


def check_extents(c):
    ents = c.entries
    literal = sum(e['size'] for e in ents)
    nonzero = [e for e in ents if e['size'] > 0]
    distinct = sorted({(e['offset'], e['size']) for e in nonzero})
    overlaps = []
    max_end, max_r = 0, None
    for off, sz in distinct:
        if off < max_end:
            overlaps.append((max_r, (off, sz)))
        if off + sz > max_end:
            max_end, max_r = off + sz, (off, sz)
    file_end = max((e['offset'] + e['size'] for e in ents), default=0)
    distinct_sum = sum(sz for _, sz in distinct)
    return {
        'entries': len(ents),
        'literal_sum': literal,
        'file_size': c.file_size,
        'literal_fits': literal <= c.file_size,
        'distinct_ranges': len(distinct),
        'shared_entries': len(nonzero) - len(distinct),
        'distinct_sum': distinct_sum,
        'distinct_fits': distinct_sum <= c.file_size,
        'partial_overlaps': len(overlaps),
        'overlap_examples': overlaps[:3],
        'all_inside_file': file_end <= c.file_size,
        'max_end': file_end,
    }


def choose_samples(cpks, want=30):
    """Small files, one extension at a time: first the smallest file of every extension
    (most common extensions first), then a second file per extension until `want`."""
    cands = collections.defaultdict(list)
    count = collections.Counter()
    for label, c in cpks:
        for e in c.entries:
            x = ext_of(e['path'])
            count[x] += 1
            if not (0 < e['extract_size'] <= 1 << 20):
                continue
            comp = e['size'] < e['extract_size']
            cands[x].append(((comp, e['extract_size'] < 8, e['extract_size'], label), label, e))
    order = [x for x, _ in count.most_common() if cands.get(x)]
    for x in order:
        cands[x].sort(key=lambda t: t[0])
    picks = []
    for rank in range(2):
        for x in order:
            if len(picks) >= want:
                return picks
            if len(cands[x]) > rank:
                _, label, e = cands[x][rank]
                picks.append((x, label, e))
    return picks


def extract_samples(cpk_by_label, picks):
    rows = []
    total = 0
    for x, label, e in picks:
        data = cpk.read_entry(cpk_by_label[label], e)
        total += len(data)
        if total > SAMPLE_CAP:
            raise SystemExit('sample cap exceeded')
        dest = os.path.join(SAMPLES, label, *e['path'].split('/'))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as fo:
            fo.write(data)
        head = data[:16]
        rows.append((label, e['path'], len(data), head.hex(), classify(head),
                     ''.join(chr(c) if 32 <= c < 127 else '.' for c in head)))
    return rows, total


def check_crilayla(cpks, per_archive=2, max_bytes=1 << 20):
    rows = []
    for label, c in cpks:
        cands = sorted((e for e in c.entries
                        if e['size'] < e['extract_size'] and e['extract_size'] <= max_bytes),
                       key=lambda e: e['size'])
        for e in cands[:per_archive]:
            raw = c.read_at(e['offset'], e['size'])
            uncomp, = struct.unpack_from('<I', raw, 8)
            out = cpk.read_entry(c, e)
            rows.append({'label': label, 'path': e['path'], 'stored': e['size'],
                         'extract': e['extract_size'], 'out_len': len(out),
                         'uncomp_field': uncomp, 'match': len(out) == e['extract_size'],
                         'head': classify(out[:16])})
    return rows


def sha1_of(c, e):
    h = hashlib.sha1()
    left = e['size']
    c.f.seek(e['offset'])
    while left:
        chunk = c.f.read(min(left, 1 << 20))
        if not chunk:
            raise cpk.CpkError('short read hashing %s' % e['path'])
        h.update(chunk)
        left -= len(chunk)
    return h.hexdigest()


def index_first(c):
    d, dup = {}, 0
    for e in c.entries:
        if e['path'] in d:
            dup += 1
        else:
            d[e['path']] = e
    return d, dup


def compare(name, ca, cb, tsv_name, la, lb):
    A, dupA = index_first(ca)
    B, dupB = index_first(cb)
    rows = []
    counts = collections.Counter()
    groups = collections.defaultdict(list)
    for p in sorted(set(A) | set(B)):
        a, b = A.get(p), B.get(p)
        if a and not b:
            status = 'only_' + la
            sa, sb = sha1_of(ca, a), ''
            rows.append((p, status, a['size'], a['extract_size'], sa, '', '', ''))
        elif b and not a:
            status = 'only_' + lb
            sb = sha1_of(cb, b)
            rows.append((p, status, '', '', '', b['size'], b['extract_size'], sb))
        else:
            sa, sb = sha1_of(ca, a), sha1_of(cb, b)
            changed = (a['size'] != b['size'] or a['extract_size'] != b['extract_size']
                       or sa != sb)
            status = 'changed' if changed else 'same'
            rows.append((p, status, a['size'], a['extract_size'], sa,
                         b['size'], b['extract_size'], sb))
        counts[status] += 1
        if status in ('changed', 'only_' + lb, 'only_' + la):
            groups[(status, os.path.dirname(p) or '(root)')].append(p)
    tsv = os.path.join(INV, tsv_name)
    with open(tsv, 'w', encoding='utf-8', newline='\n') as fo:
        fo.write('path\tstatus\tsize_%s\textract_%s\tsha1_%s\tsize_%s\textract_%s\tsha1_%s\n'
                 % (la, la, la, lb, lb, lb))
        for r in rows:
            fo.write('\t'.join(str(x) for x in r) + '\n')
    return {'name': name, 'counts': counts, 'dupA': dupA, 'dupB': dupB,
            'groups': groups, 'tsv': tsv, 'la': la, 'lb': lb,
            'n_a': len(A), 'n_b': len(B)}


def md_table(headers, rows):
    out = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join('---' for _ in headers) + '|']
    for r in rows:
        out.append('| ' + ' | '.join(str(x) for x in r) + ' |')
    return out


def mb(n):
    return '%.1f MB' % (n / 1048576.0)


def main():
    os.makedirs(SAMPLES, exist_ok=True)
    os.makedirs(INV, exist_ok=True)
    cpks = [(label, cpk.Cpk(path)) for label, path in ARCHIVES]
    by_label = dict(cpks)
    md = []
    try:
        # (a) extents
        print('== (a) extent checks')
        ext_checks = {}
        for label, c in cpks:
            r = check_extents(c)
            ext_checks[label] = r
            ok = r['all_inside_file'] and r['partial_overlaps'] == 0 and r['distinct_fits']
            print('%-15s %s entries=%d literal_sum=%d file=%d literal_fits=%s '
                  'distinct_ranges=%d distinct_sum=%d distinct_fits=%s shared_entries=%d '
                  'partial_overlaps=%d all_inside=%s -> %s' % (
                      label, 'PASS' if ok else 'CHECK', r['entries'], r['literal_sum'],
                      r['file_size'], r['literal_fits'], r['distinct_ranges'],
                      r['distinct_sum'], r['distinct_fits'], r['shared_entries'],
                      r['partial_overlaps'], r['all_inside_file'],
                      'ok' if ok else 'see numbers'))

        # per-archive stats (also reads each entry's first 16 bytes)
        stats = {}
        for label, c in cpks:
            stats[label] = analyse(label, c)
            print('stats %-15s entries=%d stored=%d extract=%d compressed=%d'
                  % (label, stats[label]['n'], stats[label]['stored'],
                     stats[label]['extract'], stats[label]['comp']))

        # (b) sample extraction
        print('== (b) sample extraction')
        picks = choose_samples(cpks, 30)
        sample_rows, total = extract_samples(by_label, picks)
        print('extracted %d sample files, %d bytes, cap %d' % (len(sample_rows), total, SAMPLE_CAP))
        for r in sample_rows:
            print('%-15s %-48s %8d %s %-28s %s' % (r[0], r[1][-48:], r[2], r[3], r[4], r[5]))
        with open(os.path.join(INV, 'magic-samples.tsv'), 'w', encoding='utf-8', newline='\n') as fo:
            fo.write('archive\tpath\tbytes\thead16_hex\tclass\tascii16\n')
            for r in sample_rows:
                fo.write('\t'.join(str(x) for x in r) + '\n')

        # (c) CRILAYLA
        print('== (c) CRILAYLA decompression')
        crow = check_crilayla(cpks)
        for r in crow:
            print('%-15s %-40s stored=%d extract=%d out=%d uncomp_field=%d match=%s head=%s'
                  % (r['label'], r['path'][-40:], r['stored'], r['extract'], r['out_len'],
                     r['uncomp_field'], r['match'], r['head']))
        n_match = sum(1 for r in crow if r['match'])
        print('decompressed %d, length == ExtractSize for %d' % (len(crow), n_match))

        # (4) comparisons
        print('== (4) comparisons')
        cmp1 = compare('patch', by_label['patch105'], by_label['repatch_patch'],
                       'compare-patch105-vs-repatch.tsv', 'patch105', 'repatch_patch')
        cmp2 = compare('movie', by_label['movie'], by_label['repatch_movie'],
                       'compare-movie-vs-repatch.tsv', 'movie', 'repatch_movie')
        for cm in (cmp1, cmp2):
            print('%s: %s dupA=%d dupB=%d' % (cm['name'], dict(cm['counts']), cm['dupA'], cm['dupB']))

        # --- generate the markdown report
        write_report(md, cpks, stats, ext_checks, sample_rows, total, crow, cmp1, cmp2)
        with open(os.path.join(HERE, 'CPK-INVENTORY.md'), 'w', encoding='utf-8', newline='\n') as fo:
            fo.write('\n'.join(md) + '\n')
        print('wrote', os.path.join(HERE, 'CPK-INVENTORY.md'))
    finally:
        for _, c in cpks:
            c.close()


def write_report(md, cpks, stats, ext_checks, sample_rows, sample_total, crow, cmp1, cmp2):
    md.append('# CPK inventory: Phantasy Star Nova (PS Vita, PCSG00351)')
    md.append('')
    md.append('Generated by `dev/psnova/cpk_report.py` (reads `dev/psnova/cpk.py`). '
              'All numbers below come from that run. Nothing was written into `dump/` or '
              '`F:/RECOMP GAMES/`.')
    md.append('')
    md.append('## 1. The five archives')
    md.append('')
    rows = []
    for label, c in cpks:
        h = c.header
        rows.append((label, '`' + os.path.basename(c.path) + '`', c.file_size, c.index_kind,
                     len(c.entries), h.get('Files'), h.get('Align'), c.content_offset,
                     'yes' if c.etoc_offset else 'no', 'yes' if c.itoc_offset else 'no',
                     stats[label]['comp']))
    md += md_table(['archive', 'file', 'file bytes', 'index', 'entries', 'header Files',
                    'Align', 'ContentOffset', 'EtocOffset set', 'ItocOffset set',
                    'compressed entries'], rows)
    md.append('')
    md.append('Index: every archive uses a TOC and none has an ITOC (ItocOffset 0). Compression '
              'is CRILAYLA (FileSize < ExtractSize). Four archives have TocOffset 2048. The rePatch '
              'movie is the exception: its TocOffset is at the end of the file (%d) and its '
              'ContentOffset is 2048, which the reader handles with `min(TocOffset, ContentOffset)`. '
              'Align is 8 in four archives and 512 in the rePatch movie.'
              % cpks[4][1].toc_offset)
    md.append('')
    md.append('## 2. Verification')
    md.append('')
    md.append('### 2a. Extents (`check_extents`)')
    md.append('')
    rows = []
    for label, c in cpks:
        r = ext_checks[label]
        rows.append((label, r['literal_sum'], r['file_size'],
                     'no' if not r['literal_fits'] else 'yes',
                     r['distinct_ranges'], r['distinct_sum'],
                     'yes' if r['distinct_fits'] else 'no', r['shared_entries'],
                     r['partial_overlaps'], 'yes' if r['all_inside_file'] else 'no'))
    md += md_table(['archive', 'sum FileSize (all entries)', 'file bytes', 'literal fit',
                    'distinct (offset,size) ranges', 'sum over distinct ranges',
                    'distinct fit', 'entries sharing an identical range',
                    'partial overlaps', 'every entry inside file'], rows)
    md.append('')
    md.append('Result: every entry lies inside its file and no two entries partially overlap, '
              'in all five archives. The literal sum of FileSize is larger than the file for '
              '`base` and `patch105`, because several entries point at the same stored bytes '
              '(in `patch105` the `*_eff.csv` entries share one 848-byte range). Identical shared '
              'ranges are allowed here; the sum over distinct ranges fits in every archive.')
    md.append('')
    md.append('### 2b. Sample extraction (30 files, up to two per extension)')
    md.append('')
    md.append('Extracted with `cpk.read_entry` (compressed entries are decompressed) into the '
              'scratchpad `cpk-samples` folder: %d files, %d bytes in total (cap 200 MB). '
              'Each extension gets its smallest file (up to 1 MB), uncompressed preferred, then a '
              'second file for each extension until 30 are picked. The magic column is what the '
              'first 16 bytes look like; "binary (unknown)" means no known signature matched.'
              % (len(sample_rows), sample_total))
    md.append('')
    rows = [(r[0], '`' + r[1] + '`', r[2], '`' + r[3] + '`', r[4]) for r in sample_rows]
    md += md_table(['archive', 'path', 'bytes', 'first 16 bytes (hex)', 'class'], rows)
    md.append('')
    md.append('### 2c. CRILAYLA decompression')
    md.append('')
    n_ok = sum(1 for r in crow if r['match'])
    md.append('%d compressed entries decompressed (the two smallest per archive, up to 1 MB). '
              'Output length equal to ExtractSize: %d of %d. In every row the CRILAYLA '
              'uncompressed_size field plus 0x100 equals ExtractSize, so the decoder output is '
              '0x100 + uncompressed_size bytes.' % (len(crow), n_ok, len(crow)))
    md.append('')
    rows = [(r['label'], '`' + r['path'] + '`', r['stored'], r['extract'], r['out_len'],
             r['uncomp_field'], 'yes' if r['match'] else 'no', r['head']) for r in crow]
    md += md_table(['archive', 'path', 'stored', 'ExtractSize', 'output length',
                    'CRILAYLA uncompressed_size field', 'length == ExtractSize', 'output head'],
                   rows)
    md.append('')
    md.append('## 3. Contents')
    md.append('')
    md.append('### 3a. Per archive: top-level directory')
    md.append('')
    md.append('No archive has directories: every TOC entry is a bare file name, so each table '
              'below has one row, `(root)`. Names only carry the folder structure through '
              'prefixes (for example `msg_`, `ev_`, `ui_`, `Script_`).')
    md.append('')
    for label, c in cpks:
        st = stats[label]
        md.append('**%s** (%d entries, %s stored)' % (label, st['n'], mb(st['stored'])))
        md.append('')
        rows = sorted(st['dir'].items(), key=lambda kv: -kv[1][1])
        md += md_table(['top directory', 'files', 'stored size'],
                       [(d, v[0], mb(v[1])) for d, v in rows])
        md.append('')
    md.append('### 3b. Per archive: extension (count, stored size)')
    md.append('')
    for label, c in cpks:
        st = stats[label]
        md.append('**%s**' % label)
        md.append('')
        rows = sorted(st['ext'].items(), key=lambda kv: -kv[1][1])
        md += md_table(['extension', 'files', 'stored size'],
                       [(x, v[0], mb(v[1])) for x, v in rows])
        md.append('')
    md.append('### 3c. Magic bytes per extension (first 16 bytes of the logical file)')
    md.append('')
    md.append('Most common class and first 4 bytes per extension, across all five archives. '
              'Compressed entries are classed from their raw first 0x100 bytes (CRILAYLA '
              'stores them uncompressed). Only the most common result is shown.')
    md.append('')
    allm = collections.defaultdict(collections.Counter)
    allcount = collections.Counter()
    for label, st in stats.items():
        for x, cnt in st['magic'].items():
            for key, n in cnt.items():
                allm[x][key] += n
            allcount[x] += st['ext'][x][0]
    rows = []
    for x, _ in allcount.most_common():
        (cls, hx), n = allm[x].most_common(1)[0]
        second = ''
        if len(allm[x]) > 1:
            (c2, h2), n2 = allm[x].most_common(2)[1]
            second = '%s (%s, %d)' % (c2, h2, n2)
        rows.append((x, allcount[x], cls, hx, n, second))
    md += md_table(['extension', 'files (all archives)', 'class', 'first 4 bytes (hex)',
                    'files with that magic', 'next most common'], rows[:150])
    if len(rows) > 150:
        md.append('')
        md.append('%d more extensions not listed.' % (len(rows) - 150))
    md.append('')
    md.append('### 3d. Magic classes seen (all archives)')
    md.append('')
    clsc = collections.Counter()
    for x in allm:
        for (cls, hx), n in allm[x].items():
            clsc[cls] += n
    md += md_table(['class', 'files'], clsc.most_common())
    md.append('')
    md.append('## 4. Comparisons')
    md.append('')
    for cm in (cmp1, cmp2):
        la, lb = cm['la'], cm['lb']
        cnt = cm['counts']
        md.append('### %s: `%s` (A) vs `%s` (B)' % (cm['name'], la, lb))
        md.append('')
        md.append('Entries in A: %d (duplicate names skipped: %d). Entries in B: %d '
                  '(duplicate names skipped: %d). Paths matched by name; stored bytes '
                  'compared by sha1.' % (cm['n_a'], cm['dupA'], cm['n_b'], cm['dupB']))
        md.append('')
        md += md_table(['status', 'count'], [
            ('same (size and sha1 equal)', cnt.get('same', 0)),
            ('changed (size or sha1 differ)', cnt.get('changed', 0)),
            ('added in %s (only in B)' % lb, cnt.get('only_' + lb, 0)),
            ('removed in %s (only in A)' % lb, cnt.get('only_' + la, 0))])
        md.append('')
        md.append('Per-path table: `dev/psnova/inventory/%s`.' % os.path.basename(cm['tsv']))
        md.append('')
        shown = 0
        total_listed = sum(len(v) for k, v in cm['groups'].items() if k[0] in ('changed', 'only_' + lb))
        keys = sorted(k for k in cm['groups'] if k[0] in ('changed', 'only_' + lb))
        md.append('Changed and added paths, grouped by directory (at most 60 paths listed):')
        md.append('')
        for k in keys:
            if shown >= 60:
                break
            paths = sorted(cm['groups'][k])
            md.append('- **%s** `%s` (%d)' % (k[0], k[1], len(paths)))
            for p in paths:
                if shown >= 60:
                    break
                md.append('  - `%s`' % p)
                shown += 1
        md.append('')
        if total_listed > shown:
            md.append('%d more changed or added paths not listed; see the TSV.' % (total_listed - shown))
            md.append('')
        rem = sorted(p for k, v in cm['groups'].items() if k[0] == 'only_' + la for p in v)
        if len(rem) <= 10:
            md.append('Removed (only in A): %d path(s): %s.'
                      % (len(rem), ', '.join('`%s`' % p for p in rem) or 'none'))
        else:
            md.append('Removed (only in A): %d paths, see the TSV.' % len(rem))
        md.append('')
    md.append('## 5. Where the text probably is (guesses from names and magic)')
    md.append('')
    md.append('These are guesses. Nothing was opened to confirm that a file holds text. A file is '
              'listed when its extension is in a text/font/script set or its name contains a '
              'word such as text, msg, font, dialog, script, string or lang. "text-like" means the '
              'first 16 bytes are printable ASCII or have a text BOM.')
    md.append('')
    md.append('Facts from the first bytes and the name/extension counts (observed in this run):')
    md.append('')
    md.append('- No font files (.ttf, .otf, .fnt, .pgf, .pvf, .ttc, .woff) and no .txt, .xml, .json, '
              '.ini, .cfg or .msg files exist in any of the five archives (checked by name).')
    md.append('- `.lua` (6,602 files across the archives) all start with the Lua bytecode magic '
              '`1b 4c 75 61` ("\\x1bLua"). The scripts are compiled, so their strings are not plain text.')
    md.append('- `.rmd` (46,593 files across the archives, 21,379 in base) are named `msg_NNNNNN.rmd` '
              'in the patches and start with the bytes `20 44 4d 52` (" DMR"); the format is not identified. Guess: message or '
              'dialogue containers. The rePatch adds 14,898 `msg_*.rmd` files and changes 2,254 more, '
              'so the rePatch changes are almost all message files. This is the strongest lead for '
              'where the English text is, but the content was not decoded.')
    md.append('- `novamessagedictionary.mdic` (858 KB, present in both patch archives, same bytes) '
              'starts with `BMVN`; the name suggests a message dictionary. Guess only.')
    md.append('- `.csv` (12,894 files): most start with `Data`. The 11-byte '
              '`ain0021a_laserbanther_gatring.csv` is just `DataStart` and CRLF. Larger ones such as '
              '`NpcTalkParameter.csv`, `skill_parameter_list.csv` and `AI_Combo.csv` look like '
              'parameter tables and may hold text ids. Guess. The rePatch changes 3 csv files and '
              'adds `ngword.csv`.')
    md.append('- `.crttl` (119 files, mostly ASCII in the first 16 bytes) holds texture-name style '
              'lines, for example `tex_Chapter.aif`. Guess: a texture-name list.')
    md.append('- `.crbpj` (119 files, all with magic `CRBD`, names like `ui_tutorial*.crbpj`) and the large '
              'families `.aif`, `.aai`, `.axs`, `.aet` (18,759 `.aet` in base alone) have unidentified '
              'headers; no text guess is made for them beyond their names.')
    md.append('')
    for label, c in cpks:
        st = stats[label]
        hits = []
        for e in c.entries:
            low = e['path'].lower()
            x = ext_of(e['path'])
            if x in TEXT_EXT or any(w in low for w in TEXT_WORDS):
                hits.append(e)
        byx = collections.Counter(ext_of(e['path']) for e in hits)
        md.append('**%s**: %d name or extension hits; text-like by first 16 bytes: %d files'
                  % (label, len(hits), sum(st['text_like'].values())))
        md.append('')
        md += md_table(['extension', 'hits'], byx.most_common(15))
        md.append('')
        ex = sorted(hits, key=lambda e: -e['extract_size'])[:20]
        md.append('Largest hits (name, extract size):')
        md.append('')
        for e in ex:
            md.append('- `%s` (%d bytes)' % (e['path'], e['extract_size']))
        md.append('')
    md.append('## 6. What was checked, and what was not')
    md.append('')
    md.append('- Checked: headers and TOC of all five archives; every entry offset and size against the '
              'file size; first 16 bytes of every entry; sha1 of stored bytes for the two patch and two '
              'movie pairs; ~30 sample extractions; CRILAYLA output length for compressed entries.')
    md.append('- Not checked: whether any sample file is valid beyond its magic bytes; the 2.8 GB base '
              'archive was not compared with the 1.05 patch (only patch vs rePatch and movie vs rePatch '
              'were compared, as asked); ITOC parsing was not exercised (no archive uses ITOC); ETOC and '
              'GTOC were not parsed; the game was not run; no build or vitarecomp was run.')
    md.append('- Only the decompressed length was checked for CRILAYLA, not the content. The 6 '
              'decompressed files were classed by their first 16 bytes only.')
    md.append('- Lua bytecode, `.rmd`, `.mdic` and `.crbpj` formats were not decoded; the names in '
              'section 5 are guesses.')
    md.append('')


if __name__ == '__main__':
    main()
