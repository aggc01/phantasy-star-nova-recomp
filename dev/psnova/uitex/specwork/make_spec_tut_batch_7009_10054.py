"""make_spec_tut_batch_7009_10054.py - specs (SPEC.md) for ten tutorial pictures (512x256 screenshots in help pages):
ui_tut_7009_0004, 7013_0001, 7014_0001, 7015_0002, 7016_0001, 8001_0001, 9001_0002, 9002_0002, 9003_0002, 10054_0001.
Written 2026-11-19. Boxes measured on the rendered PNGs (dump/psnova-l10n/scratch/research/uitex/png/{base,patch}) with
red/white/bright-pixel bounding boxes plus zoomed crops (dump/psnova-l10n/uitex/crops/). Wording from the text sheet
psnova_text_v5.tsv for the same Japanese (ids in the notes). ui_tut_9001_0002 has no Japanese (only the arena wall's
decorative pseudo-letters): no spec is written for it.

usage: python -s make_spec_tut_batch_7009_10054.py   -> dump/psnova-l10n/uitex/specs/<name>.json
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
OUT = os.path.join(ROOT, 'dump', 'psnova-l10n', 'uitex', 'specs')

RED = dict(color=[255, 0, 0], outline=[255, 255, 255], outline_px=2)          # red callout, 2-px white outline
HUD = dict(color=[235, 235, 235], outline=[0, 0, 0], outline_px=1)            # game UI text: light grey, dark edge


def lab(box, jp, en, ar, clear='inpaint', align='left', style=HUD, size=None, valign='center', **kw):
    d = dict(box=list(box), jp=jp, en=en, ar=ar, clear=clear, align=align)
    d.update(style)
    d.update(size=size, valign=valign)
    d.update(kw)
    return d


def erase(box, jp):
    """Erase-only label for a red callout: the whole box (Japanese red strokes + white outline, nothing else) is
    repainted from its surroundings. The automatic stroke mask left red strokes where the outline meets a white
    background (7009) and red specks (7014); whole-box inpainting of the tight text extent is clean."""
    return dict(box=list(box), jp=jp + ' (erase)', en='', ar='', clear='inpaint', inpaint_mask='box',
                inpaint_radius=5)


specs = {}

# ---------------------------------------------------------------- 7009_0004: Gigantes Blast support (help 780150)
specs['ui_tut_7009_0004'] = dict(
    texture='ui_tut_7009_0004.aif', archive='base',
    note='Gigantes Blast help picture. Red callout top left (red 12-329 x 11-28, 2-px white outline; the box is wider '
         'to the right over the cave background so the English keeps the Japanese height; the Arabic stays over the Japanese extent 8-334, right-aligned); wording after help 780150 '
         '("other players can support the Gigantes Blast"). HUD player names Batmar / Humar (made-up PSO-style names '
         'in the screenshot, transliterated) over the party/player bars: light grey, dark edge, small.',
    labels=[
        erase((8, 7, 334, 32), '押すことで他プレイヤーのブラストを支援'),
        lab((8, 7, 420, 32), '押すことで他プレイヤーのブラストを支援',
            "Press to support other players' Blasts", 'اضغط لدعم انفجار اللاعبين الآخرين', style=RED,
            clear='keep', box_ar=[8, 7, 334, 32]),
        lab((5, 174, 62, 187), 'バトマー', 'Batmar', 'باتمار', size_en=12, size_ar=11),
        lab((5, 207, 62, 221), 'ヒューマー', 'Humar', 'هيومار', size_en=12, size_ar=11),
    ])

# ---------------------------------------------------------------- 7013 / 7014: upper / lower level entrance (780118/9)
specs['ui_tut_7013_0001'] = dict(
    texture='ui_tut_7013_0001.aif', archive='base',
    note='Base upper level opened (help 780118 "Access it from the upper level entrance"). Red callout centred under '
         'the stairs (red 351-416 x 212-228, centre x 384); box widened over the floor so the English stays one line.',
    labels=[erase((348, 209, 419, 231), '上層入口'),
            lab((296, 208, 472, 232), '上層入口', 'Upper Level Entrance', 'مدخل الطابق العلوي',
                align='center', style=RED, clear='keep')])
specs['ui_tut_7014_0001'] = dict(
    texture='ui_tut_7014_0001.aif', archive='base',
    note='Base lower level opened (help 780119). Red callout centred (red 352-416 x 213-228, centre x 384); box '
         'widened over the floor.',
    labels=[erase((349, 210, 419, 231), '下層入口'),
            lab((296, 209, 472, 233), '下層入口', 'Lower Level Entrance', 'مدخل الطابق السفلي',
                align='center', style=RED, clear='keep')])

# ---------------------------------------------------------------- 7015_0002: "To the Ship" door plate (sheet 241102)
specs['ui_tut_7015_0002'] = dict(
    texture='ui_tut_7015_0002.aif', archive='base',
    note='Door name plate (sheet 241102 艦内へ = To the Ship). Text 233-279 x 66-80, left after the red book icon; '
         'the plate inside is flat (24,40,49) from y 65 to 81, filled; the icon (x 204-221) and the frame stay.',
    labels=[lab((227, 65, 309, 82), '艦内へ', 'To the Ship', 'إلى السفينة', clear='fill',
                fill_color=[24, 40, 49, 255], color=[238, 238, 238], outline=[8, 20, 26])])

# ---------------------------------------------------------------- 7016_0001: NPC name Sharon (sheet 30012)
specs['ui_tut_7016_0001'] = dict(
    texture='ui_tut_7016_0001.aif', archive='base',
    note='Story NPC name under the red speech bubble (sheet 30012 シャロン = Sharon): white with a dark edge, centred '
         '(text 353-414 x 80-93, centre x 383).',
    labels=[lab((340, 78, 428, 96), 'シャロン', 'Sharon', 'شارون', align='center', color=[246, 246, 246])])

# ---------------------------------------------------------------- 8001_0001: HP/PP/GP bars, player name Humar
specs['ui_tut_8001_0001'] = dict(
    texture='ui_tut_8001_0001.aif', archive='base',
    note='PP -> GP explanation, two player bars on black. The player name ヒューマー (made-up PSO-style name, '
         'transliterated Humar) above each bar (text 134-205 x 39-51 and 149-161); background pure black, filled.',
    labels=[
        lab((131, 37, 222, 53), 'ヒューマー', 'Humar', 'هيومار', clear='fill', fill_color=[0, 0, 0, 255],
            color=[230, 230, 230], size_en=15, size_ar=14),
        lab((131, 147, 222, 163), 'ヒューマー', 'Humar', 'هيومار', clear='fill', fill_color=[0, 0, 0, 255],
            color=[230, 230, 230], size_en=15, size_ar=14),
    ])

# ---------------------------------------------------------------- 9002 / 9003: Main Palette / Back Palette callouts
# sheet 780009/780018/780020/780053: 裏パレット = Back Palette / اللوحة الخلفية (the sheet's majority wording; the
# 'Subpalette' term is サブパレット, a different palette)
for n in ('ui_tut_9002_0002', 'ui_tut_9003_0002'):
    specs[n] = dict(
        texture=n + '.aif', archive='base',
        note='Palette flip help (780009). Red callouts above the two palettes: メインパレット red 76-188 x 128-144 '
             '(centre 132), 裏パレット red 356-440 x 128-142 (centre 398); 2-px white outline. Terms from the sheet: '
             'Main Palette / اللوحة الرئيسية, Back Palette / اللوحة الخلفية (780009, 780018, 780053). The △ □ '
             'buttons are symbols and stay.',
        labels=[
            erase((73, 125, 191, 147), 'メインパレット'),
            erase((353, 125, 443, 145), '裏パレット'),
            lab((60, 124, 204, 148), 'メインパレット', 'Main Palette', 'اللوحة الرئيسية', align='center', style=RED,
                clear='keep'),
            lab((334, 124, 462, 147), '裏パレット', 'Back Palette', 'اللوحة الخلفية', align='center', style=RED,
                clear='keep'),
        ])

# ---------------------------------------------------------------- 10054_0001: core list + two core detail windows
rows = [('獰猛な巨大獣・コア', 'Giant Vicious Beast Core', 'نواة الوحش العملاق الضاري'),
        ('スモール・コア', 'Small Core', 'نواة صغيرة'),
        ('巨大獣・コア', 'Giant Beast Core', 'نواة وحش عملاق'),
        ('大型兵器・コア', 'Large Weapon Core', 'نواة سلاح كبير'),
        ('ダーカー・コア', 'Darker Core', 'نواة داركر'),
        ('ギガンテス・コア', 'Gigantes Core', 'نواة جيغانتس'),
        ('輝く水晶竜族・コア', 'Shining Crystal Dragon Core', 'نواة تنين البلورة المتألق'),
        ('重厚な大型兵器・コア', 'Heavy Weapon Core', 'نواة سلاح كبير ثقيل'),
        ('深淵のダーカー・コア', 'Darker Abyss Core', 'نواة داركر الهاوية'),
        ('漆黒のダーカー・コア', 'Ebony Darker Core', 'نواة داركر الأبنوسية')]
import numpy as np
from PIL import Image
_png = np.asarray(Image.open(os.path.join(ROOT, 'dump', 'psnova-l10n', 'scratch', 'research', 'uitex', 'png', 'patch',
                                          'ui_tut_10054_0001.png')).convert('RGB')).astype(int)


def line_fills(x0, x1, y0, y1, sx0, sx1, jp):
    """Erase-only labels: each pixel row y0..y1-1 of [x0, x1) filled with the median colour of the same row at
    x sx0..sx1-1 (a text-free part of the same panel), consecutive equal rows merged. The list panels carry a vertical
    gradient between frame lines one or two pixels away, which inpainting smears into the box; per-row fills keep it."""
    out, run = [], None
    for y in range(y0, y1):
        c = [int(v) for v in np.median(_png[y, sx0:sx1], 0)]
        if run and run[1] == c:
            run[0][3] = y + 1
        else:
            run = [[x0, y, x1, y + 1], c]
            out.append(run)
    return [dict(box=b, jp=jp + ' (erase)', en='', ar='', clear='fill', fill_color=c + [255]) for b, c in out]


L = []
# erase first (fills), then the text labels draw with clear "keep" over the clean panels
L += line_fills(84, 106, 33, 43, 106, 118, 'コア')
for i, (jp, en, ar) in enumerate(rows):
    y = 46 + 16 * i                      # row frame lines y, y+1 and y+12, y+13; panel inside y+2..y+11
    L += line_fills(21, 114, y + 2, y + 12, 114, 172, jp)
L += line_fills(42, 87, 205, 218, 88, 105, '標準ソート')
L.append(lab((20, 31, 170, 44), 'コア', 'Cores', 'الأنوية', clear='keep', align='center',
             box_ar=[20, 30, 170, 45], size_ar=10))
for i, (jp, en, ar) in enumerate(rows):
    y = 46 + 16 * i
    # Arabic: same size on every row; one more pixel up and down for hamza / dots (أ ة ي)
    L.append(lab((20, y, 178, y + 13), jp, en, ar, clear='keep', size_ar=10, box_ar=[20, y - 1, 178, y + 14]))
L.append(lab((16, 204, 112, 218), '標準ソート', 'Standard', 'الترتيب الافتراضي', clear='keep', align='center',
             size_ar=10))
# window 1: attach part "Edge"
L.append(lab((304, 3, 478, 16), 'エッジ', 'Edge', 'حافة'))
L.append(lab((404, 44, 468, 58), 'パワーⅠ', 'Power I', 'القوة I', align='center', color=[222, 137, 0]))
L.append(lab((294, 59, 339, 73), 'レアリティ', 'Rarity', 'الندرة'))
L.append(lab((294, 74, 502, 112), '刃先を強化するアタッチパーツ。\nブレード形状の基礎的なモデル。',
             'Attachment that strengthens the blade tip.\nA basic blade-shaped model.',
             'قطعة إلحاق تقوّي حد النصل.\nطراز أساسي بشكل النصل.', valign='top', size_en=12, size_ar=10))
# window 2: core "Giant Vicious Beast Core" (1/2 stays)
L.append(lab((304, 127, 476, 141), '獰猛な巨大獣・コア', 'Giant Vicious Beast Core', 'نواة الوحش العملاق الضاري'))
L.append(lab((404, 169, 468, 183), 'パワーⅠ', 'Power I', 'القوة I', align='center'))
L.append(lab((294, 184, 339, 198), 'レアリティ', 'Rarity', 'الندرة'))
L.append(lab((294, 197, 502, 240), '強き生命力の源。\n力ある種に受け継ぎ、受け継がれ、\nさらなる力へと成長を続ける。',
             'Source of powerful vitality.\nPassed down through mighty species,\nit keeps growing ever stronger.',
             'مصدر حيوية قوية.\nتتوارثها الأنواع القوية جيلا بعد جيل\nوتواصل النمو نحو قوة أعظم.',
             valign='top', size_en=12, size_ar=10))
specs['ui_tut_10054_0001'] = dict(
    texture='ui_tut_10054_0001.aif', archive='patch',
    note='Core list (update copy). List header コア (sheet 21613 Cores), ten core rows (sheet 110001-110022, rows '
         'every 16 px from y 47, text after the icon at x 21, panel right edge 178), sort label 標準ソート (10701 '
         'Standard). Right: attach part window (Edge 130001, orange パワーⅠ 150001 Power I, Rarity 10314, description '
         '140001) and core window (description after 120003, line 2 shortened to fit). Page numbers 1/2 and stars '
         'stay. Menu text light grey with a dark edge. The list header, the ten rows and the sort pill are erased by '
         'per-pixel-row fills sampled from the text-free right part of the same panel (labels marked "(erase)", '
         'en/ar ""; inpainting smeared the frame lines into the thin panels), then drawn with clear "keep"; the '
         'two detail windows are inpainted.',
    labels=L)

os.makedirs(OUT, exist_ok=True)
for name, sp in specs.items():
    with open(os.path.join(OUT, name + '.json'), 'w', encoding='utf-8') as f:
        json.dump(sp, f, ensure_ascii=False, indent=2)
    print(name, len(sp['labels']))
