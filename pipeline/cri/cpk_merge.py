#!/usr/bin/env python3
"""cpk_merge.py - copy a CRI CPK archive and add entries taken from another CPK.

  cpk_merge.py <base.cpk> <out.cpk> --add <source.cpk>:<entry name> [--add ...]

Stored bytes of the added entries are copied verbatim (compressed or not) with their
FileSize / ExtractSize. Everything in the base keeps its stored bytes and TOC values
(FileOffset, ID, sizes). Only supports archives with a TOC + ETOC and no ITOC/GTOC/HTOC
(the PS Nova patch archives); anything else is refused, not guessed.

Layout (see CPK-MERGE.md): the header table is patched in place, the TOC is rewritten at
the same offset (it grows into the zero slack before ContentOffset, so ContentOffset and
every base FileOffset stay put), new file data is appended after the old content area
(8-aligned, the header's Align), and a new ETOC follows it.
Imports cpk.py from the same folder (read only).
"""

import argparse
import bisect
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpk as C  # noqa: E402

CHUNK = struct.Struct('<4sIQ')  # magic, flag, size
UTF_HEAD = struct.Struct('>IHHIIIHHI')  # tsize ver rows str data name ncols rowwidth nrows


def roundup(x, a):
    return (x + a - 1) // a * a


class Table:
    """One @UTF table, held unscrambled, with enough structure to edit rows."""

    def __init__(self, raw, scrambled):
        self.scrambled = scrambled
        self.raw = raw
        (self.tsize, self.ver, self.ro, self.so, self.do, self.no, self.ncols,
         self.rw, self.nrows) = UTF_HEAD.unpack_from(raw, 4)
        self.cols = []  # (name, flags, ctype, const_value, row_field_offset)
        pos, rowpos = 0x20, 0
        strbase, database = 8 + self.so, 8 + self.do
        for _ in range(self.ncols):
            flags = raw[pos]
            pos += 1
            noff, = struct.unpack_from('>I', raw, pos)
            pos += 4
            name = C.cstr(raw, strbase + noff)
            ctype = flags & 15
            store = flags & 0xF0
            const = None
            rfo = None
            if store in C.STORE_CONST:
                const = C._value(raw, pos, ctype, strbase, database)
                pos += C.TYPE_SIZE[ctype]
            elif store == C.STORE_ROW:
                rfo = rowpos
                rowpos += C.TYPE_SIZE[ctype]
            self.cols.append((name, flags, ctype, const, rfo))
        if rowpos != self.rw:
            raise C.CpkError('row width mismatch')
        self.coldefs_end = pos
        self.rowbase = 8 + self.ro
        self.rows = [raw[self.rowbase + i * self.rw: self.rowbase + (i + 1) * self.rw]
                     for i in range(self.nrows)]
        self.strings = raw[strbase:database]
        if 8 + self.tsize != len(raw) or database != len(raw):
            raise C.CpkError('table has a data area or trailing bytes; unsupported')

    def col(self, name):
        for c in self.cols:
            if c[0] == name:
                return c
        raise KeyError(name)

    def get_str(self, row, name):
        n, flags, ctype, const, rfo = self.col(name)
        if rfo is None:
            return const
        off, = struct.unpack_from('>I', row, rfo)
        return C.cstr(self.raw, 8 + self.so + off)

    def serialise(self, rows, strings):
        """Rebuild the table: same column defs, given row blobs and strings area.
        The strings area must already include any padding; total length is kept 8-aligned."""
        head = bytearray(self.raw[:self.coldefs_end])
        # keep any bytes between column defs and rows (none in practice)
        gap = self.raw[self.coldefs_end:self.rowbase]
        body = bytes(head) + gap + b''.join(rows)
        so_new = len(body) - 8
        total = len(body) + len(strings)
        pad = (-total) % 8
        strings = strings + b'\0' * pad
        out = bytearray(body + strings)
        do_new = len(out) - 8
        UTF_HEAD.pack_into(out, 4, do_new, self.ver, self.ro, so_new, do_new, self.no,
                           self.ncols, self.rw, len(rows))
        return bytes(out)


def read_chunk(f, off, magic):
    f.seek(off)
    h = f.read(16)
    m, flag, size = struct.unpack('<4sIQ', h)
    if m != magic:
        raise C.CpkError('expected %r at 0x%x, got %r' % (magic, off, m))
    f.seek(off + 16)
    raw = f.read(size)
    scrambled = raw[:4] != b'@UTF'
    if scrambled:
        raw = C.unscramble(raw)
    if raw[:4] != b'@UTF':
        raise C.CpkError('no @UTF in %r chunk' % magic)
    return flag, size, Table(raw, scrambled)


def merge(base_path, out_path, adds, log=print):
    base = C.Cpk(base_path)
    h = base.header
    for k in ('ItocOffset', 'GtocOffset', 'HtocOffset', 'HgtocOffset'):
        if h.get(k):
            raise C.CpkError('base has %s; not supported by this tool' % k)
    if not base.toc_offset or not base.etoc_offset:
        raise C.CpkError('base needs both TOC and ETOC')
    align = int(h['Align'])
    toc_off, etoc_off, content = base.toc_offset, base.etoc_offset, base.content_offset
    tbase = min(toc_off, content)

    f = base.f
    toc_flag, toc_size, toc = read_chunk(f, toc_off, b'TOC ')
    etoc_flag, etoc_size, etoc = read_chunk(f, etoc_off, b'ETOC')
    if toc_size != 8 + toc.tsize or etoc_size != 8 + etoc.tsize:
        raise C.CpkError('chunk size does not match table size')
    if toc.nrows != len(base.entries):
        raise C.CpkError('TOC row count differs from entries')
    if etoc.nrows not in (toc.nrows, toc.nrows + 1):
        raise C.CpkError('unexpected ETOC row count %d' % etoc.nrows)
    sentinel = etoc.nrows == toc.nrows + 1

    # ordering rule of the base: byte order of the upper-cased path
    names = [e['path'] for e in base.entries]
    keys = [n.upper() for n in names]
    if keys != sorted(keys):
        raise C.CpkError('base TOC is not sorted by upper-cased name; rule unknown')
    for r in toc.rows[:50]:
        if toc.get_str(r, 'DirName'):
            raise C.CpkError('directory names present; this tool handles flat archives only')

    if len(base.entries) and base.entries[-1]['offset'] + base.entries[-1]['size'] > etoc_off:
        raise C.CpkError('entry data past ETOC offset')
    end_of_data = etoc_off
    if end_of_data % align:
        raise C.CpkError('ETOC offset not aligned')

    # collect additions
    new = []
    for spec in adds:
        src_path, _, ename = spec.rpartition(':')
        if len(src_path) <= 1 and ':' not in spec[2:]:
            raise C.CpkError('--add needs <source.cpk>:<entry name>')
        src = C.Cpk(src_path)
        idx = [i for i, e in enumerate(src.entries) if e['path'] == ename]
        if len(idx) != 1:
            raise C.CpkError('%s: entry %r found %d times' % (src_path, ename, len(idx)))
        e = src.entries[idx[0]]
        if ename in names or any(n['name'] == ename for n in new):
            raise C.CpkError('entry %r already in the base' % ename)
        data = src.read_at(e['offset'], e['size'])
        if len(data) != e['size']:
            raise C.CpkError('short read of source entry')
        s_etoc_off = src.etoc_offset
        s_etoc = None
        if s_etoc_off:
            _, _, s_etoc = read_chunk(src.f, s_etoc_off, b'ETOC')
        s_toc_flag, s_toc_size, s_toc = read_chunk(src.f, src.toc_offset, b'TOC ')
        s_row = s_toc.rows[idx[0]]
        # constants must agree, otherwise a column would have to change storage
        for (nm, fl, ct, cv, rfo) in toc.cols:
            if rfo is None and nm not in ('DirName',):
                sc = s_toc.col(nm)
                if sc[3] != cv:
                    raise C.CpkError('constant column %s differs (%r vs %r)' % (nm, cv, sc[3]))
        etoc_vals = None
        if s_etoc is not None:
            etoc_vals = s_etoc.rows[idx[0]]
            if [c[:3] for c in s_etoc.cols] != [c[:3] for c in etoc.cols]:
                raise C.CpkError('ETOC columns differ between base and source')
        new.append(dict(name=ename, data=data, size=e['size'], esize=e['extract_size'],
                        etoc_row=etoc_vals, src=src_path, src_id=e['id']))
        src.close()
    new.sort(key=lambda n: n['name'].upper())

    # assign data offsets (appended after the old content area)
    cur = end_of_data
    for n in new:
        n['abs'] = cur
        cur = roundup(cur + n['size'], align)
    new_data_end = cur

    # ids: keep every existing ID; new ones continue after the maximum
    maxid = max(e['id'] for e in base.entries)
    for i, n in enumerate(new):
        n['id'] = maxid + 1 + i

    # new TOC rows, inserted at their sorted position
    rows = list(toc.rows)
    strings = bytearray(toc.strings)
    etoc_rows = list(etoc.rows)
    ins_keys = list(keys)
    for n in new:
        pos = bisect.bisect_left(ins_keys, n['name'].upper())
        n['row'] = pos
        row = bytearray(toc.rw)
        for (nm, fl, ct, cv, rfo) in toc.cols:
            if rfo is None:
                continue
            if nm == 'FileName':
                v = len(strings)
                strings += n['name'].encode('utf-8') + b'\0'
            elif nm == 'FileSize':
                v = n['size']
            elif nm == 'ExtractSize':
                v = n['esize']
            elif nm == 'FileOffset':
                v = n['abs'] - tbase
            elif nm == 'ID':
                v = n['id']
            else:
                raise C.CpkError('per-row TOC column %s has no rule' % nm)
            if ct == 0x0A:
                struct.pack_into('>I', row, rfo, v)
            else:
                struct.pack_into(C.TYPE_FMT[ct], row, rfo, v)
        rows.insert(pos, bytes(row))
        ins_keys.insert(pos, n['name'].upper())
        er = n['etoc_row'] if n['etoc_row'] is not None else bytes(etoc.rw)
        etoc_rows.insert(pos, er)
    new_toc = toc.serialise(rows, bytes(strings))
    new_etoc = etoc.serialise(etoc_rows, etoc.strings)

    toc_chunk = CHUNK.pack(b'TOC ', toc_flag, len(new_toc))
    etoc_chunk = CHUNK.pack(b'ETOC', etoc_flag, len(new_etoc))
    toc_blob = toc_chunk + (C.unscramble(new_toc) if toc.scrambled else new_toc)
    etoc_blob = etoc_chunk + (C.unscramble(new_etoc) if etoc.scrambled else new_etoc)

    if toc_off + len(toc_blob) > content:
        raise C.CpkError('new TOC does not fit before ContentOffset (%d > %d)'
                         % (toc_off + len(toc_blob), content))
    # the slack we grow into must be all zero in the base
    f.seek(toc_off + 16 + toc_size)
    slack = f.read(content - (toc_off + 16 + toc_size))
    if any(slack):
        raise C.CpkError('slack between TOC and content is not zero')

    # header table: patch in place (same size)
    f.seek(0)
    head_region = bytearray(f.read(content if content < toc_off else toc_off))
    hflag_hdr = struct.unpack_from('<4sIQ', head_region, 0)
    h_off = 0x10
    hdr_scrambled = bytes(head_region[h_off:h_off + 4]) != b'@UTF'
    hraw = bytes(head_region[h_off:h_off + hflag_hdr[2]])
    hraw = C.unscramble(hraw) if hdr_scrambled else hraw
    htab = Table(hraw, hdr_scrambled)
    row = bytearray(htab.rows[0])
    sizes_new = sum(n['size'] for n in new)
    esizes_new = sum(n['esize'] for n in new)

    def setf(name, v):
        _, fl, ct, cv, rfo = htab.col(name)
        if rfo is None:
            raise C.CpkError('header column %s is not per-row' % name)
        struct.pack_into(C.TYPE_FMT[ct], row, rfo, v)

    new_etoc_off = new_data_end
    setf('ContentSize', new_data_end - content)
    setf('TocSize', len(toc_blob))
    setf('EtocOffset', new_etoc_off)
    setf('EtocSize', len(etoc_blob))
    setf('Files', int(h['Files']) + len(new))
    # EnabledPackedSize = 2*sum(ExtractSize), EnabledDataSize = sum(ExtractSize)+sum(FileSize)
    # (both formulas verified on the base and on the 1.05 archive before use)
    sum_e = sum(e['extract_size'] for e in base.entries)
    sum_s = sum(e['size'] for e in base.entries)
    if int(h['EnabledPackedSize']) != 2 * sum_e or int(h['EnabledDataSize']) != sum_e + sum_s:
        log('WARNING: Enabled*Size formula does not hold for base; left unchanged')
    else:
        setf('EnabledPackedSize', 2 * (sum_e + esizes_new))
        setf('EnabledDataSize', sum_e + esizes_new + sum_s + sizes_new)
    hnew = bytearray(hraw)
    hnew[htab.rowbase:htab.rowbase + htab.rw] = bytes(row)
    hnew = C.unscramble(bytes(hnew)) if hdr_scrambled else bytes(hnew)
    head_region[h_off:h_off + len(hnew)] = hnew

    # write
    with open(out_path, 'wb') as out:
        out.write(head_region)
        out.write(toc_blob)
        out.write(b'\0' * (content - (toc_off + len(toc_blob))))
        # old content area verbatim
        f.seek(content)
        left = end_of_data - content
        while left:
            b = f.read(min(left, 1 << 24))
            if not b:
                raise C.CpkError('short read of content area')
            out.write(b)
            left -= len(b)
        for n in new:
            if out.tell() != n['abs']:
                raise C.CpkError('internal: data offset mismatch')
            out.write(n['data'])
            out.write(b'\0' * (roundup(out.tell(), align) - out.tell()))
        assert out.tell() == new_etoc_off
        out.write(etoc_blob)
        # anything the base had after its ETOC (nothing in practice)
        f.seek(etoc_off + 16 + etoc_size)
        tail = f.read()
        out.write(tail)
    base.close()
    log('wrote %s (%d bytes); added %s at rows %s with IDs %s' % (
        out_path, os.path.getsize(out_path), [n['name'] for n in new],
        [n['row'] for n in new], [n['id'] for n in new]))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description='Add entries from other CPKs to a copy of a CPK.')
    p.add_argument('base')
    p.add_argument('out')
    p.add_argument('--add', action='append', required=True,
                   help='<source.cpk>:<entry name> (repeatable)')
    a = p.parse_args(argv)
    if os.path.abspath(a.base) == os.path.abspath(a.out):
        p.error('out must differ from base')
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    return merge(a.base, a.out, a.add)


if __name__ == '__main__':
    sys.exit(main())
