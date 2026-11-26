"""rmdwrite.py - write Phantasy Star Nova message files (.rmd). Written 2026-11-18; format in docs/psnova/text-format.md.

build_rmd(msg_id, text_bytes, glyphs, ...) -> bytes
  text_bytes : the encoded text (u16 codes, furigana groups, control codes), WITHOUT the 0x0000 terminator
  glyphs     : this file's own glyph pictures, in code order (0x391 + i): list of (alpha uint8 HxW, adv byte, class byte)
               H must be <= 21 rows (the line height); W = the picture's width (the advance byte is its own field)
               with atlas_scale=2 a fourth element can supply the matching alpha bitmap at twice the dimensions
  region     : text region size in bytes (default: the text + terminator rounded up to 0x40)
  box        : the two floats at 0x9c / 0xa0 (0xa0 = text height in px: 21 + 20 per extra line for plain text; lines
               with furigana add 9-10 px; texts with 0x8081/0x8099 parts differ; whether the game reads it is not known)
  gxm        : the 0x1e0-byte texture chunk list to use (default: the template for the atlas size, IDs made from content)

Layout rules (all checked on the 46,591 game and fan files, 2026-11-18):
  header size hs = smallest value >= the end of the glyph table with hs % 0x80 == 0x10
  f[0]=0x80 f[1]=0x100 f[2]=0x100+region f[3]=f[4]=hs-0x10 f[5]=373+own glyphs f[6]=f[14]=0x1e0+W*H f[7]=f[6]+0x20
  f[8..10]=21,25,25 f[12]=f[13]=1 f[15]=0x13269dd f[16],f[17]=logical atlas W,H f[18]=1
  glyph records: own glyphs first (u8 width, u8 class, u16 0, float u0 v0 u1 v1), then zero records up to f[5]
  atlas: DXT3, Morton block order; font in the 4-bit alpha; colour half written as plain white (the original tool left
  arbitrary colours where alpha is 0; only alpha is drawn)
  own glyphs are packed left to right in rows 25 px apart (the original tool used 25-px slots; any packing works because
  the records hold the coordinates)
"""
import hashlib, struct
import numpy as np
from rmdlib import morton, _perm

PRODUCER = b'FontConverterDll_1.0.1.3_rc6\0\0\0\0'
SIZES = [(128, 32), (128, 64), (128, 128), (256, 64), (256, 128)]   # the sizes the game's own files use
# larger atlases (2026-11-19): the UI textures (.aif, up to 1024x1024) use the same texture header, and only the size
# fields differ (template_gxm derives them), so long English/Arabic messages can use fewer, wider glyph pictures and stay
# under the game's 128-glyphs-per-message limit
SIZES = SIZES + [(256, 256), (512, 256), (512, 512)]
_templates = {}


def roundup(x, a):
    return (x + a - 1) // a * a


def encode_dxt3(alpha):
    """alpha uint8 HxW -> DXT3 bytes, Morton block order, colour white"""
    H, W = alpha.shape
    bw, bh = W // 4, H // 4
    a4 = (alpha.astype(np.uint16) + 8) // 17                  # 0..255 -> 0..15 (exact for multiples of 17)
    a4 = np.clip(a4, 0, 15).astype(np.uint8)
    blk = a4.reshape(bh, 4, bw, 4).transpose(0, 2, 1, 3).reshape(bh * bw, 16)
    abytes = (blk[:, 0::2] | (blk[:, 1::2] << 4)).astype(np.uint8)            # 8 bytes per block
    col = np.frombuffer(b'\xff\xff\xff\xff\x00\x00\x00\x00', np.uint8)
    out = np.empty((bh * bw, 16), np.uint8)
    out[:, :8] = abytes
    out[:, 8:] = col
    perm = _perm(bw, bh).reshape(-1)                         # block (by,bx) -> stored position
    stored = np.empty_like(out)
    stored[perm] = out
    return stored.tobytes()


def pack(glyphs, size=None):
    """place pictures in rows 25 px apart; returns (W, H, positions). Pictures of 21 px or less take the game's 25-px
    slots when all are that narrow; otherwise every picture takes its width + 2 px. Sizes are tried smallest first, up to
    256x128 (the largest the game's own files use; a 256x256 atlas has no checked template, review 2026-11-18)."""
    narrow = all(g[0].shape[1] <= 21 for g in glyphs)
    for W, H in ([size] if size else SIZES):
        if any(g[0].shape[1] > W for g in glyphs):
            continue
        for slots in ([True, False] if narrow else [False]):     # the game's 25-px slots first, then tight packing
            x = y = 0; pos = []
            ok = True
            for g in glyphs:
                w = g[0].shape[1]
                if x and x + w > W:
                    x = 0; y += 25
                if y + 21 > H:
                    ok = False; break
                pos.append((x, y)); x += 25 if slots else w + 2
            if ok:
                return W, H, pos
    raise ValueError('glyph pictures do not fit in a 512x512 atlas (%d pictures, %d px in all)' % (
        len(glyphs), sum(g[0].shape[1] for g in glyphs)))


def game_size(n):
    """the atlas size the game's own tool picks for n own glyphs (21x21 each)"""
    return (128, 32) if n <= 5 else (128, 64) if n <= 10 else (128, 128) if n <= 16 else (256, 64) if n <= 20 else (256, 128)


def template_gxm(W, H):
    """the texture chunk list for a W x H DXT3 atlas: the game's own template where one exists, else the 256x128 one with
    its size fields set (width/height u16 at 0xa8/0xaa, blocks across/down u16 at 0xb2/0xb4, row pitch W*4 at 0xb8, data
    size W*H at 0xbc, 0x150, 0x1a0 and W*H+0xf0 at 0xf4 -- checked against the game's 1024x512 and 1024x1024 UI textures,
    which differ from the 256x128 template in nothing else but the per-file IDs)"""
    if (W, H) not in _templates:
        t = bytearray(template_gxm(256, 128))
        struct.pack_into('<HH', t, 0xa8, W, H)
        struct.pack_into('<HH', t, 0xb2, W // 4, H // 4)
        struct.pack_into('<I', t, 0xb8, W * 4)
        struct.pack_into('<I', t, 0xbc, W * H)
        struct.pack_into('<I', t, 0xf4, W * H + 0xf0)
        struct.pack_into('<I', t, 0x150, W * H)
        struct.pack_into('<I', t, 0x1a0, W * H)
        _templates[(W, H)] = bytes(t)
    return _templates[(W, H)]


PER_FILE = [(0x4c, 0x50), (0x90, 0x98), (0xc0, 0xd0), (0x120, 0x130), (0x190, 0x1a0)]


def gxm_for(W, H, content, src=None, msg_id=0):
    """the texture chunk list for a new file: size fields from the template of that atlas size; the per-file fields
    (0x91-0x93 = a 24-bit texture ID, unique in every game file, which the game uses to cache the texture; 16-byte IDs at
    0xc0/0x190 and 0x120; the value at 0x4c) from the message's original file when given (found 2026-11-18: with the
    template's ID copied into every file, files of the same atlas size showed each other's pictures in the game).
    Without an original: an ID from 0x800000 up (game IDs end at 0x525ff) and IDs made from the content."""
    t = bytearray(template_gxm(W, H))
    if src is not None:
        for a, b in PER_FILE:
            t[a:b] = src[a:b]
        return bytes(t)
    import zlib
    tid = 0x800000 | (zlib.crc32(b'%d' % msg_id) & 0x7fffff)
    t[0x91:0x94] = tid.to_bytes(3, 'little')
    gid = hashlib.md5(content).digest()
    t[0xc0:0xd0] = gid; t[0x190:0x1a0] = gid
    t[0x120:0x130] = hashlib.md5(gid + content).digest()
    return bytes(t)


# Scale the stored texture while keeping the glyphs' logical sizes and UVs.
def build_rmd(msg_id, text_bytes, glyphs, region=None, box=(0.0, 21.0), gxm=None, size=None, positions=None,
              gxm_src=None, atlas_scale=1):
    if atlas_scale not in (1, 2):
        raise ValueError('atlas scale must be 1 or 2')
    n = len(glyphs)
    if n > 0xffff - 0x391:
        raise ValueError('too many glyphs')
    if size is None and positions is None:
        size = game_size(n) if all(g[0].shape[1] <= 21 for g in glyphs) and n <= 50 else None
    if positions is None:
        W, H, positions = pack(glyphs, size)
    else:
        W, H = size
    used = len(text_bytes) + 2
    if region is None:
        region = max(0x40, roundup(used, 0x40))
    if region < len(text_bytes):          # a text that fills its region exactly has no terminator (seen in game files)
        raise ValueError('text region too small')
    f2 = 0x100 + region
    count = 373 + n
    tab_end = 0x10 + f2 + 20 * count
    hs = tab_end + ((0x10 - tab_end) % 0x80)
    atlas = np.zeros((H * atlas_scale, W * atlas_scale), np.uint8)
    recs = []
    for glyph, (x, y) in zip(glyphs, positions):
        pic, adv, cls = glyph[:3]
        h, w = pic.shape
        if atlas_scale == 2:
            # A game-supplied picture has only its original bitmap.
            pic = glyph[3] if len(glyph) == 4 else pic.repeat(2, axis=0).repeat(2, axis=1)
        atlas[y * atlas_scale:(y + h) * atlas_scale, x * atlas_scale:(x + w) * atlas_scale] = pic
        recs.append(struct.pack('<BBH4f', adv, cls, 0, x / W, y / H, (x + w) / W, (y + h) / H))
    # The RMD dimensions affect guest glyph placement.
    # The GXM chunk carries the larger dimensions of the physical texture.
    texture_height, texture_width = atlas.shape
    texture_chunk_size = 0x1e0 + atlas.size
    f = [0x80, 0x100, f2, hs - 0x10, hs - 0x10, count, texture_chunk_size, texture_chunk_size + 0x20,
         21, 25, 25, 0, 1, 1, texture_chunk_size, 0x13269dd, W, H, 1, 0, 0, 0, 0, 0]
    b = bytearray(hs)
    b[0:16] = struct.pack('<4sIII', b' DMR', hs, 0, hs)
    b[0x10:0x30] = PRODUCER
    struct.pack_into('<24I', b, 0x30, *f)
    struct.pack_into('<Q', b, 0x90, msg_id)
    struct.pack_into('<2f', b, 0x9c, *box)
    b[0x110:0x110 + len(text_bytes)] = text_bytes
    tab = 0x10 + f2
    for i, r in enumerate(recs):
        b[tab + 20 * i:tab + 20 * i + 20] = r
    data = encode_dxt3(atlas)
    if gxm is None:
        gxm = gxm_for(texture_width, texture_height, bytes(b) + data, gxm_src, msg_id)
    return bytes(b) + gxm + data


def tokens_to_bytes(tokens):
    """tokens as in build_sheet's _tokens.json (['c', code] / ['g', i] own glyph index / ['nl'] / ['ruby', hex] / ['rend'] /
    ['ctl', code, hex]) -> text bytes without the terminator"""
    out = bytearray()
    for t in tokens:
        k = t[0]
        if k == 'c':
            out += struct.pack('<H', t[1])
        elif k == 'g':
            out += struct.pack('<H', 0x391 + t[1])
        elif k == 'nl':
            out += b'\x80\x80'
        elif k == 'ruby':
            out += b'\x90\x80' + bytes.fromhex(t[1]) + b'\0'
        elif k == 'rend':
            out += b'\x91\x80'
        elif k == 'ctl':
            out += struct.pack('<H', t[1]) + bytes.fromhex(t[2])
        else:
            raise ValueError(t)
    return bytes(out)
