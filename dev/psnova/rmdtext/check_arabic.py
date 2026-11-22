"""Check translated Arabic labels before they go into the sheet (2026-11-19).
usage: python check_arabic.py <out dir with batches/ and results/> [--encode]

Reads batches/b_NN.json (source items) and results/b_NN.json ({k: arabic}) and checks each item:
  missing   no result for the item
  tags      the multiset of control tags differs from the Japanese ({ruby} tags excluded)
  japanese  kana / kanji left in the Arabic
  noarabic  no Arabic letter (allowed when the English is only Latin codes like "HP" - listed as info)
  letters   a character the shaping or the game font cannot show
  wide      wider on screen than the Japanese original (Segoe UI Bold 16 for Arabic, 21 px per full-width JP char,
            11 px per half-width) - and wider than the fan English too (both measured)
  glossary  a glossary term of the English whose Arabic is not in the line (soft; names only)
  encode    (with --encode) the line does not encode to an .rmd
Writes <out>/check_report.json and prints counts. Exit code 0 always (the report is the result)."""
import sys, os, json, re, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import ImageFont
from arabic import to_display, FORMS

out = sys.argv[1]; do_encode = '--encode' in sys.argv
TAG = re.compile(r'\{[^}]*\}')
JP = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff\uff66-\uff9f]')
AR = re.compile(r'[\u0600-\u06ff]')
font = ImageFont.truetype(r'C:\Windows\Fonts\segoeuib.ttf', 16)
OK_EXTRA = set(' 0123456789.,:;!?%+-/()[]«»"\'#*=~&<>' 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
               '،؛؟ـ' '×★☆♪※→←↑↓○△□・…「」『』【】～－＝＊！？％＋（）：　' '\u0640')
AR_OK = set(FORMS) | set('ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىي') | set('\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652') | set('٠١٢٣٤٥٦٧٨٩')

def jp_width(s):
    s = TAG.sub('', s)
    return sum(21 if ord(c) > 0x2000 else 11 for c in s)

def ar_width(s):
    s = TAG.sub('0000', s)
    return font.getlength(to_display(s))

enc = None
if do_encode:
    from encode_text import Encoder
    ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
    TEXT = os.path.join(ROOT, 'dump', 'psnova-l10n', 'text')
    enc = Encoder(TEXT, os.path.join(TEXT, 'map'))

report = collections.defaultdict(list)
n = 0
for bp in sorted(glob.glob(os.path.join(out, 'batches', 'b_*.json'))):
    b = json.load(open(bp, encoding='utf-8'))
    rp = os.path.join(out, 'results', os.path.basename(bp))
    res = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else {}
    names = [g for g in b['glossary'] if AR.search(g['ar'])]
    for it in b['items']:
        n += 1
        k = str(it['k']); ar = res.get(k)
        rec = dict(k=it['k'], id=it['ids'][0], jp=it['jp'], en=it['en'], ar=ar)
        if not ar or not ar.strip():
            report['missing'].append(rec); continue
        if collections.Counter(TAG.findall(ar)) != collections.Counter(it['tags']):
            report['tags'].append(rec)
        if JP.search(TAG.sub('', ar)):
            report['japanese'].append(rec)
        if not AR.search(ar):
            report['noarabic'].append(rec)
        bad = sorted({c for c in TAG.sub('', ar) if c not in AR_OK and c not in OK_EXTRA})
        if bad:
            rec2 = dict(rec, chars=''.join(bad)); report['letters'].append(rec2)
        aw, jw = ar_width(ar), jp_width(it['jp'])
        ew = font.getlength(TAG.sub('0000', it['en'])) if it['en'] else 0
        if aw > max(jw, ew) + 2:
            report['wide'].append(dict(rec, ar_px=round(aw), jp_px=jw, en_px=round(ew)))
        miss = [g['en'] for g in names if re.search(r'(?<![A-Za-z])' + re.escape(g['en']) + r'(?![A-Za-z])', it['en'])
                and g['ar'] not in ar]
        if miss:
            report['glossary'].append(dict(rec, terms=miss))
        if enc is not None:
            try:
                enc.encode(int(it['ids'][0]), ar, 'ar')
            except Exception as e:
                report['encode'].append(dict(rec, error=str(e)))
json.dump(report, open(os.path.join(out, 'check_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('items', n, {k: len(v) for k, v in report.items()})
