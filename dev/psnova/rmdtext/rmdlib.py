"""rmdlib.py - read Phantasy Star Nova message files (.rmd, FontConverterDll_1.0.1.3_rc6) and the message dictionary
(.mdic). Written 2026-11-18 (localization session); format notes in docs/psnova/text-format.md.

.rmd layout (little-endian):
  0x00 " DMR", 0x04 u32 header size (= offset of the texture chunk list), 0x10 producer string
  0x30.. u32 fields f[0..23]: f[1] + 0x10 = text start, f[2] + 0x10 = glyph table start, f[5] = glyph record count,
         f[16], f[17] = atlas width, height; 0x90 u64 message id (the number in the file name)
  text: u16 codes from f[1]+0x10 up to the glyph table, zero padded at the end
  glyph table: f[5] records of 20 bytes: u8 width, u8 advance-ish, u16 0, float u0, v0, u1, v1 (texture coordinates)
  after the header: 0x1e0 bytes of GXM texture chunks, then the atlas: DXT3 (BC2), blocks in Morton (Z) order,
  font pixels in the 4-bit alpha (the colour half is constant white)
Codes: >= 0x8000 control (0x8080 = new line); 0x81 .. 0x81+372 = BasicCharSet glyph (code - 0x81);
       >= 0x391 = this file's own glyph (code - 0x391), drawn in its own atlas.
"""
import struct
import numpy as np

BASIC_BASE = 0x81
LOCAL_BASE = 0x391

# furigana: a reading byte b is glyph b-1 of BasicRubySet.rmd (180 glyphs, read from its atlas 2026-11-18; checked on
# 惑星=ほし 1e 0c, 艦=ふね 1c 18, 艦外=せんがい 0e 2e 2f 02, 相棒=バディ 97 90 9d)
RUBY = ('あいうえおかきくけこさしすせそたちつてと'
        'なにぬねのはひふへほまみむめもやゆよらり'
        'るれろわをんがぎぐげござじずぜぞだぢづで'
        'どばびぶべぼぱぴぷぺぽぁぃぅぇぉゃゅょっ'
        'ゎ・ーヴアイウエオカキクケコサシスセソタ'
        'チツテトナニヌネノハヒフヘホマミムメモヤ'
        'ユヨラリルレロワヲンガギグゲゴザジズゼゾ'
        'ダヂヅデドパピプペポバビブベボァィゥェォ'
        'ャュョッヮヵヶ●1234567890-N')
assert len(RUBY) == 180


def ruby_text(bs):
    return ''.join(RUBY[b - 1] if 1 <= b <= 180 else '〔r%02x〕' % b for b in bs)


def morton(x, y, n):
    i = 0
    for b in range(n):
        i |= ((y >> b) & 1) << (2 * b) | ((x >> b) & 1) << (2 * b + 1)
    return i


_perm_cache = {}


def _perm(bw, bh):
    key = (bw, bh)
    if key not in _perm_cache:
        m = min(bw, bh); nb = m.bit_length() - 1
        p = np.empty((bh, bw), np.int64)
        for by in range(bh):
            for bx in range(bw):
                p[by, bx] = morton(bx % m, by % m, nb) + ((bx // m) if bw > bh else (by // m)) * m * m
        _perm_cache[key] = p
    return _perm_cache[key]


def decode_dxt3_alpha(data, W, H):
    """DXT3 alpha only, blocks Morton-ordered; returns uint8 HxW (0..255)"""
    bw, bh = W // 4, H // 4
    blocks = np.frombuffer(data, np.uint8)[:bw * bh * 16].reshape(-1, 16)[:, :8]
    lo, hi = blocks & 15, blocks >> 4
    px = np.empty((blocks.shape[0], 16), np.uint8); px[:, 0::2] = lo; px[:, 1::2] = hi
    px = (px * 17).reshape(-1, 4, 4)
    perm = _perm(bw, bh)
    out = px[perm.reshape(-1)].reshape(bh, bw, 4, 4).transpose(0, 2, 1, 3).reshape(H, W)
    return out


class Rmd:
    def __init__(self, data):
        b = self.b = data
        if b[:4] != b' DMR':
            raise ValueError('not an rmd')
        self.hs = struct.unpack_from('<I', b, 4)[0]
        f = self.f = struct.unpack_from('<24I', b, 0x30)
        self.id = struct.unpack_from('<Q', b, 0x90)[0]
        self.box = struct.unpack_from('<2f', b, 0x9c)
        ts, gs = 0x10 + f[1], 0x10 + f[2]
        self.ts, self.gs = ts, gs
        codes = list(struct.unpack_from('<%dH' % ((gs - ts) // 2), b, ts))
        while codes and codes[-1] == 0:
            codes.pop()
        self.codes = codes          # naive u16 reading (wrong after an odd-length furigana group; use tokens())
        self.n = f[5]
        self.recs = [struct.unpack_from('<BBH4f', b, gs + 20 * i) for i in range(self.n)]
        self.W, self.H = f[16], f[17]
        # In a 2x atlas the RMD keeps the original layout
        # dimensions. The GXM chunk describes the physical pixels.
        self.atlas_width, self.atlas_height = self.W, self.H
        if self.hs + 0x1e0 <= len(b):
            width, height = struct.unpack_from('<HH', b, self.hs + 0xa8)
            if ((width, height) == (2 * self.W, 2 * self.H)
                    and f[6] == f[14] == 0x1e0 + width * height
                    and self.hs + f[6] <= len(b)):
                self.atlas_width, self.atlas_height = width, height
        self._atlas = None

    @property
    def atlas(self):
        if self._atlas is None:
            start = self.hs + 0x1e0
            width, height = self.atlas_width, self.atlas_height
            self._atlas = decode_dxt3_alpha(self.b[start:start + width * height], width, height)
        return self._atlas

    def glyph(self, i):
        w, a, z, u0, v0, u1, v1 = self.recs[i]
        width, height = self.atlas_width, self.atlas_height
        x0, y0 = int(round(u0 * width)), int(round(v0 * height))
        x1, y1 = int(round(u1 * width)), int(round(v1 * height))
        return self.atlas[y0:y1, x0:x1]

    def tokens(self):
        """byte-level parse of the text, as the game reads it (decoder fn_817e65fc and four more; found 2026-11-19,
        docs/psnova/right-alignment-research.md): a byte b < 0x80 is a one-byte code (0 = end of the text); b >= 0x80
        starts a two-byte code (b & 0x7f) | (next byte << 7); bit 0x4000 = a control code (u16 0x80XX).
        Returned codes keep the u16 form the maps use (low byte | high byte << 8; a one-byte code b as 0x80 | b), and
        this file's own glyph i (game code 401 + i) as LOCAL_BASE + i, whatever its bytes.
        Tokens: ('c', code) | ('nl',) | ('ruby', reading bytes) | ('rend',) | ('ctl', code, param bytes).
          0x8080 new line; 0x8090 <reading bytes up to a 0x00> <base> 0x8091 furigana;
          0x8081 <1 byte> text colour (03 red, 06 cyan, 07 yellow); 0x8099 <1 byte>; 0x8094 <2 bytes> value slot;
          0x8082 colour back to the default (NOT an end: the text goes on; until 2026-11-19 it was read as the end and
          179 game messages lost their text after it)."""
        b, o, end = self.b, self.ts, self.gs
        out = []
        while o < end:
            b0 = b[o]
            if b0 == 0:
                break
            if b0 < 0x80:                            # one-byte code (furigana readings use these; rare in text)
                out.append(('c', 0x80 | b0)); o += 1; continue
            if o + 1 >= end:
                break
            hi = b[o + 1]; o += 2
            c = b0 | (hi << 8)
            if hi & 0x80:                            # control code
                if c == 0x8080:
                    out.append(('nl',))
                elif c == 0x8090:
                    j = b.index(b'\0', o, end)
                    out.append(('ruby', bytes(b[o:j]))); o = j + 1
                elif c == 0x8091:
                    out.append(('rend',))
                elif c in (0x8081, 0x8099):
                    out.append(('ctl', c, bytes(b[o:o + 1]))); o += 1
                elif c == 0x8094:
                    out.append(('ctl', c, bytes(b[o:o + 2]))); o += 2
                else:
                    out.append(('ctl', c, b''))
                continue
            code = (b0 & 0x7f) | (hi << 7)
            out.append(('c', c if code <= 400 else LOCAL_BASE + code - 401))
        return out

    def local_count(self):
        k = 0
        while k < self.n and self.recs[k][0]:
            k += 1
        return k


def read_mdic(path):
    """{64-bit id: text} from novamessagedictionary.mdic (" BMVN"? magic 'BMVN', u32 count, then entries
    u16 length, UTF-16LE text, u32 id low, u32 id high)"""
    b = open(path, 'rb').read()
    o, out, order = 0x10, {}, []
    while o + 2 <= len(b):
        L = struct.unpack_from('<H', b, o)[0]; o += 2
        s = b[o:o + 2 * L].decode('utf-16-le'); o += 2 * L
        if o + 8 > len(b):
            break
        lo, hi = struct.unpack_from('<II', b, o); o += 8
        k = (hi << 32) | lo
        order.append((k, s))
        out.setdefault(k, s)
    return out, order
