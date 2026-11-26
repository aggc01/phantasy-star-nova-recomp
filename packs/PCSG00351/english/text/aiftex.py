"""aiftex.py - render PS Nova .aif textures (GXM header 0x1e0, BC1/BC2/BC3 blocks in Vita Morton order) to PNG.

usage: aiftex.py <out_dir> <file.aif>...   (writes <name>.png, RGBA; prints name W H format texid size)
Header (same chunk set as the .rmd atlases): data at 0x1e0, format byte at 0xa0 (0x10 BC1, 0x12 BC2/DXT3,
0x14 BC3/DXT5), width u16 at 0xa8, height u16 at 0xaa, 24-bit texture id at 0x91..0x93.
Research scratch 2026-11-19 (ui-textures-research.md).
"""
import sys, os, struct
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
from rmdlib import _perm  # noqa: E402

FMT = {0x10: ('BC1', 8), 0x12: ('BC2', 16), 0x14: ('BC3', 16)}


def info(d):
    W, H = struct.unpack_from('<HH', d, 0xa8)
    return W, H, d[0xa0], int.from_bytes(d[0x91:0x94], 'little')


def rgb565(c):
    return np.stack([((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31], -1).astype(np.int32)


def bc3_alpha(a):
    a0 = a[:, 0].astype(np.int32); a1 = a[:, 1].astype(np.int32)
    bits = np.zeros(a.shape[0], np.uint64)
    for i in range(6):
        bits |= a[:, 2 + i].astype(np.uint64) << np.uint64(8 * i)
    sel = np.stack([((bits >> np.uint64(3 * i)) & np.uint64(7)).astype(np.int64) for i in range(16)], 1)
    pal = np.empty((a.shape[0], 8), np.int32)
    pal[:, 0] = a0; pal[:, 1] = a1
    big = a0 > a1
    for k in range(1, 7):
        pal[:, 1 + k] = ((7 - k) * a0 + k * a1) // 7
    for k in range(1, 5):
        pal[:, 1 + k] = np.where(big, pal[:, 1 + k], ((5 - k) * a0 + k * a1) // 5)
    pal[:, 6] = np.where(big, pal[:, 6], 0); pal[:, 7] = np.where(big, pal[:, 7], 255)
    return np.take_along_axis(pal, sel, 1).astype(np.uint8)


def decode(data, W, H, fmt=0x12):
    name, bs = FMT[fmt]
    bw, bh = max(W // 4, 1), max(H // 4, 1)
    blk = np.frombuffer(data, np.uint8)[:bw * bh * bs].reshape(-1, bs)
    n = blk.shape[0]
    alpha = None
    if name == 'BC2':
        a = blk[:, :8]
        alpha = np.empty((n, 16), np.uint8); alpha[:, 0::2] = a & 15; alpha[:, 1::2] = a >> 4
        alpha = alpha * 17
    elif name == 'BC3':
        alpha = bc3_alpha(blk[:, :8])
    if bs == 16:
        blk = blk[:, 8:]
    c0 = blk[:, 0].astype(np.int32) | (blk[:, 1].astype(np.int32) << 8)
    c1 = blk[:, 2].astype(np.int32) | (blk[:, 3].astype(np.int32) << 8)
    p0, p1 = rgb565(c0), rgb565(c1)
    four = (c0 > c1)[:, None] if name == 'BC1' else np.ones((n, 1), bool)
    p2 = np.where(four, (2 * p0 + p1) // 3, (p0 + p1) // 2)
    p3 = np.where(four, (p0 + 2 * p1) // 3, 0)
    pal = np.stack([p0, p1, p2, p3], 1)
    idx = blk[:, 4:8].astype(np.uint32)
    bits = idx[:, 0] | (idx[:, 1] << 8) | (idx[:, 2] << 16) | (idx[:, 3] << 24)
    sel = np.stack([(bits >> (2 * i)) & 3 for i in range(16)], 1).astype(np.int64)
    if alpha is None:
        alpha = np.where((sel == 3) & ~four, 0, 255).astype(np.uint8)
    rgb = np.take_along_axis(pal, sel[:, :, None].repeat(3, 2), 1)
    px = np.concatenate([rgb.astype(np.uint8), alpha[:, :, None]], 2).reshape(n, 4, 4, 4)
    perm = _perm(bw, bh)
    return px[perm.reshape(-1)].reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(H, W, 4)


def load(path):
    d = open(path, 'rb').read()
    W, H, fmt, tid = info(d)
    return decode(d[0x1e0:], W, H, fmt), (W, H, FMT[fmt][0], tid, len(d))


if __name__ == '__main__':
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    for p in sys.argv[2:]:
        try:
            img, (W, H, f, tid, n) = load(p)
        except Exception as e:
            print(os.path.basename(p), 'ERROR', e); continue
        Image.fromarray(img, 'RGBA').save(os.path.join(out, os.path.basename(p)[:-4] + '.png'))
        print(os.path.basename(p), W, H, f, '%06x' % tid, n)
