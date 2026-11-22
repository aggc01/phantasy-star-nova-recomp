"""Check translated tutorial pages (or any multi-line batch) before they go into the sheet (2026-11-19).
usage: python check_tut.py <batch.json> <result.json>   -> prints problems, exit 0 when none
result.json = {id: {"en": text, "ar": text}} with real newlines (or \\n) between lines.
Checks per language: every control tag of the Japanese kept the same number of times ({ruby} tags excluded), no
Japanese characters left, at most as many lines as the Japanese, each line within the width (English: 470 px of the
game's 10-px Latin font = 46 letters + room for a button icon; Arabic: 440 px measured as the encoder draws it), and that
the text encodes to an .rmd (glyph pictures fit one atlas)."""
import json, os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from measure import Measure

TAG = re.compile(r'\{(?!ruby:|/ruby)[^}]*\}')
JPC = re.compile(r'[぀-ヿ一-鿿]')
LIMIT = {'en': 470, 'ar': 440}


def main():
    b = json.load(open(sys.argv[1], encoding='utf-8'))
    res = json.load(open(sys.argv[2], encoding='utf-8'))
    m = Measure()
    probs = []
    for it in b['items']:
        r = res.get(it['id'])
        if not r:
            probs.append((it['id'], '-', 'missing')); continue
        want = collections.Counter(t.replace('{end}', '{/color}') for t in TAG.findall(it['jp']))
        for lang in (('en', 'ar') if it.get('need_ar', True) else ('en',)):   # need_ar false: the Arabic column already has it
            t = (r.get(lang) or '').replace('\\n', '\n')
            if not t.strip():
                probs.append((it['id'], lang, 'empty')); continue
            got = collections.Counter(x.replace('{end}', '{/color}') for x in TAG.findall(t))
            # button icons {8099:xx} and value slots {8094:xxxx} must all be there; colour ({8081:xx} ... {/color}) may
            # mark other words, but every colour start needs its {/color}
            fixed = lambda c: collections.Counter({k: v for k, v in c.items() if not (k.startswith('{8081') or k == '{/color}')})
            if fixed(got) != fixed(want):
                probs.append((it['id'], lang, 'icon/value tags differ: missing %s extra %s' % (dict(fixed(want) - fixed(got)), dict(fixed(got) - fixed(want)))))
            starts = sum(v for k, v in got.items() if k.startswith('{8081')); ends = got.get('{/color}', 0)
            if starts > ends:
                probs.append((it['id'], lang, 'a colour start {8081:..} without its {/color}'))
            if JPC.search(TAG.sub('', t)):
                probs.append((it['id'], lang, 'Japanese characters left'))
            lines = t.split('\n')
            if len(lines) > it['jp_lines'] + 1:   # one line more than the Japanese at most (the box grows; the game shrinks text that is too big)
                probs.append((it['id'], lang, '%d lines, the Japanese has %d' % (len(lines), it['jp_lines'])))
            for k, ln in enumerate(lines):
                px = m.line_px(ln, lang)
                if px > LIMIT[lang]:
                    probs.append((it['id'], lang, 'line %d is %d px (limit %d): %s' % (k + 1, px, LIMIT[lang], ln[:50])))
            try:
                m.enc.encode(int(it['id']), t, lang, rtl=False)
            except Exception as e:
                probs.append((it['id'], lang, 'does not encode: %s' % e))
    for p in probs:
        print('%s [%s] %s' % p)
    print('items %d, problems %d' % (len(b['items']), len(probs)))
    sys.exit(1 if probs else 0)


if __name__ == '__main__':
    main()
