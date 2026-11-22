"""arabic.py - Arabic shaping and right-to-left ordering without external libraries (no raqm/fribidi on this PC).
Written 2026-11-18 for the Phantasy Star Nova Arabic text.

shape(text)      -> the same text with each Arabic letter replaced by its joined presentation form (isolated, final,
                    initial, medial; lam-alef ligatures), harakat removed
visual(line)     -> one line in display order for a left-to-right renderer: the line reversed, with runs of
                    digits / Latin kept left-to-right, brackets mirrored
to_display(line) -> visual(shape(line))
"""
import unicodedata

# letter: (isolated, final, initial, medial); None = the letter does not join forward (only isolated/final)
FORMS = {
    'ء': ('ﺀ', None, None, None),
    'آ': ('ﺁ', 'ﺂ', None, None),
    'أ': ('ﺃ', 'ﺄ', None, None),
    'ؤ': ('ﺅ', 'ﺆ', None, None),
    'إ': ('ﺇ', 'ﺈ', None, None),
    'ئ': ('ﺉ', 'ﺊ', 'ﺋ', 'ﺌ'),
    'ا': ('ﺍ', 'ﺎ', None, None),
    'ب': ('ﺏ', 'ﺐ', 'ﺑ', 'ﺒ'),
    'ة': ('ﺓ', 'ﺔ', None, None),
    'ت': ('ﺕ', 'ﺖ', 'ﺗ', 'ﺘ'),
    'ث': ('ﺙ', 'ﺚ', 'ﺛ', 'ﺜ'),
    'ج': ('ﺝ', 'ﺞ', 'ﺟ', 'ﺠ'),
    'ح': ('ﺡ', 'ﺢ', 'ﺣ', 'ﺤ'),
    'خ': ('ﺥ', 'ﺦ', 'ﺧ', 'ﺨ'),
    'د': ('ﺩ', 'ﺪ', None, None),
    'ذ': ('ﺫ', 'ﺬ', None, None),
    'ر': ('ﺭ', 'ﺮ', None, None),
    'ز': ('ﺯ', 'ﺰ', None, None),
    'س': ('ﺱ', 'ﺲ', 'ﺳ', 'ﺴ'),
    'ش': ('ﺵ', 'ﺶ', 'ﺷ', 'ﺸ'),
    'ص': ('ﺹ', 'ﺺ', 'ﺻ', 'ﺼ'),
    'ض': ('ﺽ', 'ﺾ', 'ﺿ', 'ﻀ'),
    'ط': ('ﻁ', 'ﻂ', 'ﻃ', 'ﻄ'),
    'ظ': ('ﻅ', 'ﻆ', 'ﻇ', 'ﻈ'),
    'ع': ('ﻉ', 'ﻊ', 'ﻋ', 'ﻌ'),
    'غ': ('ﻍ', 'ﻎ', 'ﻏ', 'ﻐ'),
    'ف': ('ﻑ', 'ﻒ', 'ﻓ', 'ﻔ'),
    'ق': ('ﻕ', 'ﻖ', 'ﻗ', 'ﻘ'),
    'ك': ('ﻙ', 'ﻚ', 'ﻛ', 'ﻜ'),
    'ل': ('ﻝ', 'ﻞ', 'ﻟ', 'ﻠ'),
    'م': ('ﻡ', 'ﻢ', 'ﻣ', 'ﻤ'),
    'ن': ('ﻥ', 'ﻦ', 'ﻧ', 'ﻨ'),
    'ه': ('ﻩ', 'ﻪ', 'ﻫ', 'ﻬ'),
    'و': ('ﻭ', 'ﻮ', None, None),
    'ى': ('ﻯ', 'ﻰ', None, None),
    'ي': ('ﻱ', 'ﻲ', 'ﻳ', 'ﻴ'),
    # letters outside the basic 28 (Persian/borrowed sounds, alef wasla), Presentation Forms-A (review 2026-11-18)
    'ٱ': ('ﭐ', 'ﭑ', None, None),
    'پ': ('ﭖ', 'ﭗ', 'ﭘ', 'ﭙ'),
    'چ': ('ﭺ', 'ﭻ', 'ﭼ', 'ﭽ'),
    'ڤ': ('ﭪ', 'ﭫ', 'ﭬ', 'ﭭ'),
    'ک': ('ﮎ', 'ﮏ', 'ﮐ', 'ﮑ'),
    'گ': ('ﮒ', 'ﮓ', 'ﮔ', 'ﮕ'),
    'ی': ('ﯼ', 'ﯽ', 'ﯾ', 'ﯿ'),
}
LAMALEF = {'آ': ('ﻵ', 'ﻶ'), 'أ': ('ﻷ', 'ﻸ'), 'إ': ('ﻹ', 'ﻺ'), 'ا': ('ﻻ', 'ﻼ')}
TATWEEL = 'ـ'
MIRROR = {'(': ')', ')': '(', '[': ']', ']': '[', '{': '}', '}': '{', '<': '>', '>': '<', '«': '»', '»': '«',
          '（': '）', '）': '（', '「': '」', '」': '「', '『': '』', '』': '『'}


def is_harakah(ch):
    return unicodedata.category(ch) == 'Mn' and 'ً' <= ch <= 'ٟ' or ch == 'ٰ'


def joins_forward(ch):
    return ch in FORMS and FORMS[ch][2] is not None or ch == TATWEEL


def joins_back(ch):
    """the letter can connect to the letter before it (hamza ء cannot: it has no final form)"""
    return ch in FORMS and FORMS[ch][1] is not None or ch == TATWEEL


def shape(text):
    s = [c for c in text if not is_harakah(c)]
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c not in FORMS:
            out.append(c); i += 1; continue
        prev = s[i - 1] if i > 0 else ''
        connect_prev = bool(prev) and joins_forward(prev)
        if c == 'ل' and i + 1 < len(s) and s[i + 1] in LAMALEF:
            out.append(LAMALEF[s[i + 1]][1 if connect_prev else 0]); i += 2; continue
        nxt = s[i + 1] if i + 1 < len(s) else ''
        connect_next = bool(nxt) and joins_back(nxt) and FORMS[c][2] is not None
        iso, fin, ini, med = FORMS[c]
        if connect_prev and connect_next:
            out.append(med)
        elif connect_prev:
            out.append(fin or iso)
        elif connect_next:
            out.append(ini)
        else:
            out.append(iso)
        i += 1
    return ''.join(out)


def _kind(ch):
    """'R' Arabic, 'L' Latin and other left-to-right letters, 'E' numbers, 'N' neutral (spaces, punctuation, and the
    private-use characters the encoder puts in for value slots and other control codes)"""
    if 0xE000 <= ord(ch) <= 0xF8FF:
        return 'N'
    d = unicodedata.bidirectional(ch)
    if d in ('R', 'AL'):
        return 'R'
    if d == 'L':
        return 'L'
    if d in ('EN', 'AN'):
        return 'E'
    return 'N'


def visual(line):
    """reorder one logical line of a right-to-left paragraph for a left-to-right renderer (a simplified Unicode bidi:
    Latin words and numbers are left-to-right islands; a run of neutrals takes the direction of its neighbours when both
    are left-to-right, else the paragraph direction (right-to-left); numbers count as right-to-left for that (rule N1);
    the line edges count as right-to-left)"""
    k = [_kind(c) for c in line]
    n = len(k)
    strong = ['R' if x == 'E' else x for x in k]          # for neutral resolution only
    d = ['L' if x in ('L', 'E') else 'R' for x in k]        # run direction: numbers are left-to-right islands
    i = 0
    while i < n:
        if k[i] != 'N':
            i += 1; continue
        j = i
        while j < n and k[j] == 'N':
            j += 1
        left = strong[i - 1] if i > 0 else 'R'
        right = strong[j] if j < n else 'R'
        for m in range(i, j):
            d[m] = 'L' if (left == 'L' and right == 'L') else 'R'
        i = j
    runs, start = [], 0
    for m in range(1, n + 1):
        if m == n or d[m] != d[start]:
            runs.append((d[start], line[start:m])); start = m
    out = []
    for kind, t in reversed(runs):
        out.append(t if kind == 'L' else ''.join(MIRROR.get(c, c) for c in reversed(t)))
    return ''.join(out)


def to_display(line):
    return visual(shape(line))


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    for t in ['مرحباً بك في السفينة!', 'اضغط Enter للمتابعة (2 مرة).', 'لا بأس، سلاح الفرقة ٣']:
        print(t, '->', to_display(t))
