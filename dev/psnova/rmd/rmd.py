#!/usr/bin/env python3
"""Reader for Phantasy Star Nova .rmd message files (FontConverter output).

Usage (standard library only):
  rmd.py info   <file.rmd>            header fields and glyph table summary
  rmd.py atlas  <file.rmd> <out.png>  the glyph atlas as an 8-bit greyscale PNG
  rmd.py render <file.rmd> <out.png>  NOT IMPLEMENTED: glyph table and pixel layout still unknown (see RMD-FORMAT.md)

The atlas command writes the 8 bpp linear reading (row-major, 256 px rows, starting at
data_off + 0x1e0). That reading is NOT verified: the images do not show readable letters.

Field meanings are marked CONFIRMED / GUESSED in RMD-FORMAT.md.
"""
import os
import struct
import sys
import zlib


def u32(d, off):
    return struct.unpack_from('<I', d, off)[0]


def u16(d, off):
    return struct.unpack_from('<H', d, off)[0]


def png_gray8(width, height, pixels):
    """Write an 8-bit greyscale PNG. pixels: bytes, row-major, width*height."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: none
        raw += pixels[y * width:(y + 1) * width]

    def chunk(tag, body):
        c = struct.pack('>I', len(body)) + tag + body
        return c + struct.pack('>I', zlib.crc32(tag + body) & 0xffffffff)

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
            + chunk(b'IEND', b''))


class Rmd:
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.d = f.read()
        d = self.d
        if d[0:4] != b' DMR':
            raise ValueError('not an RMD file (magic %r)' % d[0:4])
        self.ident = d[0x10:0x2c].split(b'\0')[0].decode('ascii', 'replace')
        self.data_off = u32(d, 0x0c)       # start of the data block (CONFIRMED: data block ends at EOF)
        self.data_size = u32(d, 0x68)      # = data block size (CONFIRMED: data_off + data_size == len)
        self.msg_id = struct.unpack_from('<Q', d, 0x90)[0]  # 64-bit = number in the file name (CONFIRMED)
        self.atlas_w = u32(d, 0x70)        # atlas width (CONFIRMED by size check)
        self.atlas_h = u32(d, 0x74)        # atlas height (CONFIRMED by size check)
        self.count = u32(d, 0x44)          # glyph/record count (GUESSED)
        self.box = struct.unpack_from('<2f', d, 0x9c)  # two floats (GUESSED: text box size)
        self.head_len = 0x1e0              # bytes of data block before the atlas (GUESSED, see proof)

    def check(self):
        d = self.d
        problems = []
        if self.data_off + self.data_size != len(d):
            problems.append('data_off+data_size != file size')
        if self.data_size - self.head_len != self.atlas_w * self.atlas_h:
            problems.append('data_size-0x1e0 != atlas_w*atlas_h')
        return problems

    def atlas_bytes(self, where='head'):
        """Return the atlas pixels (8 bpp). where='head' puts the atlas right after
        the 0x1e0-byte block header; where='tail' takes it from the end of the block."""
        n = self.atlas_w * self.atlas_h
        base = self.data_off
        if where == 'head':
            start = base + self.head_len
        else:
            start = base + self.data_size - n
        return self.d[start:start + n]


def cmd_info(r):
    d = r.d
    print('file        %s' % r.path)
    print('size        %d' % len(d))
    print('ident       %r' % r.ident)
    print('msg_id      %d (0x%x)' % (r.msg_id, r.msg_id))
    print('data_off    0x%x (%d)  [CONFIRMED: start of data block; 0x04 and 0x0c hold it]' % (r.data_off, r.data_off))
    print('data_size   0x%x (%d)  [CONFIRMED: data_off + data_size = EOF]' % (r.data_size, r.data_size))
    print('atlas       %d x %d, 8 bpp = %d bytes  [CONFIRMED by size check]' % (r.atlas_w, r.atlas_h, r.atlas_w * r.atlas_h))
    print('count 0x44  %d  [GUESSED]' % r.count)
    print('box floats  %.1f, %.1f  [GUESSED]' % r.box)
    for off in (0x30, 0x34, 0x38, 0x3c, 0x40, 0x48, 0x4c, 0x50, 0x54, 0x58, 0x60, 0x64, 0x6c, 0x78):
        print('  0x%02x = 0x%x (%d)' % (off, u32(d, off), u32(d, off)))
    problems = r.check()
    print('checks      %s' % ('ok' if not problems else '; '.join(problems)))


def cmd_atlas(r, out, where='head'):
    pix = r.atlas_bytes(where)
    with open(out, 'wb') as f:
        f.write(png_gray8(r.atlas_w, r.atlas_h, pix))
    print('wrote %s (%dx%d, from %s of data block)' % (out, r.atlas_w, r.atlas_h, where))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, path = argv[1], argv[2]
    r = Rmd(path)
    if cmd == 'info':
        cmd_info(r)
    elif cmd == 'atlas':
        where = 'head'
        if len(argv) > 4 and argv[4] in ('head', 'tail'):
            where = argv[4]
        cmd_atlas(r, argv[3], where)
    else:
        print('unknown command %r' % cmd)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
