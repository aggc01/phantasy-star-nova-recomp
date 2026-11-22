"""aif_encode_test.py <in.aif> <out.aif> [png]  - re-encode an .aif BC2 texture from RGBA (Pillow's DDS DXT3 encoder),
put the blocks back in Vita Morton order, keep the 0x1e0 header bytes (size, format, texture ID) unchanged, and
compare the decode with the source. With [png], encode that picture (same size) instead of the original pixels.
Research prototype 2026-11-19 (ui-textures-research.md); not a production tool.
"""
import io, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aiftex  # noqa: E402


def encode_bc2_morton(rgba):
    H, W = rgba.shape[:2]
    buf = io.BytesIO()
    Image.fromarray(rgba, 'RGBA').save(buf, 'DDS', pixel_format='DXT3')
    dds = buf.getvalue()
    lin = np.frombuffer(dds[128:128 + W * H], np.uint8).reshape(H // 4, W // 4, 16).copy()   # row-major blocks
    # Pillow 12.2's DXT3 alpha half came out shifted in ~2 % of pixels (seen on tex_nova_ui_common): write the
    # explicit 4-bit alpha ourselves (pixel i of the 4x4 block -> nibble i, low nibble first) and keep only its colour half.
    a = (rgba[..., 3].astype(np.int32) + 8) // 17
    a = a.reshape(H // 4, 4, W // 4, 4).transpose(0, 2, 1, 3).reshape(H // 4, W // 4, 16)
    lin[..., :8] = (a[..., 0::2] | (a[..., 1::2] << 4)).astype(np.uint8)
    perm = aiftex._perm(W // 4, H // 4)            # perm[by,bx] = index of that block in the file
    out = np.empty((H // 4 * W // 4, 16), np.uint8)
    out[perm.reshape(-1)] = lin.reshape(-1, 16)
    return out.tobytes()


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    d = open(src, 'rb').read()
    W, H, fmt, tid = aiftex.info(d)
    assert fmt == 0x12, 'BC2 only'
    orig = aiftex.decode(d[0x1e0:], W, H, fmt)
    pic = np.array(Image.open(sys.argv[3]).convert('RGBA')) if len(sys.argv) > 3 else orig
    data = encode_bc2_morton(pic)
    new = d[:0x1e0] + data + d[0x1e0 + len(data):]
    assert len(new) == len(d)
    open(dst, 'wb').write(new)
    back = aiftex.decode(new[0x1e0:], W, H, fmt)
    diff = np.abs(back.astype(int) - pic.astype(int))
    print('size', len(d), 'texid %06x' % tid, 'max diff per channel', diff.reshape(-1, 4).max(0),
          'mean', diff.reshape(-1, 4).mean(0).round(2))
    if pic is orig:
        same = sum(a == b for a, b in zip(np.frombuffer(d[0x1e0:], np.uint8).reshape(-1, 16).tolist()[:0], []))
        blocks_equal = (np.frombuffer(d[0x1e0:0x1e0 + len(data)], np.uint8).reshape(-1, 16) ==
                        np.frombuffer(data, np.uint8).reshape(-1, 16)).all(1).mean()
        print('blocks byte-identical to the original: %.1f %%' % (100 * blocks_equal))
