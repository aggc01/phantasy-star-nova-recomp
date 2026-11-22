"""encode_text.py - turn a sheet cell (Japanese, English or Arabic, with the sheet's {tags}) into a message file (.rmd).
Written 2026-11-18, revised the same night after a code review (dump/psnova-l10n/build/encoder_review.json); format in
docs/psnova/text-format.md, sheet conventions in build_sheet.py.

  enc = Encoder(text_dir, map_dir)
  data = enc.encode(msg_id, text, lang='en'|'ja'|'ar', template=<original .rmd bytes or None>, arabic_mode='word'|'form')

How characters become codes:
  - a character of the game's fixed table (ASCII, kana, punctuation, full-width) -> its code (the one the game's own text
    uses most; hand-set codes only for characters the game never uses)
  - a kanji or symbol the game has drawn somewhere -> that exact game picture as one of this file's own glyphs
  - anything else (Arabic, accented letters, new symbols) -> drawn with Segoe UI Bold 16 px into a 21-px-high picture
    (Latin-like characters on the game's Latin baseline, row 18; Arabic on row 16 to leave room for its descenders)
Arabic lines (lang 'ar'): shaped and put in display order (arabic.py), then drawn as pictures:
  'word': each run of Arabic letters is one picture (falls back to 'form' when the pictures do not fit the atlas)
  'form': the run is drawn once and cut at each letter's advance, so neighbours join exactly; identical pieces are shared
  Control codes inside an Arabic line keep their place: they take part in the reordering as neutral placeholders.
Picture records: width byte = picture width (the advance), class byte 10 (as Latin letters) for drawn pictures.
Control-code tags are checked: {8081:xx} and {8099:xx} need 1 parameter byte, {8094:xxxx} 2, any other code none; a '{'
that is not a known tag is an error (a typo would otherwise shift the text or print the tag).
"""
import collections, glob, hashlib, json, os, pickle, re, struct, sys
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rmdlib import Rmd, LOCAL_BASE, RUBY
import rmdwrite
from arabic import to_display
from english_layout import CAPTION_CELL, WIDTH_PX, reflow

# fonts: dev/psnova/fonts.json (2026-11-19): game_arabic draws Arabic; game_english (if set) draws English letters as
# glyph pictures instead of the game's fixed-width letters. Paths relative to the project folder.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
_FJ = json.load(open(os.path.join(_ROOT, 'dev', 'psnova', 'fonts.json'), encoding='utf-8'))
FONT = os.path.join(_ROOT, _FJ['game_arabic']['file'])
SIZE = _FJ['game_arabic'].get('size', 16)
BASE_AR = _FJ['game_arabic'].get('baseline', 16)   # Arabic baseline row (descenders to ~20)
LATIN = _FJ.get('game_english') or None   # {"file", "size", "baseline"} or None (the game's own letters)
BASE_LATIN = 18        # the game's Latin glyphs stand on row ~18
PARAM_LEN = {0x8081: 1, 0x8099: 1, 0x8094: 2}
RTL_MARK = os.environ.get('PSN_RTL_MARK', '1') != '0'   # 0x8095 at the start of every Arabic message (PSN_RTL_MARK=0: without)
TAG = re.compile(r'\{ruby:([^}]*)\}|\{/ruby\}|\{end\}|\{/color\}|\{([0-9a-f]{4})(?::([0-9a-f]*))?\}|\n|.', re.S)
HERE = os.path.dirname(os.path.abspath(__file__))


def is_arabic(ch):
    o = ord(ch)
    return 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF


class Encoder:
    # Done by Codex. Keep the original layout metrics for scaled English atlases.
    def __init__(self, text_dir, map_dir, english_atlas_scale=1):
        if english_atlas_scale not in (1, 2) or (english_atlas_scale == 2 and not LATIN):
            raise ValueError('English atlas scale must be 1, or 2 with an English font configured')
        self.english_atlas_scale = english_atlas_scale
        lib = os.path.join(map_dir, 'glyphlib.pkl')
        inputs = [os.path.join(map_dir, n) for n in ('map_basic.json', 'map_glyph.pkl', 'glyph_confirmed.json')] + \
                 [os.path.join(HERE, 'map_manual.json')]
        if not os.path.exists(lib) or any(os.path.exists(p) and os.path.getmtime(p) > os.path.getmtime(lib) for p in inputs):
            build_library(text_dir, map_dir)
        d = pickle.load(open(lib, 'rb'))
        self.code_of = d['code_of']          # char -> code
        self.pic_of = d['pic_of']            # char -> (picture, width byte, class byte)
        try:
            self.font = ImageFont.truetype(FONT, SIZE, layout_engine=ImageFont.Layout.BASIC)   # we shape ourselves
        except AttributeError:
            self.font = ImageFont.truetype(FONT, SIZE, layout_engine=ImageFont.LAYOUT_BASIC)
        self.ruby_code = {ch: i + 1 for i, ch in enumerate(RUBY)}
        self.latin, self.latin_cache = None, {}
        self.basic = None
        self.charset_path = os.path.join(os.path.dirname(text_dir), 'sample', 'charset_jp', 'BasicCharSet.rmd')
        if LATIN:
            try:
                self.latin = ImageFont.truetype(os.path.join(_ROOT, LATIN['file']), LATIN.get('size', 18), layout_engine=ImageFont.Layout.BASIC)
            except AttributeError:
                self.latin = ImageFont.truetype(os.path.join(_ROOT, LATIN['file']), LATIN.get('size', 18), layout_engine=ImageFont.LAYOUT_BASIC)
            self.latin_base = LATIN.get('baseline', 16)

    # Done by Codex: use the same runs for width measurement and rendering.
    def _latin_runs(self, items):
        fallback = set((LATIN or {}).get('fallback', ''))
        run = []
        for item in items:
            if (self.latin is not None and item[0] == 'ch' and ord(item[1]) < 0x250
                    and item[1] not in fallback and self._latin_available(item[1])):
                run.append(item[1])
                continue
            if run:
                yield ('latin', ''.join(run))
                run.clear()
            yield item
        if run:
            yield ('latin', ''.join(run))

    def _latin_words(self, items):
        """English runs -> one glyph picture per word with the spaces after it (the game draws at most 128 glyphs per
        message: one picture per letter cut long pages off after 128 characters, seen in the game 2026-11-19).
        Characters the font lacks or fonts.json's game_english "fallback" lists keep the game's own letter."""
        return [('pic', 'R:' + x[1], self.latin_run(x[1])) if x[0] == 'latin' else x
                for x in self._latin_runs(items)]

    # Done by Codex: cache font work during line planning.
    @lru_cache(maxsize=1024)
    def _latin_available(self, ch):
        return ch == ' ' or bool(self.latin.getmask(ch).getbbox())

    @lru_cache(maxsize=32768)
    def _latin_geometry(self, s):
        advance = self.latin.getlength(s)
        left, _, right, _ = self.latin.getbbox(s, anchor='ls') if s.strip() else (0, 0, 0, 0)
        origin = max(0, -int(np.floor(left)))
        return origin, max(1, int(np.ceil(max(advance, right))) + origin)

    def latin_run(self, s):
        """a run of English (any width) drawn with the game_english font: (alpha 21 x W, advance, class 10); cut into
        glyph-sized slices by _slices()"""
        f = self.latin
        x0, W = self._latin_geometry(s)
        im = Image.new('L', (W + 2, 21), 0)
        if s.strip():
            ImageDraw.Draw(im).text((x0, self.latin_base), s, fill=255, font=f, anchor='ls')
        glyph = (np.array(im)[:, :W], W, 10)
        if self.english_atlas_scale == 1:
            return glyph
        return (*glyph, self._scaled_latin_run(s, W))

    # Done by Codex. Draw the full run before slicing to preserve kerning
    # and keep letter fragments aligned across cell boundaries.
    @lru_cache(maxsize=32)
    def _scaled_latin_font(self, size):
        return self.latin.font_variant(size=size * self.english_atlas_scale)

    def _scaled_latin_run(self, text, logical_width):
        scale = self.english_atlas_scale
        if not text.strip():
            return np.zeros((21 * scale, logical_width * scale), dtype=np.uint8)
        font = self._scaled_latin_font(self.latin.size)
        left, _, right, _ = font.getbbox(text, anchor='ls')
        origin = max(0, -left)
        width = max(1, int(np.ceil(max(font.getlength(text), right))) + origin)
        image = Image.new('L', (width, 21 * scale))
        ImageDraw.Draw(image).text((origin, self.latin_base * scale), text, fill=255, font=font, anchor='ls')
        return np.asarray(image.resize((logical_width * scale, 21 * scale), Image.Resampling.LANCZOS))

    def english_width(self, items, caption=False):
        """Measure original glyph advances and custom runs in game pixels."""
        total = 0
        for item in self._latin_runs(items):
            kind = item[0]
            if kind == 'latin':
                width = self._latin_geometry(item[1])[1]
                total += rmdwrite.roundup(width, CAPTION_CELL) if caption else width
            elif kind == 'ch':
                total += CAPTION_CELL if caption else self._character_width(item[1])
            elif kind == 'ctl':
                # Inline button icons and value substitutions occupy visible space.
                total += {0x8099: 24, 0x8094: 48}.get(item[1], 0)
        return total

    def _character_width(self, char):
        code = self.code_of.get(char)
        if code is None:
            return self.picture(char)[1]
        if self.basic is None:
            with open(self.charset_path, 'rb') as stream:
                self.basic = [record[0] for record in Rmd(stream.read()).recs]
        index = ((code & 0x7f) | ((code >> 8) << 7)) - 1
        return self.basic[index]

    def _caption_cells(self, items):
        # Keep the run intact across words. Only the last cell of the run
        # receives transparent padding, so there is no extra interword space.
        for item in self._latin_runs(items):
            if item[0] == 'latin':
                glyph = self.latin_run(item[1])
            elif item[0] == 'ch' and item[1] not in self.code_of:
                glyph = self.picture(item[1])
            else:
                yield item
                continue
            image = glyph[0]
            scale = self.english_atlas_scale
            for start in range(0, image.shape[1], CAPTION_CELL):
                piece = image[:, start:start + CAPTION_CELL]
                cell = np.zeros((21, CAPTION_CELL), dtype=np.uint8)
                cell[:piece.shape[0], :piece.shape[1]] = piece
                key = 'caption:' + hashlib.sha1(cell.tobytes()).hexdigest()
                cell_glyph = (cell, CAPTION_CELL, 10)
                if len(glyph) == 4:
                    high_piece = glyph[3][:, start * scale:(start + CAPTION_CELL) * scale]
                    high_cell = np.zeros((21 * scale, CAPTION_CELL * scale), dtype=np.uint8)
                    high_cell[:, :high_piece.shape[1]] = high_piece
                    cell_glyph = (*cell_glyph, high_cell)
                yield ('pic', key, cell_glyph)

    def _slices(self, items, maxw):
        """cut every drawn picture wider than maxw into slices of equal width (at most maxw px),
        each a glyph of its own with advance = width, so they join seamlessly (2026-11-19, docs/psnova/text-render-faults.md):
        the game draws each glyph's 4 shadow copies offset by 5 % of the glyph's width (a 60-px word picture got a shadow
        3 px off to the side), and the cutscene subtitle drawer fits every glyph into its 21-px cell (wide pictures were
        squeezed, narrow ones stretched). Slices of the game's own 21 px behave like its own glyphs in both."""
        out = []
        for x in items:
            if x[0] != 'pic' or x[2][0].shape[1] <= maxw:
                out.append(x); continue
            glyph = x[2]
            a = glyph[0]; W = a.shape[1]
            n = -(-W // maxw)                        # slices of equal width <= maxw (no padding: a padded last slice
            sw = -(-W // n)                          # left a gap before the next character, 2026-11-19)
            for k in range(0, W, sw):
                piece = a[:, k:k + sw]
                key = 's:' + hashlib.sha1(bytes(piece.shape) + piece.tobytes()).hexdigest()[:16]
                sliced = (piece.copy(), piece.shape[1], 10)
                if len(glyph) == 4:
                    scale = self.english_atlas_scale
                    sliced = (*sliced, glyph[3][:, k * scale:(k + sw) * scale].copy())
                out.append(('pic', key, sliced))
        return out

    def latin_word(self, tok):
        """a word (with its trailing spaces) drawn with the game_english font; None when wider than 255 px"""
        key = 'W:' + tok
        if key in self.latin_cache:
            return self.latin_cache[key]
        f = self.latin
        adv = f.getlength(tok)
        l, t, r, b = f.getbbox(tok, anchor='ls') if tok.strip() else (0, 0, 0, 0)
        x0 = max(0, -int(np.floor(l)))
        W = max(1, int(np.ceil(max(adv, r))) + x0)
        if W > 255:
            self.latin_cache[key] = None; return None
        im = Image.new('L', (W + 2, 21), 0)
        if tok.strip():
            ImageDraw.Draw(im).text((x0, self.latin_base), tok, fill=255, font=f, anchor='ls')
        pic = (np.array(im)[:, :W], min(255, max(1, int(round(adv)) + x0)), 10)
        self.latin_cache[key] = pic
        return pic

    def latin_pic(self, c):
        """one English character drawn with fonts.json's game_english font: (alpha 21 x w, width byte = advance, class 10),
        or None when the font has no glyph for it (the game's own letter is used then)"""
        if c in self.latin_cache:
            return self.latin_cache[c]
        f, pic = self.latin, None
        if c == ' ' or f.getmask(c).getbbox():
            adv = f.getlength(c)
            l, t, r, b = f.getbbox(c, anchor='ls') if c != ' ' else (0, 0, 0, 0)
            x0 = max(0, -int(np.floor(l)))
            W = max(1, int(np.ceil(max(adv, r))) + x0)
            im = Image.new('L', (W + 2, 21), 0)
            if c != ' ':
                ImageDraw.Draw(im).text((x0, self.latin_base), c, fill=255, font=f, anchor='ls')
            a = np.array(im)[:, :W]
            pic = (a, min(255, max(1, int(round(adv)) + x0)), 10)
        self.latin_cache[c] = pic
        return pic

    # ---------- drawing ----------
    def draw(self, s, baseline=BASE_AR):
        """draw a string (already in display order) -> (alpha 21xW, cut positions per character). The picture covers the
        whole ink (nothing clipped at either end); cuts follow the font's advances."""
        f = self.font
        adv = [f.getlength(s[:i]) for i in range(len(s) + 1)]
        l, t, r, b = f.getbbox(s, anchor='ls')
        x0 = max(0, -int(np.floor(l)))                         # ink left of the pen start
        W = max(1, int(np.ceil(max(adv[-1], r))) + x0)
        im = Image.new('L', (W + 2, 21), 0)
        ImageDraw.Draw(im).text((x0, baseline), s, fill=255, font=f, anchor='ls')
        a = np.array(im)[:, :W]
        cuts = [int(round(x)) + x0 for x in adv]
        cuts[0] = 0; cuts[-1] = W
        return a, cuts

    def picture(self, ch):
        if ch in self.pic_of:
            return self.pic_of[ch]
        a, _ = self.draw(ch, BASE_AR if is_arabic(ch) else BASE_LATIN)
        return (a, min(255, a.shape[1]), 10)

    # ---------- text ----------
    def parse(self, text, lang):
        """sheet cell -> items: ('ch', c) / ('nl',) / ('ruby', reading) / ('rend',) / ('ctl', code, hexparam) / ('end',)"""
        out = []
        for m in TAG.finditer(text):
            t = m.group(0)
            if m.group(1) is not None:
                out.append(('ruby', m.group(1)))
            elif t == '{/ruby}':
                out.append(('rend',))
            elif t in ('{end}', '{/color}'):   # 0x8082: colour back to white (not an end; {end} is the old name)
                out.append(('end',))
            elif m.group(2):
                code, prm = int(m.group(2), 16), m.group(3) or ''
                if code < 0x8000 or code in (0x8080, 0x8082, 0x8090, 0x8091):
                    raise ValueError('tag {%s} is not a control code to write this way' % m.group(2))
                if len(prm) != 2 * PARAM_LEN.get(code, 0) or (prm and not re.fullmatch('[0-9a-f]+', prm)):
                    raise ValueError('tag {%s:%s}: %d parameter bytes expected' % (m.group(2), prm, PARAM_LEN.get(code, 0)))
                out.append(('ctl', code, prm))
            elif t == '\n':
                out.append(('nl',))
            elif t == '{':
                raise ValueError('a "{" that is not a known tag near: %r' % text[max(0, m.start() - 10):m.start() + 20])
            else:
                out.append(('ch', t))
        if lang != 'ja':                     # furigana belong to Japanese only
            out = [x for x in out if x[0] not in ('ruby', 'rend')]
        return out

    # Done by Codex: uniformly reduce the font only when a message cannot
    # fit at the configured size, then restore it for the next message.
    def encode(self, msg_id, text, lang='en', template=None, arabic_mode='word', rtl=None, context=None):
        # Done by Codex. Measure, reflow and rasterize with the same font instance.
        items = self.parse(text, lang)
        original = self.latin
        try:
            if lang == 'en' and original is not None and context in WIDTH_PX:
                caption = context == 'caption'
                limit = WIDTH_PX[context]
                size = LATIN.get('size', 18)
                while True:
                    wrapped = reflow(items, lambda line: self.english_width(line, caption), context)
                    lines = [[]]
                    for item in wrapped:
                        if item[0] == 'nl':
                            lines.append([])
                        else:
                            lines[-1].append(item)
                    if all(self.english_width(line, caption) <= limit for line in lines):
                        items = wrapped
                        break
                    size -= 1
                    if size < 8:
                        raise ValueError('English message cannot fit without dropping text')
                    self.latin = ImageFont.truetype(os.path.join(_ROOT, LATIN['file']), size,
                                                    layout_engine=ImageFont.Layout.BASIC)
                    self._latin_geometry.cache_clear()
                    self._latin_available.cache_clear()
                if caption:
                    data = self._build(msg_id, self._caption_cells(items), template,
                                       atlas_scale=self.english_atlas_scale)
                    if self.last_drawn > 128:
                        raise ValueError('caption exceeds the 128-glyph limit')
                    return data
            return self._encode_items(msg_id, items, lang, template, arabic_mode, rtl)
        finally:
            if self.latin is not original:
                self.latin = original
                self._latin_geometry.cache_clear()
                self._latin_available.cache_clear()

    def _encode_items(self, msg_id, items, lang, template, arabic_mode, rtl):
        rtl = RTL_MARK if rtl is None else rtl   # False: no 0x8095 mark, the box keeps its own alignment (labels beside an icon)
        if lang == 'ar':
            # RTL_MARK first: the no-op control code 0x8095 tells the alignment hook "Arabic, align right"
            # (docs/psnova/right-alignment-research.md); the game itself ignores it
            mode = 'phrase' if arabic_mode in ('phrase', 'word') else arabic_mode
            drawn = ([('ctl', 0x8095, '')] if rtl else []) + self._arabic(items, mode)
        elif lang == 'en' and self.latin is not None:    # English in fonts.json's game_english font (2026-11-19)
            drawn = self._latin_words(items)
        else:
            return self._build(msg_id, items, template)
        # glyph-sized slices (21 px, the game's own glyph width); wider slices only when a message would pass the game's
        # 128 glyphs per message or not fit the largest atlas
        last = None
        for maxw in (21, 32, 48, 96, 255):
            try:
                data = self._build(msg_id, self._slices(drawn, maxw), template,
                                   atlas_scale=self.english_atlas_scale if lang == 'en' else 1)
            except ValueError as e:
                if 'atlas' not in str(e):
                    raise
                last = e
                continue
            if self.last_drawn <= 128 or maxw == 255:
                return data
        raise last if last else ValueError('message does not fit')

    def _build(self, msg_id, items, template, atlas_scale=1):
        glyphs, gindex = [], {}
        tb = bytearray()
        lines, ruby_lines, line_has_ruby = 1, 0, False

        def own(key, pic):
            if key not in gindex:
                gindex[key] = len(glyphs); glyphs.append(pic)
            return LOCAL_BASE + gindex[key]

        def code_bytes(code):
            # own glyph i is game code 401 + i, written (0x80 | low 7 bits, rest); equals the u16 0x391 + i only below 111
            if code >= LOCAL_BASE:
                g = 401 + code - LOCAL_BASE
                return bytes((0x80 | (g & 0x7f), g >> 7))
            return struct.pack('<H', code)
        drawn = 0
        for it in items:
            k = it[0]
            if k == 'ch':
                c = it[1]
                code = self.code_of.get(c)
                if code is None:
                    code = own(('ch', c), self.picture(c))
                tb += code_bytes(code); drawn += 1
            elif k == 'pic':                 # an Arabic word or letter-form picture
                tb += code_bytes(own(('pic', it[1]), it[2])); drawn += 1
            elif k == 'nl':
                tb += b'\x80\x80'; lines += 1
                ruby_lines += line_has_ruby; line_has_ruby = False
            elif k == 'ruby':
                bad = [c for c in it[1] if c not in self.ruby_code]
                if bad:
                    raise ValueError('furigana characters not in the furigana font: %r' % ''.join(bad))
                tb += b'\x90\x80' + bytes(self.ruby_code[c] for c in it[1]) + b'\0'; line_has_ruby = True
            elif k == 'rend':
                tb += b'\x91\x80'
            elif k == 'ctl':
                tb += struct.pack('<H', it[1]) + bytes.fromhex(it[2])
            elif k == 'end':
                tb += b'\x82\x80'
        ruby_lines += line_has_ruby
        self.last_drawn = drawn              # the game lays out and draws at most 128 glyphs per message (fn_817e8410)
        height = 21.0 + 20.0 * (lines - 1) + 10.0 * ruby_lines        # the game's rule for plain text; +9/10 per furigana line
        box0 = 0.0
        src = None
        if template is not None:
            t = Rmd(template)
            box0 = t.box[0]
            tl = 1 + sum(1 for x in t.tokens() if x[0] == 'nl')
            height = t.box[1] + 20.0 * (lines - tl)                     # keep the original's value, adjusted by the line change
            src = template[t.hs:t.hs + 0x1e0]                           # its texture ID and per-file IDs (see rmdwrite.gxm_for)
        return rmdwrite.build_rmd(msg_id, bytes(tb), glyphs, box=(box0, height), gxm_src=src,
                                  atlas_scale=atlas_scale)

    def _arabic(self, items, mode):
        """per line: reorder for display (control codes as neutral placeholders), Arabic runs -> pictures"""
        lines, cur, out = [], [], []
        for it in items:
            if it[0] == 'nl':
                lines.append(cur); cur = []
            else:
                cur.append(it)
        lines.append(cur)
        for li, line in enumerate(lines):
            if li:
                out.append(('nl',))
            if not any(x[0] == 'ch' and is_arabic(x[1]) for x in line):
                # no Arabic letter in the line ("Lv.", a number, a Latin name): keep it left to right as written
                # (reordering showed "Lv.1" as ". Lv1" in the game, 2026-11-20)
                out += line
                continue
            head, tail = [], []
            # layout codes at the very start (e.g. {8081:03} starting a help section) and {end} at the end stay put
            # (a colour that covers the whole line: kept first; anything else -- icons {8099:xx}, colour spans inside the
            # line -- is reordered with the words below, 2026-11-19)
            if line and line[0][0] == 'ctl' and line[0][1] == 0x8081 and not any(x[0] == 'end' or (x[0] == 'ctl' and x[1] == 0x8082) for x in line[1:-1]):
                head.append(line.pop(0))
            while line and line[-1][0] == 'end':
                tail.insert(0, line.pop())
            ph, s = {}, []
            for x in line:
                if x[0] == 'ch':
                    s.append(x[1])
                else:                                   # value slots and other codes: a private-use neutral placeholder
                    p = chr(0xE000 + len(ph)); ph[p] = x; s.append(p)
            disp = to_display(''.join(s))
            # colour spans: {8081:xx} starts a colour, {/color} (0x8082) ends it, and the game applies them in drawing
            # order (left to right). A span inside right-to-left text comes out mirrored (its end code left of its words,
            # its start code right of them), so the two codes trade places there.
            order = sorted(ph, key=lambda q: ord(q))           # placeholders in logical order
            pos = {q: disp.index(q) for q in ph if q in disp}
            k = 0
            while k < len(order):
                q = order[k]
                if ph[q][0] == 'ctl' and ph[q][1] == 0x8081:
                    e = next((r for r in order[k + 1:] if ph[r][0] in ('ctl', 'end') and (ph[r][0] == 'end' or ph[r][1] == 0x8082)), None)
                    if e is not None and q in pos and e in pos and pos[e] < pos[q]:
                        ph[q], ph[e] = ph[e], ph[q]
                k += 1
            out += head
            i = 0
            while i < len(disp):
                c = disp[i]
                if c in ph:
                    out.append(ph[c]); i += 1
                elif mode == 'phrase' and any(is_arabic(ch) for ch in disp):
                    # the whole stretch up to the next control code, in display order, as one picture in the Arabic
                    # font: punctuation, brackets, digits and Latin parts sit at their bidi places without the gaps the
                    # game's own letters left beside our pictures ("الهدف ." / a lone bracket, seen in the game 2026-11-19)
                    j = i
                    while j < len(disp) and disp[j] not in ph:
                        j += 1
                    chunk = disp[i:j]
                    if chunk.strip():
                        a, _ = self.draw(chunk)
                        out.append(('pic', 'p:' + chunk, (a, a.shape[1], 10)))
                    else:
                        out.extend(('ch', ch) for ch in chunk)
                    i = j
                elif is_arabic(c) and mode == 'phrase':
                    # words joined by single spaces become one picture (the font's own narrow space instead of the
                    # game's wide one); split at spaces where a picture would pass 255 px
                    j = i
                    while j < len(disp) and (is_arabic(disp[j]) or (disp[j] == ' ' and j + 1 < len(disp) and is_arabic(disp[j + 1]) and j > i)):
                        j += 1
                    chunk = disp[i:j]                       # the whole run: _slices() cuts it into glyph-sized slices
                    a, _ = self.draw(chunk)
                    out.append(('pic', 'p:' + chunk, (a, a.shape[1], 10)))
                    i = j
                elif is_arabic(c):
                    j = i
                    while j < len(disp) and is_arabic(disp[j]):
                        j += 1
                    run = disp[i:j]
                    a, cuts = self.draw(run)
                    if mode == 'word' and a.shape[1] <= 255:
                        out.append(('pic', 'w:' + run, (a, a.shape[1], 10)))
                    else:
                        for k in range(len(run)):
                            piece = a[:, cuts[k]:cuts[k + 1]]
                            if piece.shape[1] == 0:
                                continue
                            key = 'f:' + hashlib.sha1(bytes(piece.shape) + piece.tobytes()).hexdigest()[:16]
                            out.append(('pic', key, (piece.copy(), piece.shape[1], 10)))
                    i = j
                else:
                    out.append(('ch', c)); i += 1
            out += tail
        return out


def build_library(text_dir, map_dir):
    """code_of: char -> the code the game's text uses most; pic_of: char -> the game's most used picture of it"""
    from learn_map import ghash
    from build_sheet import load_maps
    B, G = load_maps(map_dir)
    votes = {int(k, 16): v[1] for k, v in json.load(open(os.path.join(map_dir, 'map_basic.json'), encoding='utf-8')).items()}
    code_of = {}
    for code, ch in B.items():
        if (code & 0xff) < 0x80:   # not writable as a two-byte code: the game reads a byte < 0x80 as a one-byte code (ぢ ぴ had 0x105/0x10f)
            continue
        if ch not in code_of or votes.get(code, -1) > votes.get(code_of[ch], -1):
            code_of[ch] = code
    use = collections.Counter(); rec = {}; pics = {}
    for sub in ('jp_base', 'jp_patch'):
        for p in glob.glob(os.path.join(text_dir, sub, '**', '*.rmd'), recursive=True):
            r = Rmd(open(p, 'rb').read()); lc = r.local_count()
            for i in range(lc):
                g = r.glyph(i); h = ghash(g)
                use[h] += 1
                if h not in pics:
                    pics[h] = g.copy(); rec[h] = r.recs[i][:2]
    by_char = {}
    for h, n in use.items():
        ch = G.get(h)
        if ch is None or ch in code_of:
            continue
        if ch not in by_char or n > use[by_char[ch]]:
            by_char[ch] = h
    pic_of = {ch: (pics[h], rec[h][0], rec[h][1]) for ch, h in by_char.items()}
    pickle.dump({'code_of': code_of, 'pic_of': pic_of}, open(os.path.join(map_dir, 'glyphlib.pkl'), 'wb'))
    print('library: %d coded characters, %d pictures' % (len(code_of), len(pic_of)))
