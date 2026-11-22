"""make_review.py - review sheets for the kanji pictures nobody has read yet: per picture the game's picture (x4), the
5 best font matches (x4, numbered), and up to 3 sentences where it appears (Japanese with ◆ at its place, plus the fan
English of the same message). Written 2026-11-18.

  python make_review.py <text dir> <map dir> <out dir> [per batch 25]
  -> <out dir>/batch_NN.png and batch_NN.json  ({"items": [{"n", "hash", "count", "candidates", "contexts"}]})
"""
import glob, json, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rmdlib import Rmd, LOCAL_BASE
from learn_map import ghash
from build_sheet import load_maps, decode, collect

FONT = r'C:\Windows\Fonts\YuGothB.ttc'


def main():
    textdir, mapdir, out = sys.argv[1:4]
    per = int(sys.argv[4]) if len(sys.argv) > 4 else 25
    os.makedirs(out, exist_ok=True)
    B, G = load_maps(mapdir)
    pics = np.load(os.path.join(mapdir, 'pictures.npz'))
    current = {}
    if len(sys.argv) > 5:          # second pass: <todo json> with new_unlabeled + suspicious_labels; candidates computed here
        import collections
        from ocr_kanji import norm, render, jis_kanji, FONTS
        from rmdlib import read_mdic
        todo = json.load(open(sys.argv[5]))
        sus = set(todo['suspicious_labels'])
        D, _ = read_mdic(os.path.join(textdir, 'jp_patch', 'novamessagedictionary.mdic'))
        cands = set(jis_kanji())
        for s in D.values():
            cands.update(ch for ch in s if ord(ch) > 0x2fff)
        cands = sorted(cands)
        R = render(cands, FONTS[0], 32); ok = [i for i, v in enumerate(R) if v is not None]; Mx = np.stack([R[i] for i in ok])
        cnt = collections.Counter()
        ocr = {}
        for h in todo['new_unlabeled'] + todo['suspicious_labels']:
            v = norm(pics[h])
            top = [] if v is None else [[cands[ok[i]], 0] for i in np.argsort(-(Mx @ v))[:5]]
            if h in sus:
                current[h] = G[h]
                top = [[G[h], 0]] + [t for t in top if t[0] != G[h]][:4]
            ocr[h] = {'count': 0, 'top': top}
        for h in sus:
            G.pop(h, None)                 # show it as unread in the sentences
    else:
        ocr = json.load(open(os.path.join(mapdir, 'ocr_unlabeled.json'), encoding='utf-8'))['pictures']
    want = set(h for h in ocr if h not in G)
    ctx = {h: [] for h in want}
    jp = collect(textdir, ('jp_base', 'jp_patch')); en = collect(textdir, ('en_patch',))
    for n, (p, _) in sorted(jp.items()) + [('en:' + k, v) for k, v in sorted(en.items())]:
        r = Rmd(open(p, 'rb').read()); lc = r.local_count()
        hs = set()
        for t in r.tokens():
            if t[0] == 'c' and t[1] >= LOCAL_BASE and t[1] - LOCAL_BASE < lc:
                h = ghash(r.glyph(t[1] - LOCAL_BASE))
                if h in want and len(ctx[h]) < 3:
                    hs.add(h)
        if not hs:
            continue
        txt, _ = decode(r, B, G)
        eng = ''
        base = n[3:] if n.startswith('en:') else n
        if not n.startswith('en:') and base in en:
            eng, _ = decode(Rmd(open(en[base][0], 'rb').read()), B, G)
        for h in hs:
            if len(ctx[h]) < 3:
                ctx[h].append({'id': base[4:-4], 'japanese': txt.replace('〔#%s〕' % h[:6], '◆'), 'english_fan': eng,
                               'file': 'fan patch' if n.startswith('en:') else 'japanese'})
    order = sorted(want, key=lambda h: -ocr[h]['count'])
    font = ImageFont.truetype(FONT, 64)
    small = ImageFont.truetype(FONT, 18)
    for bi in range(0, len(order), per):
        items = order[bi:bi + per]
        rows = []
        js = []
        for k, h in enumerate(items):
            cand = [c for c, s in ocr[h]['top']]
            im = Image.new('L', (100 + 6 * 96, 96), 0)
            d = ImageDraw.Draw(im)
            d.text((4, 30), '%d' % (k + 1), fill=200, font=small)
            g = cv2.resize(pics[h], (84, 84), interpolation=cv2.INTER_NEAREST)
            im.paste(Image.fromarray(g), (40, 6))
            for ci, ch in enumerate(cand):
                x = 140 + ci * 96
                d.text((x, 10), ch, fill=255, font=font)
                d.text((x + 70, 70), str(ci + 1), fill=150, font=small)
            rows.append(np.array(im))
            e = {'n': k + 1, 'hash': h, 'count': ocr[h]['count'], 'candidates': cand, 'contexts': ctx[h]}
            if h in current:
                e['current_label'] = current[h] + ' (learned from the dictionary; candidate 1; check it)'
            js.append(e)
        sheet = np.vstack(rows)
        name = 'batch_%02d' % (bi // per + 1)
        cv2.imwrite(os.path.join(out, name + '.png'), sheet)
        json.dump({'items': js}, open(os.path.join(out, name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('%d pictures in %d batches' % (len(order), (len(order) + per - 1) // per))


if __name__ == '__main__':
    main()
