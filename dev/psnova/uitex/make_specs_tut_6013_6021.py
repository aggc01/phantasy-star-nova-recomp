"""make_specs_tut_6013_6021.py - write the redraw specs (SPEC.md format) of ten tutorial pictures:
ui_tut_6013_0003, 6014_0001, 6015_0001/0002/0003, 6016_0001, 6017_0001, 6018_0001, 6021_0001/0002 (2026-11-19).

Boxes were read from the rendered PNGs (tut_detect.py + zoomed crops); wording from the text sheet
(dump/psnova-l10n/sheet/psnova_text_v5.tsv, ids in the notes) where the same Japanese exists, otherwise written in the
same style (pre-release item/costume names that the final game renamed). Labels of one kind on one picture share a
group: the group gets one font size per language = the largest that fits every label of the group (capped), so a list
does not change size from row to row. Sizes are measured with apply_spec.py's own font/measure code.

usage: make_specs_tut_6013_6021.py [--check]   (--check also prints border warnings)
"""
import json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
import apply_spec as A  # noqa: E402

OUT = os.path.join(ROOT, 'dump', 'psnova-l10n', 'uitex', 'specs')
PNG = os.path.join(ROOT, 'dump', 'psnova-l10n', 'scratch', 'research', 'uitex', 'png', 'base')

WHITE = [240, 240, 240]
CYAN = [0, 230, 230]
GREEN = [0, 240, 0]
RED = [240, 16, 16]

# style presets: (keys) ; 'cap' = largest size per language
ST = {
    'row':  dict(color=WHITE, align='left', cap=(12, 12)),
    'rowc': dict(color=CYAN, align='left', cap=(12, 12)),
    'rowg': dict(color=GREEN, align='left', cap=(12, 12)),
    'hdr':  dict(color=WHITE, align='center', cap=(12, 12)),
    'desc': dict(color=WHITE, align='left', valign='top', cap=(11, 11)),
    'call': dict(color=RED, outline=[255, 255, 255], outline_px=1, align='center', cap=(16, 16)),
    'call2': dict(color=RED, outline=[255, 255, 255], outline_px=2, align='center', cap=(24, 24)),
    'big':  dict(color=WHITE, outline=[8, 8, 8], outline_px=1, align='left', cap=(22, 22)),   # 2x: dark outline as the original
    'bigd': dict(color=WHITE, outline=[8, 8, 8], outline_px=1, align='left', valign='top', cap=(20, 20)),
    'erase': dict(color=WHITE, align='left', cap=(12, 12)),
}

# common words (sheet ids): ja -> (en, ar)
W = {
    'レアリティ': ('Rarity', 'الندرة'),                     # 10314
    '標準ソート': ('Standard', 'الترتيب الافتراضي'),        # 10701
    '所持数': ('Owned', 'المتوفر'),                          # 21617
    'バック容量': ('Item Pack', 'سعة الحقيبة'),             # 21618 パック容量 (the screenshot shows バック)
    '倉庫容量': ('Storage', 'سعة المخزن'),                  # 21510
    '必要素材': ('Materials Needed', 'المواد المطلوبة'),     # 21615
    '必要個数': ('Needed', 'المطلوب'),                      # 21616
    '打撃力': ('S-ATK', 'قوة الضرب'), '射撃力': ('R-ATK', 'قوة الرمي'), '法撃力': ('T-ATK', 'قوة التقنية'),
    '技量': ('DEX', 'البراعة'),
    '打撃防御': ('S-DEF', 'دفاع الضرب'), '射撃防御': ('R-DEF', 'دفاع الرمي'), '法撃防御': ('T-DEF', 'دفاع التقنية'),
    # 10334-10339: the stat list says "Resist" after the element icon (Arabic likewise without the element, to fit)
    '炎耐性': ('Resist', 'مقاومة'), '氷耐性': ('Resist', 'مقاومة'), '雷耐性': ('Resist', 'مقاومة'),
    '風耐性': ('Resist', 'مقاومة'), '光耐性': ('Resist', 'مقاومة'), '闇耐性': ('Resist', 'مقاومة'),
    'フラットテック': ('Flat Tech', 'تقنية مسطحة'),          # 310027
    'ダーカー・コア': ('Darker Core', 'نواة داركر'),         # 110001
    '白い岩石': ('White Rock', 'صخر أبيض'),                  # 350048
    'テクニックⅡ': ('Tech II', 'تقنية II'),                  # 150012
    'フレイムⅠ': ('Flame I', 'لهب I'),                       # 150069
    '炎ジェムⅠ': ('Fire Gem I', 'جوهرة نار I'),              # 130205
    'ソード': ('Sword', 'سيف'),                              # 10801
    'パルチザン': ('Partisan', 'رمح'),                       # 10802 (Partisan as in the glossary)
    'モノメイト': ('Monomate', 'مونوميت'),                   # 370001
    'スケープドール': ('Scape Doll', 'دمية الإنقاذ'),        # 24102
}

STATS = ['打撃力', '射撃力', '法撃力', '技量', '打撃防御', '射撃防御', '法撃防御',
         '炎耐性', '氷耐性', '雷耐性', '風耐性', '光耐性', '闇耐性']

DESC_FLAT = ('法撃への防御に特化した\n遠距離戦向けの標準シールドユニット。\n初心者向けに調整された汎用品。',
             # 320027 (sheet EN drops the first clause; kept here, it is what the picture is about)
             'Specialized in T-DEF. A standard\nShield Unit for long-range combat,\nfine-tuned for beginners.',
             'مخصصة لدفاع التقنية. وحدة درع\nقياسية للقتال من بعيد، معدّلة\nلتناسب المبتدئين.')
DESC_CORE = ('毒された強き生命力の源。\n貪欲に他者を攻撃し生き延びようと\nあらゆる進化の可能性を秘める。',
             'Source of tainted, powerful vitality.\nGreedily attacking others to survive,\nit holds every possibility of evolution.',
             'مصدر حيوية قوية مسمومة.\nتهاجم الآخرين بجشع لتبقى حية،\nوتخفي كل إمكانيات التطور.')   # 120001


def L(g, box, jp, en=None, ar=None, **kw):
    if en is None:
        en, ar = W[jp]
    d = dict(g=g, box=list(box), jp=jp, en=en, ar=ar)
    d.update(kw)
    return d


def rows(g, x0, x1, y_first, jps, pitch=16, sel=None, **kw):
    """List rows: text tops y_first + k*pitch; box = 2 px above the text top to 9 px below (inside the row frame);
    the selected row (`sel`) starts 1 px lower (its yellow frame line)."""
    out = []
    for k, item in enumerate(jps):
        jp, en, ar = item if isinstance(item, tuple) else (item, None, None)
        y = y_first + k * pitch
        out.append(L(g, (x0, y - 2 + (k == sel), x1, y + 9), jp, en, ar, **kw))
    return out


def stats(g, ys, x1):
    out = []
    for jp, y in zip(STATS, ys):
        x0 = 200 if '耐性' in jp else 188          # resist rows: the element icon sits at x188-198
        out.append(L(g, (x0, y - 1, x1, y + 9), jp))
    return out


def table(gh, gr, names):
    out = [L(gh, (292, 162, 412, 175), '必要素材'),
           L(gh + 'c', (417, 162, 458, 175), '必要個数'),
           L(gh + 'c', (460, 162, 502, 175), '所持数')]
    for k, item in enumerate(names):
        jp, en, ar = item if isinstance(item, tuple) else (item, None, None)
        out.append(L(gr, (304, 176 + 12 * k, 412, 189 + 12 * k), jp, en, ar))
    return out


SPECS = {}

# ---------------------------------------------------------------------------------------------- 6013_0003
SPECS['ui_tut_6013_0003'] = dict(
    note='Weapon attachment screen (attach parts list, Fire Gem I selected) with red callouts naming the six element '
         'icons of the weapon panel (炎 氷 雷 風 光 闇, red with white outline). Two half-hidden item names under the '
         'callouts (炎ジェムⅠ, フレイムⅠ cut off at the top) are only erased. Callouts share one size (Lightning is the '
         'widest). Sheet: 130205 Fire Gem I, 150069 Flame I, 20505 Attachments, 1300xx Edge/Alva.../Gran Blade D, '
         '10701 Standard, 10314 Rarity, 10801 Sword. The description is a pre-release text (not in the sheet).',
    labels=[
        L('tl', (65, 5, 172, 15), '炎ジェムⅠ'),
        L('tl', (55, 17, 172, 29), 'フレイムⅠ'),
        L('hdr', (20, 48, 170, 62), 'アタッチパーツ', 'Attachments', 'الملحقات', style='hdr'),
        *rows('row', 19, 176, 66, [('エッジ', 'Edge', 'حافة'), ('アルバエッジ', 'Alva Edge', 'حافة ألبا'),
                                    ('ネイル', 'Nail', 'ظفر'), ('アルバネイル', 'Alva Nail', 'ظفر ألبا'),
                                    ('ピック', 'Pick', 'معول'), ('アルバピック', 'Alva Pick', 'معول ألبا'),
                                    ('グランブレードＤ', 'Gran Blade D', 'نصل غران D'), '炎ジェムⅠ']),
        L('sort', (25, 220, 105, 234), '標準ソート', style='hdr'),
        L('title', (304, 3, 470, 15), '炎ジェムⅠ'),
        L('sub', (383, 44, 500, 57), 'フレイムⅠ', style='hdr'),
        L('rar', (293, 60, 340, 72), 'レアリティ'),
        L('desc', (292, 73, 500, 117), '炎の属性を付けるアタッチパーツ。\n宝石形状の基礎的なモデル。',
          'An attachment part that adds Fire.\nA basic gem-shaped model.',
          'قطعة إلحاق تضيف عنصر النار.\nنموذج أساسي على شكل جوهرة.', style='desc'),
        L('title2', (305, 131, 470, 143), 'ソード'),
        L('erase', (295, 200, 337, 208), '炎ジェムⅠ (cut off)', '', '', style='erase'),
        L('erase', (417, 200, 452, 208), 'フレイムⅠ (cut off)', '', '', style='erase'),
        L('call', (288, 207, 320, 228), '炎', 'Fire', 'نار', style='call'),
        L('call', (321, 207, 353, 228), '氷', 'Ice', 'جليد', style='call'),
        L('call', (354, 207, 389, 228), '雷', 'Lightning', 'برق', style='call'),
        L('call', (390, 207, 422, 228), '風', 'Wind', 'رياح', style='call'),
        L('call', (423, 207, 457, 228), '光', 'Light', 'ضوء', style='call'),
        L('call', (458, 207, 491, 228), '闇', 'Dark', 'ظلام', style='call'),
    ])

# ---------------------------------------------------------------------------------------------- 6014_0001
SPECS['ui_tut_6014_0001'] = dict(
    note='Weapon preview with four attach-part panels (part name + ability) and the button guide (SELECT Reset, L/R '
         'Zoom) over the 3D view. Sheet: 130051/130049 Gran Blade F/D, 150051/150049 Mind III/I, 130129 Rug, '
         '150159 style "Fire Resist Down II" (the picture says 火属性ダウンⅡ), 150069 Flame I; フォイエジェム is the '
         'pre-release name of the fire gem (Foie Gem). Reset/Zoom as in the button guide spec.',
    labels=[
        L('ptitle', (64, 4, 175, 15), 'グランブレードＦ', 'Gran Blade F', 'نصل غران F'),
        L('pabil', (54, 17, 175, 29), 'マインドⅢ', 'Mind III', 'عقل III'),
        L('ptitle', (64, 46, 175, 58), 'グランブレードＤ', 'Gran Blade D', 'نصل غران D'),
        L('pabil', (54, 59, 175, 71), 'マインドⅠ', 'Mind I', 'عقل I'),
        L('ptitle', (64, 89, 175, 101), 'ラグ', 'Rug', 'سجادة'),
        L('pabil', (54, 102, 175, 114), '火属性ダウンⅡ', 'Fire Resist Down II', 'خفض مقاومة النار II'),
        L('ptitle', (64, 133, 175, 144), 'フォイエジェム', 'Foie Gem', 'جوهرة فوي'),
        L('pabil', (54, 144, 175, 156), 'フレイムⅠ'),
        L('btn', (455, 211, 510, 225), 'リセット', 'Reset', 'إعادة ضبط'),
        L('btn', (459, 229, 510, 243), 'ズーム', 'Zoom', 'تكبير'),
    ])

# ---------------------------------------------------------------------------------------------- 6015_0001
SPECS['ui_tut_6015_0001'] = dict(
    note='Shield unit crafting: Flat Tech selected, stat preview column, materials table. Sheet: 20503 Shields, '
         '310027 Flat Tech, 10307-10313 stat names, 10334-10339 Resist (the element icon names the element), 21617 '
         'Owned, 21618 Item Pack (パック容量), 21615/21616 Materials Needed/Needed, 110001 Darker Core, 350048 White '
         'Rock, 10701 Standard. Description 320027 (EN keeps the T-DEF clause the sheet line drops).',
    labels=[
        L('cap', (291, 19, 348, 31), '所持数'),
        L('cap', (401, 19, 450, 31), 'バック容量'),
        L('hdr', (20, 32, 170, 44), 'シールドユニット', 'Shields', 'الدروع', style='hdr'),
        L('row', (19, 48, 176, 58), 'フラットテック'),
        *stats('stat', [75, 86, 98, 110, 122, 133, 145, 157, 169, 181, 192, 204, 216], 239),
        L('title', (304, 36, 470, 50), 'フラットテック'),
        L('desc', (292, 107, 500, 150), *DESC_FLAT, style='desc'),
        *table('th', 'tr', ['ダーカー・コア', '白い岩石']),
        L('sort', (25, 204, 105, 217), '標準ソート', style='hdr'),
    ])

# ---------------------------------------------------------------------------------------------- 6015_0002
SPECS['ui_tut_6015_0002'] = dict(
    note='Attaching a Darker Core to the Flat Tech shield: cores list, stat preview, core panel and shield panel. '
         'Sheet: 310027 Flat Tech, 21613 Cores, 110001 Darker Core (+ description 120001 EN/AR), 150012 Tech II, '
         '10314 Rarity, stats 10307-10313, Resist 10334-10339, description 320027, 10701 Standard.',
    labels=[
        L('tl', (66, 5, 172, 15), 'フラットテック'),
        L('hdr', (20, 48, 170, 62), 'コア', 'Cores', 'الأنوية', style='hdr'),
        *rows('row', 19, 176, 66, ['ダーカー・コア'] * 3),
        *stats('stat', [91, 103, 115, 126, 138, 150, 162, 173, 185, 197, 209, 220, 232], 236),
        L('title', (304, 3, 470, 16), 'ダーカー・コア'),
        L('sub', (386, 44, 500, 58), 'テクニックⅡ', style='hdr'),
        L('rar', (293, 60, 340, 72), 'レアリティ'),
        L('desc', (292, 72, 500, 117), *DESC_CORE, style='desc'),
        L('title', (304, 130, 470, 144), 'フラットテック'),
        L('sub', (386, 172, 500, 186), 'テクニックⅡ', style='hdr'),
        L('desc', (292, 201, 500, 245), *DESC_FLAT, style='desc'),
        L('sort', (25, 220, 105, 234), '標準ソート', style='hdr'),
    ])

# ---------------------------------------------------------------------------------------------- 6015_0003
SPECS['ui_tut_6015_0003'] = dict(
    note='Zoomed (about 2x) Flat Tech panel: red callouts (white 2 px outline) name the three defence values '
         '(S-DEF / R-DEF / T-DEF, sheet 10311-10313). The materials table header at the bottom edge is cut in half '
         'by the picture edge: drawn at the description size, valign top, so the box (the picture edge) cuts the '
         'English the same way. Description 320027.',
    labels=[
        L('btitle', (121, 9, 450, 29), 'フラットテック', style='big'),
        L('call2', (196, 69, 276, 91), '打撃防御', style='call2'),
        L('call2', (278, 69, 358, 91), '射撃防御', style='call2'),
        L('call2', (360, 69, 440, 91), '法撃防御', style='call2'),
        L('bdesc', (102, 138, 492, 198), *DESC_FLAT, style='bigd'),
        L('bcut', (102, 244, 250, 256), '必要素材 (cut off)', *W['必要素材'], style='bigd', fixed='bdesc'),
        L('bcut', (337, 244, 410, 256), '必要個数 (cut off)', *W['必要個数'], style='bigd', align='center',
          fixed='bdesc'),
        L('bcut', (425, 244, 485, 256), '所持数 (cut off)', *W['所持数'], style='bigd', align='center',
          fixed='bdesc'),
    ])

# ---------------------------------------------------------------------------------------------- 6016_0001
SPECS['ui_tut_6016_0001'] = dict(
    note='Item crafting: recovery items list, Monomate panel, materials table. Sheet: 21617 Owned, 21618 Item Pack, '
         '11002 Items, 370001-370005 Monomate/Dimate/Sol Atomizer/Moon Atomizer, 24102 Scape Doll, 10314 Rarity, '
         '380001 description (EN re-broken, AR new), 21615/21616, 350001 Gran Piece, 10701 Standard.',
    labels=[
        L('cap', (291, 19, 348, 31), '所持数'),
        L('cap', (401, 19, 450, 31), 'バック容量'),
        L('hdr', (20, 32, 170, 44), 'アイテム', 'Items', 'الأغراض', style='hdr'),
        *rows('row', 19, 176, 49, sel=0, jps=['モノメイト', ('ディメイト', 'Dimate', 'ديميت'),
                                    ('ソルアトマイザー', 'Sol Atomizer', 'مرذاذ الشمس'),
                                    ('ムーンアトマイザー', 'Moon Atomizer', 'مرذاذ القمر'), 'スケープドール']),
        L('title', (304, 37, 470, 49), 'モノメイト'),
        L('rar', (293, 93, 340, 105), 'レアリティ'),
        L('desc', (292, 107, 500, 150), 'アークス御用達の回復剤。\n使用することでＨＰが回復する。',
          'Recovery item provided by ARKS.\nRestores HP when used.',
          'دواء استشفاء تزوّده آركس.\nيستعيد HP عند استخدامه.', style='desc'),
        *table('th', 'tr', [('グランピース', 'Gran Piece', 'قطعة غران')]),
        L('sort', (25, 204, 105, 217), '標準ソート', style='hdr'),
    ])

# ---------------------------------------------------------------------------------------------- 6017_0001
SPECS['ui_tut_6017_0001'] = dict(
    note='Costume crafting: costume list, Heavy Scudo B panel (race/sex, colour), materials table. Sheet: 21617 '
         'Owned, 21510 Storage, 20504 Costumes, 330003 Heavy Scudo B, 3300xx costume names (the picture shows '
         'pre-release names without 破: same words without "(Damaged)"), 330039/330040 Jan Du, 330043 Slight Suit, '
         '10315/10316 Race/Sex, 10404 Non-Cast + 22411 Arabic, 22408 Color, 340003 description, G-Dagan from 350143; '
         '黒い足 / ヴァイセクルーン are pre-release names (translated). Race (Sex) instead of Race (Gender) to fit.',
    labels=[
        L('cap', (291, 19, 348, 31), '所持数'),
        L('cap', (401, 19, 450, 31), '倉庫容量'),
        L('hdr', (20, 32, 170, 44), 'コスチューム', 'Costumes', 'الأزياء', style='hdr'),
        *rows('row', 19, 176, 49, sel=0, jps=[
            ('ヘヴィスクードＢ', 'Heavy Scudo B', 'سكودو ثقيل B'),
            ('アドヴェントスＷ', 'Adventos W', 'أدفنتوس W'),
            ('クローズクォーターＯ', 'Close Quarter O', 'كلوز كوارتر O'),
            ('シャープオーダーＶ', 'Sharp Order V', 'ترتيب حاد V'),
            ('ブリッツエースＷ', 'Blitz Ace W', 'بليتز ماهر W'),
            ('センシアスコートＫ', 'Sensuous Coat K', 'معطف سنسيوس K'),
            ('レーベンシルトＢ', 'Raven Schild B', 'رايفن شيلد B'),
            ('ヴァイセクルーンＷ', 'Weisse Croon W', 'فايسه كرون W'),
            ('ジャン・ドゥＫ', 'Jan Du K', 'جان دو K'),
            ('スライトスーツＲ', 'Slight Suit R', 'بدلة سلايت R')]),
        L('title', (304, 37, 470, 49), 'ヘヴィスクードＢ', 'Heavy Scudo B', 'سكودو ثقيل B'),
        L('info1', (344, 52, 392, 65), '種族(性別)', 'Race (Sex)', 'العرق (الجنس)'),
        L('info', (398, 52, 503, 65), 'キャスト以外(男性)', 'Non-Cast (Male)', 'غير كاست (ذكر)'),
        L('info', (344, 66, 392, 78), 'カラー', 'Color', 'اللون'),
        L('rar', (293, 93, 340, 105), 'レアリティ'),
        L('desc', (292, 107, 500, 150), '戦闘用に作られたアークスの服装。\n衝撃吸収用のアブソーバーが各所に\n取り付けられており、安定性が高い。',
          'ARKS combat attire. Shock-absorbing\nabsorbers are fitted all over, making\nit highly stable.',
          'زي قتالي لأفراد آركس. تُثبَّت في أجزائه\nماصّات للصدمات، مما يمنحه ثباتًا عاليًا.', style='desc'),
        *table('th', 'tr', [('黒い足', 'Black Leg', 'ساق سوداء'), ('Ｇダガンの脚', 'G-Dagan Leg', 'ساق G-داغان')]),
        L('sort', (25, 204, 105, 217), '標準ソート', style='hdr'),
    ])

# ---------------------------------------------------------------------------------------------- 6018_0001
SPECS['ui_tut_6018_0001'] = dict(
    note='Character edit, makeup pattern grid. Sheet: 500010 Edit Face and Hair, 500021 Select Makeup Pattern 1, '
         '440246 Tattoo.',
    labels=[
        L('top', (10, 4, 176, 18), '顔と髪を編集', 'Edit Face and Hair', 'تحرير الوجه والشعر'),
        L('hdr', (15, 24, 173, 36), 'メイクパターン１選択', 'Select Makeup Pattern 1', 'اختيار نمط المكياج 1', style='hdr'),
        L('row', (21, 219, 90, 233), 'タトゥー', 'Tattoo', 'وشم'),
    ])

# ---------------------------------------------------------------------------------------------- 6021_0001
SPECS['ui_tut_6021_0001'] = dict(
    note='Item pack, All tab: weapons in cyan (new), new materials in green, counts at the right edge (kept). '
         'Sheet: 21618 Item Pack, 20501 All, 10801 Sword, 10802 Partisan, 370001 Monomate, 350049 Dendritic '
         'Material, 350048 White Rock, 24102 Scape Doll, 350047 Memory Fragment A, 10701 Standard; 黒い鱗皮, '
         'ラウーダンの爪 and 小さなたまご are pre-release names (from 350563 Scaly Hide, 350169 Ra Oodan Claw, '
         '350011 Egg wording).',
    labels=[
        L('cap', (401, 19, 450, 31), 'バック容量'),
        L('hdr', (20, 32, 170, 44), 'すべて', 'All', 'الكل', style='hdr'),
        *rows('row', 19, 176, 49, ['ソード', 'パルチザン'], sel=0, style='rowc'),
        *rows('row', 19, 157, 81, ['モノメイト', ('樹木状の鉱物', 'Dendritic Material', 'مادة معدنية شجرية'),
                                    '白い岩石', 'スケープドール']),
        *rows('row', 19, 157, 145, [('メモリーフラグメントＡ', 'Memory Fragment A', 'شظية ذاكرة A'),
                                     ('黒い鱗皮', 'Black Scaly Hide', 'جلد حرشفي أسود'),
                                     ('ラウーダンの爪', 'Ra Oodan Claw', 'مخلب را أودان'),
                                     ('小さなたまご', 'Small Egg', 'بيضة صغيرة')], style='rowg'),
        L('title', (304, 37, 470, 49), 'ソード'),
        L('sort', (25, 204, 105, 217), '標準ソート', style='hdr'),
    ])

# ---------------------------------------------------------------------------------------------- 6021_0002
def bar_rows(name, x0, x1, y0, y1, xs, jp):
    """The zoomed storage buttons are horizontally uniform bars with a vertical gradient: refill every row of the text
    band with that row's colour taken at column xs (right of the text), one 1-px 'fill' label per row (no text)."""
    a = np.array(Image.open(os.path.join(PNG, name + '.png')).convert('RGBA'))
    return [L('erase', (x0, y, x1, y + 1), '(bar row under %s)' % jp, '', '', style='erase', clear='fill',
              fill_color=[int(v) for v in a[y, xs]]) for y in range(y0, y1)]


SPECS['ui_tut_6021_0002'] = dict(
    note='Zoomed (about 2x) storage menu: Storage capacity label and the three storage commands. Sheet: 21510 '
         'Storage, 21501 / 21502 / 21503 (the fan English names the action: Send to Storage / Withdraw From '
         'Storage / Open Temp Storage, as the game menu shows them). The command bars are horizontally uniform with a '
         'vertical gradient (and a yellow frame on the selected one): inpainting pulled the frame colour in, so the '
         'Japanese is removed by 1-px "fill" rows with the colour of each bar row at x450 (labels with jp "(bar row '
         'under ...)" and no text), then the English/Arabic is drawn with clear "keep". The two line ends of a cut-off '
         'description at the left edge (回復剤。 / が回復する。) are erased with the flat panel colour.',
    labels=[
        L('bcap', (50, 39, 135, 58), '倉庫容量', style='big'),
        *bar_rows('ui_tut_6021_0002', 272, 446, 55, 76, 450, 'アイテムパックを開く'),
        *bar_rows('ui_tut_6021_0002', 272, 446, 85, 106, 450, '通常倉庫を開く'),
        *bar_rows('ui_tut_6021_0002', 272, 446, 115, 136, 450, '一時倉庫を開く'),
        L('bbtn', (272, 55, 494, 76), 'アイテムパックを開く', 'Send to Storage', 'فتح حقيبة الأغراض', style='big',
          clear='keep'),
        L('bbtn', (272, 85, 494, 106), '通常倉庫を開く', 'Withdraw From Storage', 'فتح المخزن العادي', style='big',
          clear='keep'),
        L('bbtn', (272, 115, 494, 136), '一時倉庫を開く', 'Open Temp Storage', 'فتح المخزن المؤقت', style='big',
          clear='keep'),
        L('erase', (0, 203, 36, 222), '(回)復剤。 (cut off)', '', '', style='erase', clear='fill',
          fill_color=[24, 36, 49, 255]),
        L('erase', (0, 222, 84, 242), '(HP)が回復する。 (cut off)', '', '', style='erase', clear='fill',
          fill_color=[24, 36, 49, 255]),
    ])

GROUP_STYLE_DEFAULT = 'row'
# the Japanese has a dark shadow/outline around light strokes: 'any' polarity with a lower threshold and a 2 px
# dilation removes both (tried on 6015_0003: the default 'bright' mask left grey ghosts of the shadows and red/white
# remains of the callouts; a whole-box mask left a visible lighter block on the textured panel)
INPAINT = {'inpaint_polarity': 'any', 'inpaint_threshold': 25, 'inpaint_dilate': 2}
# ...but only over flat panels and the zoomed pictures: on the 1x list rows / title bars (vertical gradients, frame
# lines 1 px outside the box) a 2 px dilation is refilled from the frame lines and leaves dark or coloured smears;
# there 'any' with a 1 px dilation was the cleanest of default / any-d1 / any-d1-t15 / any-d2-r5 (crops/exp/rows_cmp)
INPAINT_ROWS = {'inpaint_polarity': 'any', 'inpaint_threshold': 20, 'inpaint_dilate': 1}
INPAINT_STYLES = ('call', 'call2', 'big', 'bigd', 'desc', 'erase')


def fit_size(lab, lang, s_max):
    """Largest size <= s_max at which the label's text fits its box (apply_spec rules)."""
    text = lab[lang]
    if not text:
        return None
    x0, y0, x1, y1 = lab['box']
    bw, bh = x1 - x0, y1 - y0
    stroke = lab.get('outline_px', 0) if lab.get('outline') else 0
    lines = A._lines(text, lang)
    for s in range(s_max, 5, -1):
        w, h, _ = A._measure(lines, A.font_for(lang, s), stroke, lab.get('line_gap', 0))
        if w <= bw - 2 * lab.get('pad', 1) and h <= bh:
            return s
    return 6


def build():
    report = {}
    for name, sp in SPECS.items():
        labs = []
        for raw in sp['labels']:
            st = dict(ST[raw.get('style', GROUP_STYLE_DEFAULT)])
            cap = st.pop('cap')
            lab = {'box': raw['box'], 'jp': raw['jp'], 'en': raw['en'], 'ar': raw['ar'], 'clear': 'inpaint'}
            lab.update(INPAINT if raw.get('style', GROUP_STYLE_DEFAULT) in INPAINT_STYLES else INPAINT_ROWS)
            lab.update({'align': 'left', 'color': WHITE, 'outline': None, 'outline_px': 0, 'size': None,
                        'valign': 'center'})
            lab.update(st)
            for k in ('align', 'valign', 'color', 'clear', 'fill_color'):
                if k in raw:
                    lab[k] = raw[k]
            if lab['clear'] != 'inpaint':
                for k in list(lab):
                    if k.startswith('inpaint_'):
                        del lab[k]
            lab['_g'] = raw['g']; lab['_cap'] = cap; lab['_fixed'] = raw.get('fixed')
            labs.append(lab)
        # group sizes
        sizes = {}
        for lang_i, lang in enumerate(('en', 'ar')):
            for g in {l['_g'] for l in labs}:
                ss = [fit_size(l, lang, l['_cap'][lang_i]) for l in labs if l['_g'] == g]
                ss = [s for s in ss if s]
                sizes[(g, lang)] = min(ss) if ss else None
        for l in labs:
            g = l['_fixed'] or l['_g']
            l['size'] = sizes.get((g, 'en'))
            l['size_ar'] = sizes.get((g, 'ar'))
            if not l['en']:
                l['size'] = None
            if not l['ar']:
                l['size_ar'] = None
        out = []
        for l in labs:
            d = {k: l[k] for k in ('box', 'jp', 'en', 'ar', 'clear', 'align', 'color', 'outline', 'outline_px',
                                   'size', 'valign')}
            if 'fill_color' in l:
                d['fill_color'] = l['fill_color']
            if l['outline'] is None:
                d['outline'] = None; d['outline_px'] = 0
            if l['size_ar'] is not None:
                d['size_ar'] = l['size_ar']
            for k in ('inpaint_polarity', 'inpaint_threshold', 'inpaint_dilate'):
                if k in l:
                    d[k] = l[k]
            out.append(d)
        spec = {'texture': name + '.aif', 'archive': 'base', 'note': sp['note'], 'labels': out}
        with open(os.path.join(OUT, name + '.json'), 'w', encoding='utf-8') as f:
            json.dump(spec, f, ensure_ascii=False, indent=1)
        report[name] = (len(out), sum(1 for d in out if d['en']), sizes)
        if '-v' in sys.argv:
            for l in labs:
                for i, lang in enumerate(('en', 'ar')):
                    f = fit_size(l, lang, l['_cap'][i])
                    gs = sizes.get((l['_fixed'] or l['_g'], lang))
                    if f and gs and f > gs:
                        pass
                    if f and f <= 8:
                        print('   small: %s %s %s %s fit %s' % (name, lang, l['jp'][:10], l[lang][:20], f))
    return report


def check():
    """Warn when a box holds a bright horizontal line (a frame border would be inpainted away)."""
    for name, sp in SPECS.items():
        a = np.array(Image.open(os.path.join(PNG, name + '.png')).convert('RGB')).astype(int)
        lum = a.sum(2) // 3
        for raw in sp['labels']:
            x0, y0, x1, y1 = raw['box']
            sub = lum[y0:y1, x0:x1]
            frac = (sub > 110).mean(1)
            bad = [y0 + i for i, f in enumerate(frac) if f > 0.6]
            col = (lum[y0:y1, x0:x1] > 110).mean(0)
            badc = [x0 + i for i, f in enumerate(col) if f > 0.85]
            if bad or badc:
                print('  %s %-12s box %s: bright rows %s cols %s' % (name, raw['jp'][:10], raw['box'], bad, badc))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    rep = build()
    for n, (cnt, en, sizes) in rep.items():
        print(n, cnt, 'labels', ' '.join('%s/%s=%s' % (g, l, s) for (g, l), s in sorted(sizes.items())))
    if '--check' in sys.argv:
        check()
