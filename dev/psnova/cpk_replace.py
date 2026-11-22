#!/usr/bin/env python3
"""cpk_replace.py - copy an UNCOMPRESSED CRI CPK and replace the data of named entries (written 2026-11-18; generalised the
same evening for the game's own movie archive, whose TOC comes BEFORE the content).

  cpk_replace.py <base.cpk> <out.cpk> --replace <entry name>=<file> [--replace ...]

Made for NOVA_FileList_Vita_movie.cpk (21 mp4 entries, stored uncompressed). Two layouts are handled:
  - the fan rePatch's: content first, TOC and ETOC after the content, Align 512
  - the game's own: TOC at 2048, content from 3176, ETOC last, Align 8 (Version 7, ContentSize present,
    EnabledPackedSize = EnabledDataSize = 2 x sum of the file sizes)
Entry order, names, ETOC rows and every other entry's bytes stay as they are; the content is laid out again from ContentOffset
with each entry aligned to Align, in the order the data lies in the file, so a replacement may be larger or smaller. Then the
TOC (FileSize, ExtractSize, FileOffset) is rewritten and the header's TocOffset, TocSize, EtocOffset, EtocSize, ContentSize
(when present), EnabledPackedSize and EnabledDataSize are updated. The result is read back with cpk.py and every entry is
compared with its source bytes before the tool reports success. It refuses archives with compressed entries or ITOC/GTOC/HTOC.

Reuses pipeline/cri/cpk.py and cpk_merge.py (Table class) unchanged; see dev/psnova/CPK-MERGE.md for the format facts.
"""
import argparse, os, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'pipeline', 'cri'))
import cpk as C            # noqa: E402
import cpk_merge as M      # noqa: E402


def roundup(x, a):
    return (x + a - 1) // a * a


def replace(base_path, out_path, repl, log=print):
    base = C.Cpk(base_path)
    h = base.header
    for k in ('ItocOffset', 'GtocOffset', 'HtocOffset', 'HgtocOffset'):
        if h.get(k):
            raise C.CpkError('%s present; not supported' % k)
    align = int(h['Align'])
    content, toc_off, etoc_off = base.content_offset, base.toc_offset, base.etoc_offset
    if not (toc_off and etoc_off):
        raise C.CpkError('expects a TOC and an ETOC')
    toc_first = toc_off < content          # the game's own movie archive: TOC at 2048, content, ETOC last
    if not toc_first and not (content < toc_off < etoc_off):
        raise C.CpkError('expects TOC, content, ETOC or content, TOC, ETOC')
    if any(e['size'] != e['extract_size'] for e in base.entries):
        raise C.CpkError('compressed entries present; not supported')
    names = [e['path'] for e in base.entries]
    for n in repl:
        if names.count(n) != 1:
            raise C.CpkError('entry %r found %d times' % (n, names.count(n)))
    f = base.f
    toc_flag, toc_size, toc = M.read_chunk(f, toc_off, b'TOC ')
    etoc_flag, etoc_size, etoc = M.read_chunk(f, etoc_off, b'ETOC')
    if toc.nrows != len(names):
        raise C.CpkError('TOC rows differ from entries')
    tbase = min(toc_off, content)          # FileOffset is relative to min(TocOffset, ContentOffset)

    # header region before the content (CPK chunk, padding, and the TOC when it comes first), tables patched below
    f.seek(0)
    head_region = bytearray(f.read(content))

    # lay out the content again, in the order the data lies in the file (offset order); rows keep their TOC order
    order = sorted(range(len(base.entries)), key=lambda i: base.entries[i]['offset'])
    datas = []
    new_rows = [None] * len(names)
    cur = content
    for i in order:
        e = base.entries[i]
        if e['path'] in repl:
            with open(repl[e['path']], 'rb') as g:
                data = g.read()
        else:
            data = base.read_at(e['offset'], e['size'])
            if len(data) != e['size']:
                raise C.CpkError('short read of %s' % e['path'])
        row = bytearray(toc.rows[i])
        for (nm, fl, ct, cv, rfo) in toc.cols:
            if rfo is None:
                continue
            if nm == 'FileSize' or nm == 'ExtractSize':
                struct.pack_into(C.TYPE_FMT[ct], row, rfo, len(data))
            elif nm == 'FileOffset':
                struct.pack_into(C.TYPE_FMT[ct], row, rfo, cur - tbase)
        new_rows[i] = bytes(row)
        datas.append((cur, data))
        cur = roundup(cur + len(data), align)
    content_end = cur
    new_toc = toc.serialise(new_rows, toc.strings)
    toc_blob = struct.pack('<4sIQ', b'TOC ', toc_flag, len(new_toc)) + (C.unscramble(new_toc) if toc.scrambled else new_toc)
    new_etoc = etoc.serialise(etoc.rows, etoc.strings)
    etoc_blob = struct.pack('<4sIQ', b'ETOC', etoc_flag, len(new_etoc)) + (C.unscramble(new_etoc) if etoc.scrambled else new_etoc)
    if toc_first:
        old_toc_len = 16 + toc_size
        if len(toc_blob) != old_toc_len:
            raise C.CpkError('TOC size changed (%d -> %d) with the TOC before the content' % (old_toc_len, len(toc_blob)))
        head_region[toc_off:toc_off + len(toc_blob)] = toc_blob
        new_toc_off = toc_off
        new_etoc_off = content_end
    else:
        new_toc_off = content_end
        new_etoc_off = new_toc_off + roundup(len(toc_blob), align)

    # header table, patched in place
    hdr = struct.unpack_from('<4sIQ', head_region, 0)
    hraw = bytes(head_region[0x10:0x10 + hdr[2]])
    scrambled = hraw[:4] != b'@UTF'
    if scrambled:
        hraw = C.unscramble(hraw)
    ht = M.Table(hraw, scrambled)
    row = bytearray(ht.rows[0])

    def setf(name, v):
        _, fl, ct, cv, rfo = ht.col(name)
        if rfo is None:
            raise C.CpkError('header column %s is not per-row' % name)
        struct.pack_into(C.TYPE_FMT[ct], row, rfo, v)

    total = sum(len(d) for _, d in datas)
    old_sum = sum(e['size'] for e in base.entries)
    setf('TocOffset', new_toc_off)
    setf('TocSize', len(toc_blob))
    setf('EtocOffset', new_etoc_off)
    setf('EtocSize', len(etoc_blob))
    if h.get('ContentSize') is not None:
        setf('ContentSize', content_end - content)
    pk, dk = int(h['EnabledPackedSize']), int(h['EnabledDataSize'])
    if pk == old_sum and dk == old_sum:                  # the rePatch movie archive: plain sums
        setf('EnabledPackedSize', total)
        setf('EnabledDataSize', total)
    elif pk == 2 * old_sum and dk == 2 * old_sum:         # the game's own: 2 x sum (FileSize + ExtractSize, stored uncompressed)
        setf('EnabledPackedSize', 2 * total)
        setf('EnabledDataSize', 2 * total)
    else:
        log('WARNING: Enabled*Size is not a known function of the file sizes in the base; left unchanged')
    hnew = bytearray(hraw)
    hnew[ht.rowbase:ht.rowbase + ht.rw] = bytes(row)
    hnew = C.unscramble(bytes(hnew)) if scrambled else bytes(hnew)
    head_region[0x10:0x10 + len(hnew)] = hnew

    with open(out_path, 'wb') as out:
        out.write(head_region)
        for at, data in datas:
            if out.tell() > at:
                raise C.CpkError('internal: offset overrun')
            out.write(b'\0' * (at - out.tell()))
            out.write(data)
        if toc_first:
            out.write(b'\0' * (new_etoc_off - out.tell()))
            out.write(etoc_blob)
        else:
            out.write(b'\0' * (new_toc_off - out.tell()))
            out.write(toc_blob)
            out.write(b'\0' * (new_etoc_off - out.tell()))
            out.write(etoc_blob)
        f.seek(etoc_off + 16 + etoc_size)
        out.write(f.read())               # whatever the base had after its ETOC (nothing)

    # read back and compare every entry
    chk = C.Cpk(out_path)
    if [e['path'] for e in chk.entries] != names:
        raise C.CpkError('read-back: entry names differ')
    for e0, e1 in zip(base.entries, chk.entries):
        if e0['path'] in repl:
            with open(repl[e0['path']], 'rb') as g:
                want = g.read()
        else:
            want = base.read_at(e0['offset'], e0['size'])
        got = chk.read_at(e1['offset'], e1['size'])
        if got != want or e1['size'] != len(want) or e1['extract_size'] != len(want):
            raise C.CpkError('read-back: entry %s differs' % e0['path'])
    log('wrote %s (%d bytes, base %d); replaced %s; all %d entries read back equal' % (
        out_path, os.path.getsize(out_path), os.path.getsize(base_path), sorted(repl), len(names)))
    chk.close()
    base.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base'); ap.add_argument('out')
    ap.add_argument('--replace', action='append', default=[], metavar='NAME=FILE')
    a = ap.parse_args()
    repl = {}
    for s in a.replace:
        n, _, p = s.partition('=')
        repl[n] = p
    replace(a.base, a.out, repl)


if __name__ == '__main__':
    main()
