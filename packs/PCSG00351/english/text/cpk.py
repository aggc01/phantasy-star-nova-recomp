#!/usr/bin/env python3
"""cpk.py - read and extract CRI CPK archives (standard library only).

Commands:
  cpk.py list <cpk> [--tsv out.tsv]
      Writes the entry table as TSV (to --tsv, else stdout) and a summary to stderr.
      Columns: path, id, offset, size, extract_size, compressed
      offset is the absolute offset of the stored bytes inside the .cpk file.
  cpk.py extract <cpk> <outdir> [--match <glob>] [--max-bytes N]
      Writes entries under <outdir>/<archive path>. CRILAYLA-compressed entries are
      decompressed. --match is an fnmatch glob on the archive path (case-insensitive,
      '/' separators). --max-bytes skips entries whose extract size is larger than N.

Format notes (from the project spec, checked against the real archives):
  * CPK header: magic 'CPK ' at 0. An @UTF table at 0x10 with one row:
    TocOffset, ContentOffset, EtocOffset, ItocOffset, GtocOffset, Files, Align.
  * @UTF table at T: u32 table_size at T+4 (bytes after that field), u16 version T+8,
    u16 rows_offset T+0xA, u32 strings_offset T+0xC, u32 data_offset T+0x10,
    u32 name_offset T+0x14, u16 columns T+0x18, u16 row_width T+0x1A, u32 rows T+0x1C.
    rows/strings/data offsets are relative to T+8. Column definitions start at T+0x20.
  * Column definition: u8 flags (high nibble: 0x10 none, 0x30/0x70 constant value stored
    inline after the name, 0x50 per-row value in each row; low nibble: 0 u8, 1 s8, 2 u16,
    3 s16, 4 u32, 5 s32, 6 u64, 7 s64, 8 f32, 9 f64, 0xA string (u32 offset into strings),
    0xB data (u32 offset + u32 size into the data area)), then u32 name offset (strings).
  * If the bytes at 0x10 are not '@UTF' the table is XOR-scrambled: m=0x5f, t=0x15,
    for each byte b ^= m; m = (m*t) & 0xff. The same applies to every @UTF table here.
  * TOC at TocOffset: magic 'TOC ', @UTF at +0x10. Rows: DirName, FileName, FileSize,
    ExtractSize, FileOffset, ID. Absolute offset = FileOffset + base, where
    base = min(TocOffset, ContentOffset) ignoring a zero value.
  * No TOC but an ITOC: magic 'ITOC' at ItocOffset, @UTF at +0x10, with data columns
    DataL / DataH that each hold an embedded @UTF table (ID, FileSize, ExtractSize).
    Files are laid out from ContentOffset in increasing ID order, each start rounded up
    to Align. These entries have no names, so they are listed as _noname/id_NNNNNNNN.
  * FileSize < ExtractSize means the stored bytes are CRILAYLA-compressed: 'CRILAYLA',
    u32le uncompressed_size at +8, u32le header_offset at +12. The first 0x100 output
    bytes are copied raw from data[header_offset+0x10 : header_offset+0x110]; the rest is
    a bit-stream decoded MSB-first, reading input backwards from the end (CriPakTools).
"""

import argparse
import fnmatch
import os
import struct
import sys

TYPE_FMT = {0: '>B', 1: '>b', 2: '>H', 3: '>h', 4: '>I', 5: '>i',
            6: '>Q', 7: '>q', 8: '>f', 9: '>d'}
TYPE_SIZE = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 8, 7: 8, 8: 4, 9: 8,
             0x0A: 4, 0x0B: 8}
STORE_ROW = 0x50
STORE_CONST = (0x30, 0x70)


class CpkError(Exception):
    pass


def unscramble(buf):
    """Undo the XOR scrambling used for @UTF tables (m=0x5f, t=0x15)."""
    out = bytearray(buf)
    m = 0x5F
    for i in range(len(out)):
        out[i] ^= m
        m = (m * 0x15) & 0xFF
    return bytes(out)


def cstr(buf, off):
    end = buf.index(b'\0', off)
    return buf[off:end].decode('utf-8', 'replace')


def _value(blob, pos, ctype, strbase, database):
    if ctype in TYPE_FMT:
        return struct.unpack_from(TYPE_FMT[ctype], blob, pos)[0]
    if ctype == 0x0A:
        off, = struct.unpack_from('>I', blob, pos)
        return cstr(blob, strbase + off)
    off, size = struct.unpack_from('>II', blob, pos)
    return blob[database + off: database + off + size]


def parse_utf(blob):
    """Parse one @UTF table whose bytes start at the '@UTF' magic.

    Returns a list of row dicts. Data-type (0xB) values come back as the referenced
    bytes, so embedded tables can be parsed again by the caller."""
    if blob[:4] != b'@UTF':
        raise CpkError('no @UTF magic')
    (_tsize, _version, rows_off, strings_off, data_off, _name_off,
     ncols, row_width, nrows) = struct.unpack_from('>IHHIIIHHI', blob, 4)
    strbase = 8 + strings_off
    database = 8 + data_off
    rowbase = 8 + rows_off
    pos = 0x20
    cols = []
    for _ in range(ncols):
        flags = blob[pos]
        pos += 1
        storage = flags & 0xF0
        ctype = flags & 0x0F
        if ctype not in TYPE_SIZE:
            raise CpkError('bad column type 0x%x' % ctype)
        name_off, = struct.unpack_from('>I', blob, pos)
        pos += 4
        name = cstr(blob, strbase + name_off)
        const = None
        if storage in STORE_CONST:
            const = _value(blob, pos, ctype, strbase, database)
            pos += TYPE_SIZE[ctype]
        cols.append((name, storage, ctype, const))
    rows = []
    for r in range(nrows):
        start = rowbase + r * row_width
        q = start
        row = {}
        for name, storage, ctype, const in cols:
            if storage == STORE_ROW:
                row[name] = _value(blob, q, ctype, strbase, database)
                q += TYPE_SIZE[ctype]
            elif storage in STORE_CONST:
                row[name] = const
            else:
                row[name] = None
        if q - start != row_width:
            raise CpkError('row %d: read %d bytes, row_width is %d'
                           % (r, q - start, row_width))
        rows.append(row)
    return rows


def read_table(f, at):
    """Return the raw @UTF table bytes that start at file offset `at`, unscrambled."""
    f.seek(at)
    raw = f.read(8)
    if len(raw) < 8:
        raise CpkError('short read at 0x%x' % at)
    scrambled = raw[:4] != b'@UTF'
    head = unscramble(raw) if scrambled else raw
    if head[:4] != b'@UTF':
        raise CpkError('no @UTF table at 0x%x' % at)
    tsize, = struct.unpack_from('>I', head, 4)
    raw = raw + f.read(tsize)
    if len(raw) != 8 + tsize:
        raise CpkError('truncated @UTF table at 0x%x' % at)
    return unscramble(raw) if scrambled else raw


def _roundup(x, a):
    return (x + a - 1) // a * a


def crilayla_decompress(data):
    """Decompress one CRILAYLA stream (CriPakTools algorithm). Returns the output bytes."""
    if data[:8] != b'CRILAYLA':
        raise CpkError('not CRILAYLA')
    uncomp, = struct.unpack_from('<I', data, 8)
    hdr_off, = struct.unpack_from('<I', data, 12)
    if hdr_off + 0x110 > len(data):
        raise CpkError('CRILAYLA header offset out of range')
    result = bytearray(uncomp + 0x100)
    result[0:0x100] = data[hdr_off + 0x10: hdr_off + 0x110]

    class Bits:
        def __init__(self):
            self.off = len(data) - 0x100 - 1
            self.pool = 0
            self.n = 0

        def get(self, count):
            res = 0
            while count > 0:
                if self.n == 0:
                    if self.off < 0:
                        raise CpkError('CRILAYLA input exhausted')
                    self.pool = data[self.off]
                    self.off -= 1
                    self.n = 8
                take = min(count, self.n)
                self.n -= take
                bits = (self.pool >> self.n) & ((1 << take) - 1)
                res = (res << take) | bits
                count -= take
            return res

    bits = Bits()
    out_end = 0x100 + uncomp - 1
    done = 0
    while done < uncomp:
        if bits.get(1):
            distance = bits.get(13) + 3
            length = 3
            for lens in (2, 3, 5, 8):
                v = bits.get(lens)
                length += v
                if v != (1 << lens) - 1:
                    break
            else:
                while True:
                    v = bits.get(8)
                    length += v
                    if v != 255:
                        break
            # Copy a whole backward reference at once. If
            # it overlaps the output, the already-decoded suffix repeats.
            right = out_end - done + 1
            length = min(length, uncomp - done)
            if right + distance > len(result):
                raise CpkError('CRILAYLA back-reference out of range')
            if length <= distance:
                result[right - length:right] = result[right + distance - length:right + distance]
            else:
                seed = result[right:right + distance]
                repeats, tail = divmod(length, distance)
                result[right - length:right] = seed[distance - tail:] + seed * repeats
            done += length
        else:
            result[out_end - done] = bits.get(8)
            done += 1
    return bytes(result)


class Cpk:
    def __init__(self, path):
        self.path = path
        self.file_size = os.path.getsize(path)
        self.f = open(path, 'rb')
        if self.read_at(0, 4) != b'CPK ':
            raise CpkError('no CPK magic')
        hdr = parse_utf(read_table(self.f, 0x10))
        if len(hdr) != 1:
            raise CpkError('CPK header table has %d rows' % len(hdr))
        self.header = hdr[0]
        self.entries = []
        self.index_kind = None
        self.n_compressed_flagged = 0
        self._load()

    def close(self):
        self.f.close()

    def read_at(self, off, n):
        self.f.seek(off)
        return self.f.read(n)

    def _load(self):
        h = self.header
        toc = int(h.get('TocOffset') or 0)
        content = int(h.get('ContentOffset') or 0)
        itoc = int(h.get('ItocOffset') or 0)
        bases = [x for x in (toc, content) if x]
        base = min(bases) if bases else 0
        self.toc_offset = toc
        self.content_offset = content
        self.itoc_offset = itoc
        self.etoc_offset = int(h.get('EtocOffset') or 0)
        self.gtoc_offset = int(h.get('GtocOffset') or 0)
        if toc:
            if self.read_at(toc, 4) != b'TOC ':
                raise CpkError('TocOffset has no TOC magic')
            rows = parse_utf(read_table(self.f, toc + 0x10))
            self.index_kind = 'TOC'
            for r in rows:
                fn = r.get('FileName')
                dn = r.get('DirName')
                rid = r.get('ID')
                if fn is None:
                    name = dn or ''
                else:
                    name = ('%s/%s' % (dn, fn)) if dn else fn
                if not name:
                    name = '_noname/id_%s' % rid
                name = name.replace('\\', '/').lstrip('/')
                fsize = int(r['FileSize'])
                esize = r.get('ExtractSize')
                esize = fsize if esize is None else int(esize)
                self.entries.append({
                    'path': name,
                    'id': None if rid is None else int(rid),
                    'offset': base + int(r['FileOffset']),
                    'size': fsize,
                    'extract_size': esize,
                    'source': 'TOC'})
        elif itoc:
            if self.read_at(itoc, 4) != b'ITOC':
                raise CpkError('ItocOffset has no ITOC magic')
            rows = parse_utf(read_table(self.f, itoc + 0x10))
            self.index_kind = 'ITOC'
            sizes = {}
            for r in rows:
                for col in ('DataL', 'DataH'):
                    v = r.get(col)
                    if isinstance(v, bytes) and v:
                        sub = v if v[:4] == b'@UTF' else unscramble(v)
                        for sr in parse_utf(sub):
                            sid = int(sr['ID'])
                            fs = int(sr['FileSize'])
                            es = sr.get('ExtractSize')
                            sizes[sid] = (fs, fs if es is None else int(es))
            if not sizes:
                raise CpkError('ITOC has no DataL/DataH sizes; columns=%s'
                               % sorted(rows[0].keys() if rows else []))
            align = int(h.get('Align') or 0x800)
            cur = content
            for sid in sorted(sizes):
                fs, es = sizes[sid]
                self.entries.append({
                    'path': '_noname/id_%08d' % sid,
                    'id': sid,
                    'offset': cur,
                    'size': fs,
                    'extract_size': es,
                    'source': 'ITOC'})
                cur = _roundup(cur + fs, align)
        else:
            raise CpkError('archive has neither TOC nor ITOC')
        self.n_compressed_flagged = sum(1 for e in self.entries
                                        if e['size'] < e['extract_size'])


def read_entry(cpk, e):
    """Return the logical (decompressed) bytes of one entry."""
    data = cpk.read_at(e['offset'], e['size'])
    if len(data) != e['size']:
        raise CpkError('short read for %s' % e['path'])
    if e['size'] < e['extract_size']:
        if data[:8] != b'CRILAYLA':
            raise CpkError('size < extract_size but no CRILAYLA magic: %s' % e['path'])
        return crilayla_decompress(data)
    return data


def cmd_list(args):
    cpk = Cpk(args.cpk)
    out = open(args.tsv, 'w', encoding='utf-8', newline='\n') if args.tsv else sys.stdout
    out.write('path\tid\toffset\tsize\textract_size\tcompressed\n')
    for e in cpk.entries:
        comp = 'yes' if e['size'] < e['extract_size'] else 'no'
        out.write('%s\t%s\t%d\t%d\t%d\t%s\n' % (
            e['path'], '' if e['id'] is None else e['id'], e['offset'],
            e['size'], e['extract_size'], comp))
    if args.tsv:
        out.close()
    total = sum(e['size'] for e in cpk.entries)
    sys.stderr.write('%s: index=%s entries=%d header.Files=%s stored_bytes=%d '
                     'file_size=%d compressed=%d\n' % (
                         cpk.path, cpk.index_kind, len(cpk.entries),
                         cpk.header.get('Files'), total, cpk.file_size,
                         cpk.n_compressed_flagged))
    sys.stderr.write('offsets: TocOffset=%d ContentOffset=%d ItocOffset=%d '
                     'EtocOffset=%d GtocOffset=%d Align=%s\n' % (
                         cpk.toc_offset, cpk.content_offset, cpk.itoc_offset,
                         cpk.etoc_offset, cpk.gtoc_offset, cpk.header.get('Align')))
    cpk.close()
    return 0


def cmd_extract(args):
    cpk = Cpk(args.cpk)
    pat = args.match.lower() if args.match else None
    written = skipped = warned = 0
    for e in cpk.entries:
        if pat and not fnmatch.fnmatchcase(e['path'].lower(), pat):
            continue
        if args.max_bytes is not None and e['extract_size'] > args.max_bytes:
            skipped += 1
            continue
        parts = e['path'].split('/')
        if any(p in ('', '.', '..') for p in parts) or ':' in e['path']:
            sys.stderr.write('unsafe path skipped: %r\n' % e['path'])
            skipped += 1
            continue
        data = read_entry(cpk, e)
        if len(data) != e['extract_size']:
            warned += 1
            sys.stderr.write('length mismatch %s: got %d, ExtractSize %d\n'
                             % (e['path'], len(data), e['extract_size']))
        dest = os.path.join(args.outdir, *parts)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as fo:
            fo.write(data)
        written += 1
    cpk.close()
    sys.stderr.write('extracted %d, skipped %d, length warnings %d\n'
                     % (written, skipped, warned))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description='Read and extract CRI CPK archives.')
    sub = p.add_subparsers(dest='cmd', required=True)
    pl = sub.add_parser('list', help='write the entry table')
    pl.add_argument('cpk')
    pl.add_argument('--tsv', help='write TSV to this file instead of stdout')
    pl.set_defaults(func=cmd_list)
    pe = sub.add_parser('extract', help='extract entries')
    pe.add_argument('cpk')
    pe.add_argument('outdir')
    pe.add_argument('--match', help='fnmatch glob on the archive path')
    pe.add_argument('--max-bytes', type=int, help='skip entries with extract size above N')
    pe.set_defaults(func=cmd_extract)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
