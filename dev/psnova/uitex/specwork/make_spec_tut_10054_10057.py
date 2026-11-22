"""Write the uitex specs for the tutorial pictures ui_tut_10054_0002, ui_tut_10057_0001, ui_tut_10057_0002 (2026-11-19).

10054_0002: core selection screen (Giant Vicious Beast Core list + item details).
10057_0001/0002: weapon list for a White Ticket exchange (Sword list + weapon details); 0002 is the same picture with a
red callout rectangle around the ticket/needed row (red pixels y 10..35, x 1..186), so its boxes stay inside it.

Clearing: the menu rows, title bars and info panels of these screenshots are horizontally uniform (per pixel row the
colour varies by a few levels, DXT noise), while Telea inpainting of the glyphs left visible smudges (tested). So each
Japanese text is erased by clear-only "fill" labels, one per pixel row (merged when equal), whose colour is the mean of
the same pixel row in a clean stretch of the same bar (sample range given per text). A pixel row that is not uniform
there (std > MAX_STD) falls back to an "inpaint" clear-only label. The text labels themselves use clear "keep" and a
draw box that may be larger than the erased area. The sort tabs (horizontal gradient) are inpainted as a whole
area (inpaint_mask box); the Equipped badge interior is filled with its yellow and gets dark text.

Boxes measured on the rendered PNGs (dump/psnova-l10n/scratch/research/uitex/png/patch/), crops in
dump/psnova-l10n/uitex/crops/t5457/. Wording from dump/psnova-l10n/sheet/psnova_text_v5.tsv (ids in the comments).
"""
import json, os, sys
import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'dev', 'psnova', 'rmdtext'))
sys.path.insert(0, os.path.join(ROOT, 'dev', 'psnova', 'uitex'))
import aiftex  # noqa: E402

OUT = os.path.join(ROOT, 'dump', 'psnova-l10n', 'uitex', 'specs')
SRC = os.path.join(ROOT, 'dump', 'psnova-l10n', 'scratch', 'research', 'patch')
MAX_STD = 14.0

WHITE = [245, 245, 245]
DARK = [8, 12, 16]

_img = {}


def picture(name):
    if name not in _img:
        d = open(os.path.join(SRC, name + '.aif'), 'rb').read()
        W, H, fmt, tid = aiftex.info(d)
        _img[name] = aiftex.decode(d[0x1e0:], W, H, fmt)[..., :3].astype(np.float64)
    return _img[name]


def line_fills(name, cbox, sx):
    """Clear-only labels erasing cbox [x0,y0,x1,y1) row by row with the mean colour of the row in x range sx."""
    img = picture(name)
    x0, y0, x1, y1 = cbox
    rows = []
    for y in range(y0, y1):
        seg = img[y, sx[0]:sx[1]]
        rows.append((y, seg.mean(0).round().astype(int).tolist(), float(seg.std(0).max())))
    out, i = [], 0
    while i < len(rows):
        y, c, s = rows[i]
        if s > MAX_STD:                                    # not uniform: inpaint this pixel row
            j = i
            while j + 1 < len(rows) and rows[j + 1][2] > MAX_STD:
                j += 1
            out.append({'box': [x0, y, x1, rows[j][0] + 1], 'jp': '', 'en': '', 'ar': '', 'clear': 'inpaint',
                        'note': 'clear only (row not uniform)'})
            i = j + 1
            continue
        j = i
        while j + 1 < len(rows) and rows[j + 1][2] <= MAX_STD and max(abs(a - b) for a, b in zip(rows[j + 1][1], c)) <= 2:
            j += 1
        col = np.mean([rows[k][1] for k in range(i, j + 1)], 0).round().astype(int).tolist()
        out.append({'box': [x0, y, x1, rows[j][0] + 1], 'jp': '', 'en': '', 'ar': '', 'clear': 'fill',
                    'fill_color': col + [255], 'note': 'clear only'})
        i = j + 1
    return out


def lab(box, jp, en, ar, align='left', clear='keep', color=WHITE, outline=DARK, **kw):
    d = {'box': box, 'jp': jp, 'en': en, 'ar': ar, 'clear': clear, 'align': align, 'valign': 'center',
         'color': color, 'outline': outline, 'outline_px': 1 if outline else 0, 'size': None}
    d.update(kw)
    return d


class Spec:
    def __init__(self, name):
        self.name, self.clears, self.texts = name, [], []

    def add(self, box, jp, en, ar, cbox=None, sx=None, **kw):
        if cbox is not None and sx == 'box':          # gradient background: repaint the whole area from its edges
            self.clears.append({'box': cbox, 'jp': '', 'en': '', 'ar': '', 'clear': 'inpaint', 'inpaint_mask': 'box',
                                'note': 'clear only (gradient: whole area inpainted)'})
        elif cbox is not None:
            self.clears += line_fills(self.name, cbox, sx)
        self.texts.append(lab(box, jp, en, ar, **kw))

    def labels(self):
        return self.clears + self.texts


ROW_SIZE = {'size_en': 10, 'size_ar': 9}        # one size for every list row (largest that fits all rows)


def add_rows(sp, tops, items):
    # erase the row interior (t-1..t+8) from x 20; English box = interior + 1 px, Arabic 2 px taller (alef-hamza and
    # descenders); rows never overlap
    for t, (jp, en, ar) in zip(tops, items):
        sp.add([20, t - 2, 177, t + 10], jp, en, ar, cbox=[20, t - 1, 177, t + 9], sx=(115, 165),
               box_ar=[20, t - 3, 177, t + 11], **ROW_SIZE)


# ------------------------------------------------------------------------------------------------ ui_tut_10054_0002
CORES = [
    ('獰猛な巨大獣・コア', 'Giant Vicious Beast Core', 'نواة الوحش العملاق الضاري'),      # 110003
    ('スモール・コア', 'Small Core', 'نواة صغيرة'),                                       # 110005
    ('巨大獣・コア', 'Giant Beast Core', 'نواة وحش عملاق'),                                # 110007
    ('大型兵器・コア', 'Large Weapon Core', 'نواة سلاح كبير'),                             # 110009
    ('ダーカー・コア', 'Darker Core', 'نواة داركر'),                                       # 110011
    ('ギガンテス・コア', 'Gigantes Core', 'نواة جيغانتس'),                                 # 110012
    ('輝く水晶竜族・コア', 'Shining Crystal Dragon Core', 'نواة تنين البلورة المتألق'),     # 110014
    ('重厚な大型兵器・コア', 'Heavy Weapon Core', 'نواة سلاح كبير ثقيل'),                  # 110020
    ('深淵のダーカー・コア', 'Darker Abyss Core', 'نواة داركر الهاوية'),                   # 110021
    ('漆黒のダーカー・コア', 'Ebony Darker Core', 'نواة داركر الأبنوسية'),                 # 110022
]


def spec_10054():
    sp = Spec('ui_tut_10054_0002')
    sp.add([11, 15, 133, 29], '個数選択', 'Select Number', 'اختيار العدد', cbox=[11, 16, 48, 28], sx=(55, 130))  # 25205
    sp.add([40, 32, 150, 44], 'コア', 'Cores', 'الأنوية', align='center', cbox=[84, 34, 105, 42], sx=(108, 145),
           box_ar=[40, 30, 150, 46], size_ar=10)  # 21613
    add_rows(sp, [49, 65, 81, 97, 113, 129, 145, 161, 177, 193], CORES)
    sp.add([16, 206, 111, 218], '標準ソート', 'Standard', 'الترتيب الافتراضي', align='center',
           cbox=[44, 207, 83, 217], sx='box')                                                                # 10701
    sp.add([300, 4, 478, 16], '獰猛な巨大獣・コア', 'Giant Vicious Beast Core', 'نواة الوحش العملاق الضاري',
           cbox=[298, 5, 382, 15], sx=(385, 445))
    sp.add([418, 45, 502, 57], 'パワーⅠ', 'Power I', 'القوة I', cbox=[417, 44, 454, 57], sx=(455, 470))          # 150001
    sp.add([294, 60, 340, 72], 'レアリティ', 'Rarity', 'الندرة', cbox=[294, 61, 337, 71], sx=(432, 500),
           box_ar=[294, 58, 340, 74], size_ar=10)          # 10314
    sp.add([294, 72, 502, 105], '強き生命力の源。\n力ある種に受け継ぎ、受け継がれ、\nさらなる力へと成長を続ける。',  # 120003
           'Source of powerful vitality.\nInherited and passed on by mighty species,\nit keeps growing into greater power.',
           'مصدر حيوية قوية.\nتتوارثها الأنواع القوية جيلا بعد جيل\nوتواصل النمو نحو قوة أعظم.',
           cbox=[294, 73, 428, 104], sx=(440, 500), line_gap_ar=-2)
    sp.add([302, 128, 500, 140], 'スモール・コア', 'Small Core', 'نواة صغيرة', cbox=[301, 128, 366, 140], sx=(368, 440))
    sp.add([294, 143, 500, 155], 'パワーⅡ', 'Power II', 'القوة II', cbox=[294, 144, 328, 154], sx=(340, 500))     # 150002
    sp.add([294, 156, 502, 169], '打撃力が５０上昇する。', 'Increases your S-ATK by 50.', 'يرفع قوة الضرب بمقدار 50.',
           cbox=[294, 156, 384, 168], sx=(400, 500))                                                             # 60001
    return {
        'texture': 'ui_tut_10054_0002.aif',
        'archive': 'patch',
        'note': ('Tutorial picture: core selection screen. Left: title bar (Select Number), list header (Cores), 10 core '
                 'rows, sort tab (Standard); right: item details of Giant Vicious Beast Core (title, Power I, Rarity, '
                 '3-line description 120003) and the Small Core box (title, Power II, effect 60001). 20 text labels; the '
                 'labels with an empty jp are clear-only: per-pixel-row fills sampled from a clean part of the same bar '
                 '(the screenshot rows are horizontally uniform; inpainting smudged); the gradient sort tab is inpainted as a '
                 'whole area. Text labels use clear keep. White text, 1 px dark outline; '
                 'left-aligned rows (Arabic right), centred header and sort tab. Counters 0/5, 1/2 and the stars stay. '
                 'Wording from psnova_text_v5.tsv (25205, 21613, 110003-110022, 10701, 150001, 150002, 10314, 120003, '
                 '60001). Written by dev/psnova/uitex/specwork/make_spec_tut_10054_10057.py.'),
        'labels': sp.labels(),
    }


# ------------------------------------------------------------------------------------------------ ui_tut_10057_000x
SWORDS = [
    ('アルバギガッシュ', 'Alva Gigush', 'ألبا غيغاش'),            # 90002
    ('ヴィタブレイカー', 'Vita Breaker', 'فيتا محطم'),            # 90003
    ('クレイモア', 'Claymore', 'كليمور'),                         # 90004
    ('コートエッジ', 'Coat Edge', 'حافة معطف'),                   # 90006
    ('ルインシャルム', 'Ruin Charm', 'سحر الخراب'),               # 90016
    ('ドラゴンスレイヤー', 'Dragon Slayer', 'قاتل التنين'),       # 90019
    ('アグリード', 'Agleed', 'أغريد'),                            # 90022
    ('ノヴァヌーク', 'Novanuhk', 'نوفانوك'),                      # 90024
    ('タルナーダ', 'Tarnada', 'تارنادا'),                         # 90007
    ('ラムダアリスティン', 'Lambda Aristin', 'لامدا أريستين'),    # 90010
]
ABIL_SIZE = {'size_en': 10, 'size_ar': 9}
SLOTS = [('エッジ', 'Edge', 'حافة'), ('シザー', 'Scissor', 'مقص'), ('ウェッジ', 'Wedge', 'إسفين'),
         ('スティール', 'Steel', 'فولاذ')]                                                        # 130001-130016
ABILS = [('パワーⅠ', 'Power I', 'القوة I'), ('ボディⅠ', 'Body I', 'جسم I'), ('アビリティⅠ', 'Ability I', 'قدرة I'),
         ('不屈の心', 'Indomitable Heart', 'قلب لا يقهر')]                                     # 150001 150039 150034 150205


def spec_10057(name, callout):
    sp = Spec(name)
    sp.add([10, 17, 94, 29], 'ホワイトチケット', 'White Ticket', 'تذكرة بيضاء', cbox=[11, 19, 133, 28], sx=(82, 96),
           align_ar='left')  # Arabic: kept apart from Needed (read as two fields)  # 350151
    sp.add([95, 17, 133, 29], '必要個数', 'Needed', 'المطلوب', align='right')  # 21616
    if callout:
        sp.add([40, 36, 150, 46], 'ソード', 'Sword', 'سيف', align='center', cbox=[81, 36, 107, 44], sx=(110, 150),
               box_ar=[40, 36, 150, 48], size_ar=10)
    else:
        sp.add([40, 33, 150, 45], 'ソード', 'Sword', 'سيف', align='center', cbox=[81, 35, 107, 44], sx=(110, 150),
               box_ar=[40, 31, 150, 47], size_ar=10)
    add_rows(sp, [51, 67, 83, 99, 115, 131, 147, 163, 179, 195], SWORDS)
    sp.add([16, 207, 111, 219], '標準ソート', 'Standard', 'الترتيب الافتراضي', align='center',
           cbox=[44, 208, 83, 218], sx='box')
    sp.add([305, 5, 500, 17], 'ソード', 'Sword', 'سيف', cbox=[304, 7, 332, 16], sx=(366, 440))                    # 90001
    # badge: a translucent yellow tag with dark text; the interior (inside its outline) is filled, dark text drawn
    sp.add([347, 49, 364, 57], '装備', 'Equip', 'مجهز', clear='fill', fill_color=[180, 176, 98, 255], align='center',
           color=[56, 58, 20], outline=None)
    sp.add([372, 48, 471, 59], 'エクステンド', 'Extend', 'توسيع', align='right', color=[255, 175, 0],
           outline=[8, 8, 24], cbox=[416, 48, 471, 59], sx=(375, 415))                                           # 152106
    sp.add([305, 132, 478, 144], 'コートエッジ', 'Coat Edge', 'حافة معطف', cbox=[304, 134, 357, 144], sx=(366, 440))
    for t, (jp, en, ar) in zip([204, 216, 228, 240], SLOTS):
        sp.add([304, t - 2, 416, t + 10], jp, en, ar, cbox=[303, t - 3, 350, t + 9], sx=(351, 370),
               box_ar=[304, t - 3, 416, t + 11], **ABIL_SIZE)
    for t, (jp, en, ar) in zip([204, 216, 228, 240], ABILS):
        sp.add([418, t - 2, 502, t + 10], jp, en, ar, cbox=[417, t - 3, 472, t + 9], sx=(473, 485),
               box_ar=[418, t - 3, 502, t + 11], **ABIL_SIZE)
    note = ('Tutorial picture: White Ticket exchange, Sword list. Left: title bar (White Ticket / Needed 3/3), list '
            'header (Sword), 10 sword rows, sort tab (Standard); right: Sword box (title, Equipped badge, Extend with '
            'the original star-7 kept after it) and Coat Edge details (title, 4 extend slots Edge/Scissor/Wedge/Steel, '
            '4 abilities Power I/Body I/Ability I/Indomitable Heart). 26 text labels; the labels with an empty jp are '
            'clear-only: per-pixel-row fills sampled from a clean part of the same bar; the gradient sort tab is '
            'inpainted as a whole area; the badge interior is filled with its yellow and gets dark text. White '
            'text with 1 px dark outline; orange (Extend) and yellow (badge) sampled from the Japanese. Left-aligned '
            'rows (Arabic right), centred header and sort tab; Needed right-aligned next to the counter. Wedge: the '
            'sheet Arabic for 130013 is "إسوريد" (looks wrong), used "إسفين" (wedge). The badge (19x8 px) has no sheet '
            'line in this sense: "Equip" / "مجهز". In Arabic the kept star-7 stays right of "توسيع". Wording from '
            'psnova_text_v5.tsv (350151, 21616, 90001-90024, 10701, 152106, 130001-130016, 150001, 150039, 150034, '
            '150205). Written by dev/psnova/uitex/specwork/make_spec_tut_10054_10057.py.')
    if callout:
        note = ('Same picture as ui_tut_10057_0001 plus a red callout rectangle (red y 10..35, x 1..186) around the '
                'White Ticket / Needed row; every box stays inside it or below its bottom edge. ' + note)
    return {'texture': name + '.aif', 'archive': 'patch', 'note': note, 'labels': sp.labels()}


def write(spec):
    p = os.path.join(OUT, spec['texture'][:-4] + '.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    n_text = sum(1 for l in spec['labels'] if l['jp'])
    n_inp = sum(1 for l in spec['labels'] if not l['jp'] and l['clear'] == 'inpaint')
    print(p, '%d text labels, %d clear-only (%d inpaint fallbacks)' % (n_text, len(spec['labels']) - n_text, n_inp))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    write(spec_10054())
    write(spec_10057('ui_tut_10057_0001', False))
    write(spec_10057('ui_tut_10057_0002', True))
