#!/usr/bin/env python3
"""cpk_build.py - rebuild a flat CRI CPK (TOC first, content, ETOC last; e.g. NOVA_FileList_Vita_patch.cpk) with entries
replaced or added from files. Written 2026-11-18 for the Phantasy Star Nova localization (cpk_merge.py can only add a few
entries into the slack before the content area; a translation replaces and adds thousands).

  cpk_build.py <base.cpk> <out.cpk> <folder with the new files>      (every file in the folder: replace or add by name)

Rules: entries keep their stored bytes (compressed or not), ID and ETOC row; a replaced entry is stored uncompressed
(FileSize = ExtractSize) under its old ID; an added entry gets the next free ID and the ETOC row of the base's first entry.
TOC rows are kept in the base's order rule (upper-cased name, byte order). Layout: the header region up to TocOffset as in
the base, the TOC at the same offset, content from the next 0x800 boundary, each entry 8-aligned (Align), ETOC after the
content. The header's ContentOffset, ContentSize, TocSize, EtocOffset, EtocSize, Files, EnabledPackedSize (2 x sum of
ExtractSize) and EnabledDataSize (sum ExtractSize + sum FileSize; both formulas checked on the base first) are updated.
The result is read back with cpk.py and every entry's stored bytes are compared.
"""
import bisect, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'pipeline', 'cri'))
import cpk as C            # noqa: E402
import cpk_merge as M      # noqa: E402


def roundup(x, a):
    return (x + a - 1) // a * a


def build(base_path, out_path, files, log=print):
    if os.path.abspath(out_path) == os.path.abspath(base_path) or (
            os.path.exists(out_path) and os.path.samefile(out_path, base_path)):
        raise C.CpkError('out must differ from base (the base would be destroyed)')
    base = C.Cpk(base_path); h = base.header; f = base.f
    upper = {e['path'].upper(): e['path'] for e in base.entries}
    files = {upper.get(n.upper(), n): d for n, d in files.items()}   # a name differing only in case replaces the entry
    for k in ('ItocOffset', 'GtocOffset', 'HtocOffset', 'HgtocOffset'):
        if h.get(k):
            raise C.CpkError('%s present; not supported' % k)
    align = int(h['Align'])
    toc_off, content, etoc_off = base.toc_offset, base.content_offset, base.etoc_offset
    if not (toc_off < content < etoc_off):
        raise C.CpkError('expects TOC, content, ETOC in that order')
    toc_flag, toc_size, toc = M.read_chunk(f, toc_off, b'TOC ')
    etoc_flag, etoc_size, etoc = M.read_chunk(f, etoc_off, b'ETOC')
    n0 = len(base.entries)
    sentinel = etoc.nrows == n0 + 1
    if etoc.nrows not in (n0, n0 + 1):
        raise C.CpkError('unexpected ETOC rows')
    names = [e['path'] for e in base.entries]
    if [x.upper() for x in names] != sorted(x.upper() for x in names):
        raise C.CpkError('base TOC not sorted by upper-cased name')
    sum_e = sum(e['extract_size'] for e in base.entries); sum_s = sum(e['size'] for e in base.entries)
    if int(h['EnabledPackedSize']) != 2 * sum_e or int(h['EnabledDataSize']) != sum_e + sum_s:
        raise C.CpkError('Enabled*Size formulas do not hold for the base')
    tbase = min(toc_off, content)

    def colpos(name):
        return toc.col(name)[4], toc.col(name)[2]
    rows = list(toc.rows)
    strings = bytearray(toc.strings)
    etoc_rows = list(etoc.rows[:n0])
    etoc_tail = list(etoc.rows[n0:])
    items = [dict(name=e['path'], id=e['id'], size=e['size'], esize=e['extract_size'], src=('base', e['offset']))
             for e in base.entries]
    index = {it['name']: i for i, it in enumerate(items)}
    maxid = max(e['id'] for e in base.entries)
    keys = [x.upper() for x in names]
    replaced = added = 0
    for name in sorted(files, key=str.upper):
        data = files[name]
        if name in index:
            it = items[index[name]]
            it.update(size=len(data), esize=len(data), src=('new', data)); replaced += 1
        else:
            maxid += 1
            pos = bisect.bisect_left(keys, name.upper())
            row = bytearray(toc.rw)
            fo, ft = colpos('FileName')
            struct.pack_into('>I', row, fo, len(strings)); strings += name.encode('utf-8') + b'\0'
            items.insert(pos, dict(name=name, id=maxid, size=len(data), esize=len(data), src=('new', data)))
            rows.insert(pos, bytes(row)); etoc_rows.insert(pos, etoc.rows[0]); keys.insert(pos, name.upper())
            index = {x['name']: i for i, x in enumerate(items)}
            added += 1
    # offsets: content from the 0x800 boundary after the new TOC
    probe = toc.serialise(rows, bytes(strings))
    toc_len = 16 + len(probe)
    new_content = roundup(toc_off + toc_len, 0x800)
    cur = new_content
    placed = {}                      # entries of the base that share stored bytes (same offset and size) stay shared
    for it in items:
        key = ('base', it['src'][1], it['size']) if it['src'][0] == 'base' else None
        if key in placed:
            it['abs'] = placed[key]; it['shared'] = True; continue
        it['abs'] = cur; cur = roundup(cur + it['size'], align)
        if key:
            placed[key] = it['abs']
    data_end = cur
    final_rows = []
    for it, row in zip(items, rows):
        row = bytearray(row)
        for nm in ('FileSize', 'ExtractSize', 'FileOffset', 'ID'):
            rfo, ct = colpos(nm)
            v = {'FileSize': it['size'], 'ExtractSize': it['esize'], 'FileOffset': it['abs'] - toc_off, 'ID': it['id']}[nm]
            struct.pack_into(C.TYPE_FMT[ct], row, rfo, v)
        final_rows.append(bytes(row))
    new_toc = toc.serialise(final_rows, bytes(strings))
    new_etoc = etoc.serialise(etoc_rows + etoc_tail, etoc.strings)
    toc_blob = struct.pack('<4sIQ', b'TOC ', toc_flag, len(new_toc)) + (C.unscramble(new_toc) if toc.scrambled else new_toc)
    etoc_blob = struct.pack('<4sIQ', b'ETOC', etoc_flag, len(new_etoc)) + (C.unscramble(new_etoc) if etoc.scrambled else new_etoc)
    assert len(toc_blob) == toc_len
    # header table
    f.seek(0); head = bytearray(f.read(toc_off))
    hl = struct.unpack_from('<4sIQ', head, 0)[2]
    hraw = bytes(head[0x10:0x10 + hl]); hs = hraw[:4] != b'@UTF'
    hraw = C.unscramble(hraw) if hs else hraw
    ht = M.Table(hraw, hs); hrow = bytearray(ht.rows[0])

    def setf(name, v):
        _, fl, ct, cv, rfo = ht.col(name)
        if rfo is None:
            raise C.CpkError('header column %s is not per-row' % name)
        struct.pack_into(C.TYPE_FMT[ct], hrow, rfo, v)
    se = sum(it['esize'] for it in items); ss = sum(it['size'] for it in items)
    setf('ContentOffset', new_content); setf('ContentSize', data_end - new_content)
    setf('TocSize', len(toc_blob)); setf('EtocOffset', data_end); setf('EtocSize', len(etoc_blob))
    setf('Files', len(items)); setf('EnabledPackedSize', 2 * se); setf('EnabledDataSize', se + ss)
    hnew = bytearray(hraw); hnew[ht.rowbase:ht.rowbase + ht.rw] = bytes(hrow)
    hnew = C.unscramble(bytes(hnew)) if hs else bytes(hnew)
    head[0x10:0x10 + len(hnew)] = hnew
    with open(out_path, 'wb') as out:
        out.write(head); out.write(toc_blob)
        out.write(b'\0' * (new_content - out.tell()))
        for it in items:
            if it.get('shared'):
                continue
            assert out.tell() <= it['abs']
            out.write(b'\0' * (it['abs'] - out.tell()))
            if it['src'][0] == 'base':
                out.write(base.read_at(it['src'][1], it['size']))
            else:
                out.write(it['src'][1])
        out.write(b'\0' * (data_end - out.tell()))
        out.write(etoc_blob)
    # read back
    chk = C.Cpk(out_path)
    got = {e['path']: e for e in chk.entries}
    if len(got) != len(items):
        raise C.CpkError('read-back: entry count differs')
    for it in items:
        e = got[it['name']]
        want = base.read_at(it['src'][1], it['size']) if it['src'][0] == 'base' else it['src'][1]
        if e['size'] != it['size'] or e['extract_size'] != it['esize'] or chk.read_at(e['offset'], e['size']) != want:
            raise C.CpkError('read-back: %s differs' % it['name'])
    chk.close(); base.close()
    log('wrote %s (%d bytes): %d entries, %d replaced, %d added; all entries read back equal' % (
        out_path, os.path.getsize(out_path), len(items), replaced, added))


def main():
    base, out, folder = sys.argv[1:4]
    files = {n: open(os.path.join(folder, n), 'rb').read() for n in sorted(os.listdir(folder))
             if os.path.isfile(os.path.join(folder, n))}
    build(base, out, files)


if __name__ == '__main__':
    main()
