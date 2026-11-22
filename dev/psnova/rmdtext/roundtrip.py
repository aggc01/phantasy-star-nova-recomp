"""roundtrip.py - proof of rmdwrite.py: rebuild every message file from its decoded parts (text bytes, own glyph pictures,
their records and positions, region size, box, texture chunks) and compare with the original: the header part must be
byte-identical and the atlas must decode to the same alpha. Also saves one texture-chunk template per atlas size
(gxm_templates/). Written 2026-11-18.   python roundtrip.py <text dir>
"""
import collections, glob, os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rmdlib import Rmd, decode_dxt3_alpha
import rmdwrite


def text_end(r):
    """offset of the 0x00 byte that ends the text, read as the game reads it (rmdlib.Rmd.tokens; 0x8082 is not an end)"""
    b, o, end = r.b, r.ts, r.gs
    while o < end:
        b0 = b[o]
        if b0 == 0:
            return o
        if b0 < 0x80:
            o += 1; continue
        if o + 1 >= end:
            return end
        c = b0 | (b[o + 1] << 8); o += 2
        if c == 0x8090:
            o = b.index(b'\x00', o, end) + 1
        elif c in (0x8081, 0x8099):
            o += 1
        elif c == 0x8094:
            o += 2
    return o


def main():
    textdir = sys.argv[1]
    tdir = os.path.join(rmdwrite.HERE, 'gxm_templates'); os.makedirs(tdir, exist_ok=True)
    res = collections.Counter(); bad = []
    for sub in ('jp_base', 'jp_patch', 'en_patch'):
        for p in sorted(glob.glob(os.path.join(textdir, sub, '**', '*.rmd'), recursive=True)):
            b = open(p, 'rb').read(); r = Rmd(b); f = r.f
            W, H = r.W, r.H
            tp = os.path.join(tdir, '%dx%d.bin' % (W, H))
            if not os.path.exists(tp):
                open(tp, 'wb').write(b[r.hs:r.hs + 0x1e0])
            te = text_end(r)
            tb = b[r.ts:te]
            lc = r.local_count()
            glyphs, pos = [], []
            for i in range(lc):
                w, cls, z, u0, v0, u1, v1 = r.recs[i]
                x0, y0, x1, y1 = round(u0 * W), round(v0 * H), round(u1 * W), round(v1 * H)
                glyphs.append((r.atlas[y0:y1, x0:x1].copy(), w, cls)); pos.append((x0, y0))
            try:
                out = rmdwrite.build_rmd(r.id, tb, glyphs, region=f[2] - 0x100, box=r.box, gxm=b[r.hs:r.hs + 0x1e0],
                                         size=(W, H), positions=pos)
            except Exception as e:
                res['error ' + type(e).__name__] += 1; bad.append((p, str(e))); continue
            body_ok = out[:r.hs] == b[:r.hs]
            chunk_ok = out[r.hs:r.hs + 0x1e0] == b[r.hs:r.hs + 0x1e0]
            a0 = decode_dxt3_alpha(b[r.hs + 0x1e0:r.hs + 0x1e0 + W * H], W, H)
            ohs = struct.unpack_from('<I', out, 4)[0]
            a1 = decode_dxt3_alpha(out[ohs + 0x1e0:], W, H) if len(out) - ohs - 0x1e0 == W * H else None
            alpha_ok = a1 is not None and np.array_equal(a0, a1)
            size_ok = len(out) == r.hs + f[6]
            k = (sub, body_ok, chunk_ok, alpha_ok, size_ok)
            res[k] += 1
            if not (body_ok and alpha_ok and size_ok) and len(bad) < 20:
                d = [i for i in range(min(len(out), r.hs)) if out[i] != b[i]][:8]
                bad.append((p, 'header bytes differ at %s' % [hex(x) for x in d], 'alpha', alpha_ok))
    for k, v in sorted(res.items(), key=str):
        print(k, v)
    for x in bad[:20]:
        print(x)


if __name__ == '__main__':
    main()
