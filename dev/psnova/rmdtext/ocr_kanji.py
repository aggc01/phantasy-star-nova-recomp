"""ocr_kanji.py - suggest characters for the per-file glyph pictures (kanji) that learn_map.py could not label, by matching
each 21x21 picture against kanji rendered with an installed Japanese font. Written 2026-11-18.

  python ocr_kanji.py <text dir> <map dir>          (writes <map dir>/ocr_*.json and a calibration line)

Method: every picture and every rendered candidate is cut to its ink box and scaled to 24x24, then compared by normalised
correlation. Calibration: the same matching is run on a sample of the pictures learn_map.py DID label (their answer is known)
and the font/size with the best top-1 rate is used. Candidates: the JIS X 0208 kanji (cp932) plus every character of the
game's dictionary. The output keeps the top 5 per picture with scores; a reader (person or model) confirms them with the
sentence context (ocr_review.json).
"""
import collections, glob, json, os, pickle, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rmdlib import Rmd, read_mdic, LOCAL_BASE
from learn_map import ghash

N = 24
FONTS = [r'C:\Windows\Fonts\YuGothB.ttc', r'C:\Windows\Fonts\YuGothM.ttc', r'C:\Windows\Fonts\msgothic.ttc']


def norm(img):
    a = img.astype(np.float32)
    ys, xs = np.where(a > 60)
    if len(ys) == 0:
        return None
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = a.shape
    s = max(h, w)
    sq = np.zeros((s, s), np.float32)
    sq[(s - h) // 2:(s - h) // 2 + h, (s - w) // 2:(s - w) // 2 + w] = a
    v = cv2.resize(sq, (N, N), interpolation=cv2.INTER_AREA)
    v = cv2.GaussianBlur(v, (3, 3), 0.8).ravel()
    v -= v.mean()
    n = np.linalg.norm(v)
    return v / n if n else None


def render(chars, font, size):
    f = ImageFont.truetype(font, size)
    out = []
    for ch in chars:
        im = Image.new('L', (size * 2, size * 2), 0)
        ImageDraw.Draw(im).text((size // 2, size // 2), ch, fill=255, font=f)
        out.append(norm(np.array(im)))
    return out


def jis_kanji():
    s = set()
    for lead in list(range(0x88, 0xa0)) + list(range(0xe0, 0xeb)):
        for tr in list(range(0x40, 0x7f)) + list(range(0x80, 0xfd)):
            try:
                ch = bytes([lead, tr]).decode('cp932')
            except UnicodeDecodeError:
                continue
            if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf':
                s.add(ch)
    return s


def main():
    textdir, mapdir = sys.argv[1], sys.argv[2]
    G = pickle.load(open(os.path.join(mapdir, 'map_glyph.pkl'), 'rb'))
    D, _ = read_mdic(os.path.join(textdir, 'jp_patch', 'novamessagedictionary.mdic'))
    pics, count = {}, collections.Counter()
    files = {}
    for sub in ('jp_base', 'jp_patch'):
        for p in glob.glob(os.path.join(textdir, sub, '**', '*.rmd'), recursive=True):
            files[os.path.basename(p)] = p
    for sub in ('en_patch',):
        for p in glob.glob(os.path.join(textdir, sub, '**', '*.rmd'), recursive=True):
            files['en:' + os.path.basename(p)] = p
    for n, p in files.items():
        r = Rmd(open(p, 'rb').read()); lc = r.local_count()
        for t in r.tokens():
            if t[0] == 'c' and t[1] >= LOCAL_BASE and t[1] - LOCAL_BASE < lc:
                g = r.glyph(t[1] - LOCAL_BASE); h = ghash(g)
                pics.setdefault(h, g.copy()); count[h] += 1
    cands = set(jis_kanji())
    for s in D.values():
        cands.update(ch for ch in s if ord(ch) > 0x2fff)
    cands = sorted(cands)
    labeled = [h for h in pics if h in G]
    unl = [h for h in pics if h not in G]
    print('pictures %d, labeled %d, unlabeled %d, candidates %d' % (len(pics), len(labeled), len(unl), len(cands)), flush=True)
    rng = np.random.default_rng(1)
    sample = [labeled[i] for i in rng.choice(len(labeled), min(400, len(labeled)), replace=False)]
    best = None
    for font in FONTS:
        for size in (20, 21, 24, 32):
            R = render(cands, font, size)
            ok = [i for i, v in enumerate(R) if v is not None]
            M = np.stack([R[i] for i in ok])
            hit = 0
            for h in sample:
                v = norm(pics[h])
                if v is None:
                    continue
                j = ok[int(np.argmax(M @ v))]
                hit += cands[j] == G[h][0]
            rate = hit / len(sample)
            print('calibration %s size %d: top-1 %.3f' % (os.path.basename(font), size, rate), flush=True)
            if best is None or rate > best[0]:
                best = (rate, font, size, M, ok)
    rate, font, size, M, ok = best
    print('using %s size %d (top-1 %.3f on labeled pictures)' % (os.path.basename(font), size, rate), flush=True)
    res = {}
    for h in unl:
        v = norm(pics[h])
        if v is None:
            res[h] = {'count': count[h], 'top': []}; continue
        sc = M @ v
        top = np.argsort(-sc)[:5]
        res[h] = {'count': count[h], 'top': [[cands[ok[i]], round(float(sc[i]), 3)] for i in top]}
    json.dump({'font': os.path.basename(font), 'size': size, 'calibration_top1': rate, 'pictures': res},
              open(os.path.join(mapdir, 'ocr_unlabeled.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    np.savez_compressed(os.path.join(mapdir, 'pictures.npz'), **{h: pics[h] for h in pics})


if __name__ == '__main__':
    main()
