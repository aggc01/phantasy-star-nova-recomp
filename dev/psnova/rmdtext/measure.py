"""On-screen width of a sheet line as the game will draw it (2026-11-19).
  from measure import Measure; m = Measure(); m.line_px(text, lang)   # lang 'ja' | 'en' | 'ar'
Japanese and Latin characters: the advance (width byte) of the game's glyph record -- BasicCharSet.rmd for the fixed
table, 21 px for a per-file kanji picture; Arabic: the phrase pictures our encoder draws (Segoe UI Bold 16, words joined
by the font's own space). Tags: {8099:xx} (a button icon) counts 24 px, other control codes 0.
CLI: python measure.py <sheet.tsv> <id> ...  -> per line: px per language."""
import os, re, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rmdlib import Rmd
from encode_text import Encoder, is_arabic
from arabic import to_display

ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TEXT = os.path.join(ROOT, 'dump', 'psnova-l10n', 'text')
TAG = re.compile(r'\{[^}]*\}')
ICON_PX = 24


class Measure:
    def __init__(self):
        self.enc = Encoder(TEXT, os.path.join(TEXT, 'map'))
        p = glob.glob(os.path.join(ROOT, 'dump', 'psnova-l10n', '**', 'BasicCharSet.rmd'), recursive=True)[0]
        r = Rmd(open(p, 'rb').read())
        self.basic = [rec[0] for rec in r.recs]          # record i = game code i + 1

    def char_px(self, c):
        code = self.enc.code_of.get(c)
        if code is not None:
            true = (code & 0x7f) | ((code >> 8) << 7) if (code & 0xff) >= 0x80 else code
            i = true - 1
            if 0 <= i < len(self.basic) and self.basic[i]:
                return self.basic[i]
        if c in self.enc.pic_of:
            return self.enc.pic_of[c][1]
        return 21 if ord(c) > 0x2000 else 10

    def line_px(self, line, lang):
        icons = len(re.findall(r'\{8099:[0-9a-f]{2}\}', line))
        s = TAG.sub('', line)
        if lang != 'ar':
            return sum(self.char_px(c) for c in s) + icons * ICON_PX
        disp = to_display(s)
        px, i = 0, 0
        while i < len(disp):
            if is_arabic(disp[i]):
                j = i
                while j < len(disp) and (is_arabic(disp[j]) or (disp[j] == ' ' and j + 1 < len(disp) and is_arabic(disp[j + 1]))):
                    j += 1
                px += self.enc.font.getlength(disp[i:j]) + 1; i = j
            else:
                px += self.char_px(disp[i]); i += 1
        return int(round(px)) + icons * ICON_PX


if __name__ == '__main__':
    import csv
    rows = {r['id']: r for r in csv.DictReader(open(sys.argv[1], encoding='utf-8-sig'), delimiter='\t')}
    m = Measure()
    for i in sys.argv[2:]:
        r = rows[i]
        for col, lang in (('Japanese (original)', 'ja'), ('English (fan rePatch, to revise)', 'en'), ('Arabic', 'ar')):
            for ln in r[col].split('\\n'):
                if ln.strip():
                    print(i, lang, m.line_px(ln, lang), ln[:60])
