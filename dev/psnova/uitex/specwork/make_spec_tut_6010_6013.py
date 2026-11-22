"""make_spec_tut_6010_6013.py - specs (SPEC.md) for ten tutorial pictures (512x256 screenshots in help pages), 2026-11-19:
ui_tut_6010_0001..0004 (Class Counter: menu, class change, Gran Arts list, Skill Board), ui_tut_6011_0001 (cuisine),
ui_tut_6012_0001..0003 (weapon creation: weapon list, core list, red S-ATK/R-ATK/T-ATK callouts),
ui_tut_6013_0001..0002 (attachments: slot cards, ability/core/shape selection with red callouts).

All base-archive textures. Boxes measured on the rendered PNGs (dump/psnova-l10n/scratch/research/uitex/png/base/) with
bright/red-pixel bounding boxes and row profiles (dump/psnova-l10n/uitex/crops/tight.py, prof.py, core.py) plus zoomed
crops (crops/zoom.py). Wording from dump/psnova-l10n/sheet/psnova_text_v5.tsv for the same Japanese (ids in comments);
Arabic per docs/psnova/arabic-style.md. Conventions as make_spec_tut_10054_10057.py: white text with a 1 px dark
outline, list rows size 10 (Arabic 9, 8 with a hamza on alef), left-aligned rows (Arabic right, apply_spec flips
"left"), centred headers and sort tabs; red callouts red with a 2 px white outline. Row boxes start 1-2 px left of the
first Japanese glyph (x profiles) and stay inside the row frames (inpaint, default telea). Checked with apply_spec into
dump/psnova-l10n/uitex/crops/pv601x/ (before/after stacks there).
Fonts lack the Roman-numeral glyphs (Ⅱ) and ※: Latin "II" and "*" are used.

usage: python -s make_spec_tut_6010_6013.py   -> dump/psnova-l10n/uitex/specs/<name>.json
"""
import json, os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
OUT = os.path.join(ROOT, 'dump', 'psnova-l10n', 'uitex', 'specs')

WHITE = [245, 245, 245]
GREY = [168, 168, 166]          # greyed-out rows (current class, weapons that cannot be made, unusable attachment)
DARK = [8, 12, 16]
PANEL = [24, 36, 49, 255]
RED = dict(color=[255, 8, 8], outline=[255, 255, 255], outline_px=2)
# labels on the flat dark info panels (stat column, item details, material rows, skill list): filled with the panel
# colour (24,36,49), which removes the dark glyph outlines the inpaint leaves as faint smudges on a flat panel
FILL = dict(clear='fill', fill_color=PANEL)


def lab(box, jp, en, ar, align='left', clear='inpaint', color=WHITE, outline=DARK, **kw):
    d = {'box': list(box), 'jp': jp, 'en': en, 'ar': ar, 'clear': clear, 'align': align, 'valign': 'center',
         'color': color, 'outline': outline, 'outline_px': 1 if outline else 0, 'size': None}
    d.update(kw)
    return d


def ar_taller(label, box_ar):
    """Arabic needs a taller box than the Japanese occupied (hamza on alef: 13-14 px). An inpainted box that reaches
    the panel frame row erases the glyphs less reliably, so the label is split: the first one clears the Japanese box
    in both languages and draws only the English (Arabic ""), the second one draws only the Arabic in the taller box
    without clearing (English "", clear keep)."""
    a = dict(label, ar='')
    b = dict(label, en='', clear='keep', box=list(box_ar))
    for k in ('inpaint_dilate', 'inpaint_shadow', 'fill_color', 'size_en'):
        b.pop(k, None)
    return [a, b]


ROW = {'size_en': 10, 'size_ar': 9}
# list rows: no stray stroke or outline remnant left where the right-aligned Arabic leaves the row empty
ROW_CLEAR = {'inpaint_dilate': 2, 'inpaint_shadow': 3}


def rows(x0, x1, tops, items):
    """list rows: text glyph top t (8 px glyphs); box [t-2, t+10) for both languages (the row frames sit just
    outside). Arabic with a hamza on alef is 13 px tall even at size 8: size 8, drawn in a box 1 px higher
    (ar_taller)."""
    out = []
    for t, it in zip(tops, items):
        jp, en, ar = it[:3]
        kw = dict(ROW, **ROW_CLEAR)
        tall = any(c in ar for c in 'أإآ')
        if tall:
            kw['size_ar'] = 8
        if len(it) > 3:
            kw.update(it[3])
        if kw.get('color') == GREY:         # dim glyphs over the see-through panel: lower threshold, no ー left over
            kw.setdefault('inpaint_threshold', 30)
        d = lab([x0, t - 2, x1, t + 10], jp, en, ar, **kw)
        out.extend(ar_taller(d, [x0, t - 3, x1, t + 10]) if tall else [d])
    return out


def stats(x0, x1, tops, items):
    """stat table labels (11-12 px pitch): box [t-1, t+10), size = the largest that fits (9 / 8)."""
    return [lab([x0, t - 1, x1, t + 10], jp, en, ar, **FILL) for t, (jp, en, ar) in zip(tops, items)]


STAT7 = [('打撃力', 'S-ATK', 'قوة الضرب'), ('射撃力', 'R-ATK', 'قوة الرمي'), ('法撃力', 'T-ATK', 'قوة التقنية'),  # 10307-9
         ('技量', 'DEX', 'البراعة'), ('打撃防御', 'S-DEF', 'دفاع الضرب'), ('射撃防御', 'R-DEF', 'دفاع الرمي'),     # 10310-2
         ('法撃防御', 'T-DEF', 'دفاع التقنية')]                                                              # 10313
RESIST6 = [('炎耐性', 'Resist', 'مقاومة نار'), ('氷耐性', 'Resist', 'مقاومة جليد'), ('雷耐性', 'Resist', 'مقاومة برق'),
           ('風耐性', 'Resist', 'مقاومة رياح'), ('光耐性', 'Resist', 'مقاومة ضوء'), ('闇耐性', 'Resist', 'مقاومة ظلام')]
# 10334-10339: the game's English stat line says "Resist" after the element icon; the Arabic names the element.

MAT_HEAD = [  # material table header (6010_0003, 6012_0001): 21615-21617
    lab([294, 163, 414, 175], '必要素材', 'Materials Needed', 'المواد المطلوبة'),
    lab([419, 163, 458, 175], '必要個数', 'Needed', 'المطلوب', align='center'),
    lab([462, 163, 501, 175], '所持数', 'Owned', 'المتوفر', align='center'),
]

specs = {}

# ------------------------------------------------------------------------------------------------ 6010_0001
specs['ui_tut_6010_0001'] = dict(
    texture='ui_tut_6010_0001.aif', archive='base',
    note='Class Counter menu over the base (help: class change). Five menu rows top left (glyph tops 34/50/66/82/98, '
         'x from 9, row panels end at x 127): Change Class (selected, yellow frame), Learn Gran Arts, Learn Techniques, '
         'Skill Board, Leave. White text, dark edge; inpainted (screenshot panels). Sheet 20101, 20135, 20136, 11010, '
         '11107. Written by dev/psnova/uitex/specwork/make_spec_tut_6010_6013.py.',
    labels=rows(8, 125, [34, 50, 66, 82, 98], [
        ('クラスを変更', 'Change Class', 'تغيير الفئة'),
        ('グランアーツを習得', 'Learn Gran Arts', 'تعلم فنون غران'),
        ('テクニックを習得', 'Learn Techniques', 'تعلم التقنيات'),
        ('スキルボード', 'Skill Board', 'لوحة المهارات'),
        ('退出', 'Leave', 'مغادرة'),
    ]))

# ------------------------------------------------------------------------------------------------ 6010_0002
specs['ui_tut_6010_0002'] = dict(
    texture='ui_tut_6010_0002.aif', archive='base',
    note='Class change screen. Top left: player box (name Humar, made-up PSO-style name as in ui_tut_7009_0004, and '
         'current class Hunter); class list (header Class, rows Hunter greyed = current class, Ranger selected, Force); '
         'caution box (* CAUTION * + the 4-line text 23101 set in 3 lines); stat column (S-ATK..T-DEF; the GP '
         'label is hidden under the red tutorial arrow and the first stat label is partly under it, so its box starts '
         'at x 201 right of the arrow: the arrow is never inside a box); right: Ranger box (title, class description '
         '660002 in 3 lines, "This class can equip:" 20116, Assault Rifle 10805, Twin Machineguns 10806). Element '
         'rows have icons only (no text). The stat column and the Ranger box are flat (24,36,49) panels: filled; the '
         'caution panel is shaded (inpainted), its box stays '
         'inside the panel frame (frame x 7/182, y 142/202). '
         'Written by dev/psnova/uitex/specwork/make_spec_tut_6010_6013.py.',
    labels=[
        lab([12, 3, 180, 15], 'ヒューマー', 'Humar', 'هيومار', **ROW),
        lab([23, 17, 132, 29], 'ハンター', 'Hunter', 'صياد', **ROW),                               # 10201
        lab([40, 49, 150, 61], 'クラス', 'Class', 'الفئة', align='center'),                       # 11008
        *rows(31, 140, [66, 82, 98], [
            ('ハンター', 'Hunter', 'صياد', {'color': GREY}),
            ('レンジャー', 'Ranger', 'رامي'),                                                       # 10202
            ('フォース', 'Force', 'ساحر'),                                                          # 10203
        ]),
        lab([40, 144, 150, 156], '※注意※', '* CAUTION *', '* تنبيه *', align='center'),           # 23102
        lab([16, 156, 180, 200], 'クラス変更すると、装備中の武器や\n防具が無効になることがあります。\n'
            '無効になっている装備は\nリスト上で名前が灰色に表示されます。',
            'Changing class may make your equipped\nweapons or armor unusable. Unusable\n'
            'equipment is shown in gray in the list.',
            'قد يؤدي تغيير الفئة إلى تعطيل الأسلحة\nأو الدروع المجهزة. تظهر المعدات المعطلة\n'
            'باللون الرمادي في القائمة.',
            valign='top', size_en=10, size_ar=9, line_gap=1),
        lab([201, 89, 244, 101], '打撃力', 'S-ATK', 'قوة الضرب', **FILL),     # values here are 2 digits (x >= 250)
        *stats(189, 244, [103, 115, 126, 138, 150, 162], STAT7[1:]),
        lab([304, 48, 500, 60], 'レンジャー', 'Ranger', 'رامي'),
        lab([294, 62, 490, 104], '射撃武器による攻撃を主とし、中距離での戦\n闘を得意とするクラス。\n'
            '射撃に必要な能力が軒並み高く、精密な射撃\nでの攻撃が可能。',
            'Utilizes ranged weapons to fight at mid-range.\nHigh proficiency at all shooting abilities,\n'
            'including precision attacks.',
            'فئة تقاتل بأسلحة الرمي من مسافة\nمتوسطة. قدراتها في الرمي عالية،\nوتتيح هجمات رمي دقيقة.',
            valign='top', size_en=10, size_ar=10, line_gap=1, **FILL),
        lab([294, 105, 490, 117], '装備可能武器', 'This class can equip:', 'الأسلحة القابلة للتجهيز:',
            box_ar=[294, 104, 490, 117], **FILL),
        lab([304, 117, 400, 129], 'アサルトライフル', 'Assault Rifle', 'بندقية هجومية', **FILL),
        lab([413, 117, 490, 129], 'ツインマシンガン', 'Twin Machineguns', 'رشاشان', **FILL),
    ])

# ------------------------------------------------------------------------------------------------ 6010_0003
specs['ui_tut_6010_0003'] = dict(
    texture='ui_tut_6010_0003.aif', archive='base',
    note='Gran Arts list (Sword). Left: list header Sword, rows Rising Edge, Twister Fall (selected), Nova Strike, '
         'Sonic Arrow (Lv. column at x 138 stays); right: Twister Fall details (title, Power / GP Cost / Dex Mod labels '
         'left of their "/value", 2-line description 570003 on the flat panel = fill), material table (header '
         'Materials Needed / Needed / Owned, rows Memory Fragment A, Gran Piece). Sheet 10801, 560002-560007, 10302-4, '
         '21615-7, 350047, 350001. Written by dev/psnova/uitex/specwork/make_spec_tut_6010_6013.py.',
    labels=[
        lab([40, 32, 150, 44], 'ソード', 'Sword', 'سيف', align='center'),
        *rows(20, 134, [49, 65, 81, 97], [
            ('ライジングエッジ', 'Rising Edge', 'حافة صاعدة'),
            ('ツイスターフォール', 'Twister Fall', 'تويستر فول'),
            ('ノヴァストライク', 'Nova Strike', 'ضربة نوفا'),
            ('ソニックアロウ', 'Sonic Arrow', 'سهم صوتي'),
        ]),
        lab([304, 39, 500, 51], 'ツイスターフォール', 'Twister Fall', 'تويستر فول'),
        lab([348, 65, 382, 77], '威力', 'Power', 'القوة', size_en=9, size_ar=9, **FILL),
        lab([348, 78, 382, 90], '消費GP', 'GP Cost', 'تكلفة GP', size_en=9, **FILL),
        lab([412, 65, 468, 77], '技量補正', 'Dex Mod', 'تعديل البراعة', align='right', size_en=9, size_ar=9, **FILL),
        lab([294, 106, 490, 130], '高く飛び上がり、回転攻撃を行った後に\n衝撃波を伴う降下攻撃を行う。',
            'Jumps high, performs a spinning attack\nand sends a shockwave upon descent.',
            'يقفز عاليا وينفذ هجوما دورانيا،\nثم يهبط بهجوم يطلق موجة صدمية.',
            size_en=10, size_ar=10, line_gap_en=-1, **FILL),
        *MAT_HEAD,
        lab([304, 176, 412, 188], 'メモリーフラグメントＡ', 'Memory Fragment A', 'شظية ذاكرة A', **ROW, **FILL),
        lab([304, 189, 412, 201], 'グランピース', 'Gran Piece', 'قطعة غران', **ROW, **FILL),
    ])

# ------------------------------------------------------------------------------------------------ 6010_0004
specs['ui_tut_6010_0004'] = dict(
    texture='ui_tut_6010_0004.aif', archive='base',
    note='Skill Board screen: board header (centred, 11010), right panel column headers Set Skill / Combo Skill '
         '(23004/5) and the set skills Just Guard / Step Attack (50010, 50016) after their icons. Inpainted. '
         'Set Skill Arabic written with one shadda only (style guide). '
         'Written by dev/psnova/uitex/specwork/make_spec_tut_6010_6013.py.',
    labels=[
        lab([70, 16, 190, 29], 'スキルボード', 'Skill Board', 'لوحة المهارات', align='center'),
        lab([271, 19, 388, 31], 'セットスキル', 'Set Skill', 'المهارة المعيّنة'),
        lab([393, 19, 500, 31], 'コンボスキル', 'Combo Skill', 'مهارة التتابع'),
        lab([283, 35, 388, 47], 'ジャストガード', 'Just Guard', 'دفاع دقيق', **ROW, **FILL),
        lab([283, 48, 388, 60], 'ステップアタック', 'Step Attack', 'هجوم الخطوة', **ROW, **FILL),
    ])

# ------------------------------------------------------------------------------------------------ 6011_0001
specs['ui_tut_6011_0001'] = dict(
    texture='ui_tut_6011_0001.aif', archive='base',
    note='Cuisine menu (three rows: dish name, then "/" + effect). The "/" at x 91 stays; names in x 21-90, effects '
         'in x 94-178 (the Latin "up" is part of the Japanese label and is replaced too). Sheet 21301-21306. '
         'Written by dev/psnova/uitex/specwork/make_spec_tut_6010_6013.py.',
    labels=[
        *rows(21, 90, [34, 50, 66], [
            ('ガッツ料理', 'Guts Cuisine', 'طعام العزيمة'),
            ('スタミナ料理', 'Stamina Cuisine', 'طعام قدرة التحمل', {'size_ar': None}),
            ('グルメ料理', 'Gourmet Cuisine', 'طعام الذواقة'),
        ]),
        *rows(94, 178, [34, 50, 66], [
            ('攻撃力up', 'ATK UP', 'زيادة الهجوم'),
            ('防御力up', 'DEF UP', 'زيادة الدفاع'),
            ('特殊効果up', 'Special UP', 'زيادة التأثير الخاص', {'size_ar': None}),
        ]),
    ])

# ------------------------------------------------------------------------------------------------ 6012_0001
specs['ui_tut_6012_0001'] = dict(
    texture='ui_tut_6012_0001.aif', archive='base',
    note='Weapon creation, Sword list. Top right: Owned / Item Pack cells (21617, 21618); left: header Sword, 9 rows '
         '(Sword, Alva Gigush selected and white, the other seven greyed in the Japanese and kept grey), sort tab '
         'Standard (10701); stat column (S-ATK..T-DEF, then six element "Resist" rows after their icons; HP/GP are '
         'Latin and stay); right: weapon title, material table (Darker Core 110001, Terra Mander Scale 350174, '
         'Dendritic Material 350049). Weapon names 90002-90027. '
         'Written by dev/psnova/uitex/specwork/make_spec_tut_6010_6013.py.',
    labels=[
        lab([293, 17, 347, 29], '所持数', 'Owned', 'المتوفر'),
        lab([401, 17, 450, 29], 'パック容量', 'Item Pack', 'سعة الحقيبة'),
        lab([40, 32, 150, 44], 'ソード', 'Sword', 'سيف', align='center'),
        *rows(20, 178, [49, 65, 81, 97, 113, 129, 145, 161, 177], [
            ('ソード', 'Sword', 'سيف', {'color': GREY}),
            ('アルバギガッシュ', 'Alva Gigush', 'ألبا غيغاش'),
            ('ヴィタブレイカー', 'Vita Breaker', 'فيتا محطم', {'color': GREY}),
            ('クレイモア', 'Claymore', 'كليمور', {'color': GREY}),
            ('キャリバー', 'Calibur', 'كاليبر', {'color': GREY}),
            ('タルナーダ', 'Tarnada', 'تارنادا', {'color': GREY}),
            ('アーディロウ', 'Ardillo', 'آرديلو', {'color': GREY}),
            ('モーニング・レッド', 'Morning Red', 'أحمر الصباح', {'color': GREY}),
            ('フォスティプス', 'Fostibus', 'فوستيبوس', {'color': GREY}),
        ]),
        lab([16, 206, 111, 218], '標準ソート', 'Standard', 'الترتيب الافتراضي', align='center'),
        *stats(189, 236, [75, 86, 98, 110, 122, 133, 145], STAT7),
        *stats(200, 246, [157, 168, 180, 192, 204, 216], RESIST6),
        *ar_taller(lab([304, 35, 455, 47], 'アルバギガッシュ', 'Alva Gigush', 'ألبا غيغاش'), [304, 34, 455, 48]),
        *MAT_HEAD,
        lab([304, 176, 412, 188], 'ダーカー・コア', 'Darker Core', 'نواة داركر', **ROW, **FILL),
        lab([304, 188, 412, 200], 'テッラマンデルの鱗片', 'Terra Mander Scale', 'حرشفة تيرا مانديل', **ROW, **FILL),
        lab([304, 201, 412, 213], '樹木状の鉱物', 'Dendritic Material', 'مادة معدنية شجرية', **ROW, **FILL),
    ])

# ------------------------------------------------------------------------------------------------ 6012_0002
specs['ui_tut_6012_0002'] = dict(
    texture='ui_tut_6012_0002.aif', archive='base',
    note='Weapon creation, core list. Top left: weapon box title Alva Gigush; header Cores (21613), 4 rows Darker Core '
         '(110001), sort tab Standard; stat column as 6012_0001 shifted down (GP at 80); right: Darker Core details '
         '(title, Rarity 10314, 3-line description 120001, inpainted) and the Alva Gigush box title. '
         'Written by dev/psnova/uitex/specwork/make_spec_tut_6010_6013.py.',
    labels=[
        *ar_taller(lab([66, 3, 175, 15], 'アルバギガッシュ', 'Alva Gigush', 'ألبا غيغاش', size_en=10, size_ar=8), [66, 2, 175, 15]),
        *ar_taller(lab([31, 49, 150, 61], 'コア', 'Cores', 'الأنوية', align='center'), [31, 48, 150, 62]),
        *rows(20, 178, [65, 81, 97, 113], [('ダーカー・コア', 'Darker Core', 'نواة داركر')] * 4),
        lab([16, 222, 111, 234], '標準ソート', 'Standard', 'الترتيب الافتراضي', align='center'),
        *stats(189, 236, [91, 103, 115, 126, 138, 150, 162], STAT7),
        *stats(200, 246, [173, 185, 197, 209, 220, 232], RESIST6),
        lab([304, 4, 470, 16], 'ダーカー・コア', 'Darker Core', 'نواة داركر'),
        lab([294, 60, 342, 72], 'レアリティ', 'Rarity', 'الندرة', **FILL),
        lab([293, 72, 490, 110], '毒された強き生命力の源。\n貪欲に他者を攻撃し生き延びようと\nあらゆる進化の可能性を秘める。',
            'Source of tainted, powerful vitality.\nGreedily attacking others to survive,\n'
            'it holds every possibility of evolution.',
            'مصدر حيوية قوية مسمومة.\nتهاجم الآخرين بجشع لتبقى حية،\nوتخفي كل إمكانيات التطور.',
            valign='top', size_en=10, size_ar=10, **FILL),
        *ar_taller(lab([304, 131, 455, 143], 'アルバギガッシュ', 'Alva Gigush', 'ألبا غيغاش'), [304, 130, 455, 144]),
    ])

# ------------------------------------------------------------------------------------------------ 6012_0003
specs['ui_tut_6012_0003'] = dict(
    texture='ui_tut_6012_0003.aif', archive='base',
    note='Zoomed weapon box (2x scale screenshot): title Alva Gigush (large), three red callouts with white outline '
         'under the S-ATK / R-ATK / T-ATK icons (red 201-248, 280-332, 364-412 x 72-88; boxes centred on them and '
         'widened for the Arabic), and the material table header cut by the bottom edge (Materials Needed / Needed / '
         'Owned, glyph tops ~245, drawn in the visible strip). Left column numbers stay. '
         'Written by dev/psnova/uitex/specwork/make_spec_tut_6010_6013.py.',
    labels=[
        lab([122, 8, 420, 29], 'アルバギガッシュ', 'Alva Gigush', 'ألبا غيغاش', size_en=18),
        lab([185, 68, 265, 92], '打撃力', 'S-ATK', 'قوة الضرب', align='center', **RED),
        lab([267, 68, 347, 92], '射撃力', 'R-ATK', 'قوة الرمي', align='center', **RED),
        lab([349, 68, 431, 92], '法撃力', 'T-ATK', 'قوة التقنية', align='center', **RED),
        lab([102, 242, 250, 256], '必要素材', 'Materials Needed', 'المواد المطلوبة', valign='top'),
        lab([338, 242, 410, 256], '必要個数', 'Needed', 'المطلوب', align='center', valign='top'),
        lab([424, 242, 486, 256], '所持数', 'Owned', 'المتوفر', align='center', valign='top'),
    ])

# ------------------------------------------------------------------------------------------------ 6013_0001
specs['ui_tut_6013_0001'] = dict(
    texture='ui_tut_6013_0001.aif', archive='base',
    note='Attachment editor: four slot cards (part name indented at x 67, ability at x 55): Gran Blade F / Mind III, '
         'Gran Blade D / Mind I, Rug / Fire Resist Down II (the glyph is 炎属性ダウンⅡ, 150159), Slot 4 / No '
         'Attachments; bottom right button prompts Reset (after the SELECT icon) and Zoom (after L/R), icons stay. '
         'Sheet 130051, 150051, 130049, 150049, 130129, 150159, 21632, 21633; Reset/Zoom have no menu line in the '
         'sheet (wording after help 780001). Written by dev/psnova/uitex/specwork/make_spec_tut_6010_6013.py.',
    labels=[
        lab([66, 3, 176, 15], 'グランブレードＦ', 'Gran Blade F', 'نصل غران F', **ROW),
        lab([55, 16, 176, 28], 'マインドⅢ', 'Mind III', 'عقل III', **ROW),
        lab([66, 47, 176, 59], 'グランブレードＤ', 'Gran Blade D', 'نصل غران D', **ROW),
        lab([55, 59, 176, 71], 'マインドⅠ', 'Mind I', 'عقل I', **ROW),
        lab([66, 88, 176, 100], 'ラグ', 'Rug', 'سجادة', **ROW),
        lab([55, 102, 176, 114], '炎属性ダウンⅡ', 'Fire Resist Down II', 'خفض مقاومة النار II', **ROW),
        lab([66, 132, 176, 144], 'スロット４', 'Slot 4', 'الخانة 4', **ROW),
        lab([55, 144, 176, 156], 'アタッチパーツなし', 'No Attachments', 'بلا ملحقات', **ROW),
        lab([457, 211, 508, 224], 'リセット', 'Reset', 'إعادة ضبط', **ROW),
        lab([462, 230, 508, 243], 'ズーム', 'Zoom', 'تكبير', **ROW),
    ])

# ------------------------------------------------------------------------------------------------ 6013_0002
specs['ui_tut_6013_0002'] = dict(
    texture='ui_tut_6013_0002.aif', archive='base',
    note='Attachment making, three panels side by side: Special Ability list (Power II, EXP Boost I, Light Resist '
         'Down I, Power II), Cores list (Darker Core), Attachments list (Alva Edge, Aim greyed) under the chosen core '
         'card (Darker Core / Power II); three sort tabs Standard; red callouts with white outline at the bottom (red '
         'y 231-248, left-aligned at each panel: Select Ability / Select Core / Select Shape, wording after help '
         '780091; boxes widened over the stone floor to the panel width). Sheet 10317, 21613, 20505, 150002, '
         '150136, 150178, 110001, 130002, 130187, 10701. '
         'Written by dev/psnova/uitex/specwork/make_spec_tut_6010_6013.py.',
    labels=[
        lab([20, 47, 150, 59], '特殊能力', 'Special Ability', 'قدرة خاصة', align='center'),
        *ar_taller(lab([193, 47, 322, 59], 'コア', 'Cores', 'الأنوية', align='center'), [193, 46, 322, 60]),
        lab([358, 47, 487, 59], 'アタッチパーツ', 'Attachments', 'الملحقات', align='center'),
        *rows(20, 162, [63, 77, 91, 105], [
            ('パワーⅡ', 'Power II', 'القوة II'),
            ('ＥＸＰブーストⅠ', 'EXP Boost I', 'تعزيز EXP I'),
            ('光属性ダウンⅠ', 'Light Resist Down I', 'خفض مقاومة الضوء I'),
            ('パワーⅡ', 'Power II', 'القوة II'),
        ]),
        *rows(191, 334, [63], [('ダーカー・コア', 'Darker Core', 'نواة داركر')]),
        lab([401, 6, 503, 18], 'ダーカー・コア', 'Darker Core', 'نواة داركر', **ROW),
        lab([391, 18, 503, 30], 'パワーⅡ', 'Power II', 'القوة II', **ROW),
        *rows(361, 503, [63, 77], [
            ('アルバエッジ', 'Alva Edge', 'حافة ألبا'),
            ('エイム', 'Aim', 'تصويب', {'color': GREY}),
        ]),
        lab([14, 203, 102, 214], '標準ソート', 'Standard', 'الترتيب الافتراضي', align='center', size_en=9, size_ar=8),
        lab([186, 203, 274, 214], '標準ソート', 'Standard', 'الترتيب الافتراضي', align='center', size_en=9, size_ar=8),
        lab([355, 203, 443, 214], '標準ソート', 'Standard', 'الترتيب الافتراضي', align='center', size_en=9, size_ar=8),
        lab([4, 227, 166, 252], '特殊能力選択', 'Select Ability', 'اختيار القدرة', **RED),
        lab([176, 227, 338, 252], 'コア選択', 'Select Core', 'اختيار النواة', **RED),
        lab([344, 227, 508, 252], '形状選択', 'Select Shape', 'اختيار الشكل', **RED),
    ])


def write(name, spec):
    p = os.path.join(OUT, name + '.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    print(p, len(spec['labels']), 'labels')


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for n, s in specs.items():
        write(n, s)
