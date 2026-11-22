"""Write the specs of nova_ui_title.aif (title screen katakana) and ev_dlc_104.aif (DLC cast card), 2026-11-19.
Boxes measured from the rendered PNGs (alpha / brightness bounds of the Japanese, plus a small margin)."""
import json, os
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
SPECS = os.path.join(ROOT, 'dump', 'psnova-l10n', 'uitex', 'specs')

# ------------------------------------------------------------------ nova_ui_title.aif (base, 2048x2048 DXT3)
# Two copies of the same small katakana line on a transparent sheet: a thin black one (x949-1155, y721-736) and,
# 231 px to the right, a white bold rounded one that is the same text dilated by ~2.5 px (x1178-1389, y719-738):
# a halo layer drawn under the black line. Both are redrawn with the same size and centring so they stay registered.
EN, AR = 'Phantasy Star Nova', 'فانتاسي ستار نوفا'
title = {
    'texture': 'nova_ui_title.aif',
    'archive': 'base',
    'note': ('Title screen sheet (base only, 2048x2048 DXT3, ID 02ad07). The small katakana ファンタシースター ノヴァ exists '
             'twice: a thin black line (x949-1155, y721-736) and, 231 px to the right, a white halo copy (the same text '
             'dilated ~2.5 px, x1178-1389, y719-738) that the title screen layers under the black one. Both boxes have '
             'the same width (216) and the same fixed size and centring so the redrawn halo stays registered with the '
             'black text (offset 231 px); halo = white text with a 2 px white outline. The TM mark (x1425-1447) and the '
             'English menu words stay. Transparent sheet: clear = transparent.'),
    'labels': [
        {'box': [945, 716, 1161, 742], 'jp': 'ファンタシースター ノヴァ (black line)', 'en': EN, 'ar': AR,
         'clear': 'transparent', 'align': 'center', 'color': [0, 0, 0], 'outline': None, 'outline_px': 0,
         'size': 20, 'size_ar': 17, 'valign': 'center'},
        {'box': [1176, 716, 1392, 742], 'jp': 'ファンタシースター ノヴァ (white halo copy)', 'en': EN, 'ar': AR,
         'clear': 'transparent', 'align': 'center', 'color': [255, 255, 255], 'outline': [255, 255, 255],
         'outline_px': 2, 'size': 20, 'size_ar': 17, 'valign': 'center'},
    ],
}

# ------------------------------------------------------------------ ev_dlc_104.aif (update, 1024x1024 DXT1)
# Opaque black card; five rows: character name right-aligned (ends x456), voice actor left-aligned (starts x503/504).
ROWS = [  # (y0, y1, jp char, en char, ar char, jp actor, en actor, ar actor)
    (143, 174, 'ガーネット', 'Garnet', 'غارنت', 'ゆかな', 'Yukana', 'يوكانا'),
    (193, 223, 'サンシャウト', 'Sunshout', 'سانشاوت', '前野 智昭', 'Tomoaki Maeno', 'توموأكي ماينو'),
    (241, 272, 'グラバー', 'Glover', 'غلوفر', '木内 秀信', 'Hidenobu Kiuchi', 'هيدينوبو كيوتشي'),
    (290, 321, 'コウエン', 'Cohen', 'كوين', '小松 由佳', 'Yuka Komatsu', 'يوكا كوماتسو'),
    (339, 370, 'ズック', 'Zukku', 'زوك', '阪口 大助', 'Daisuke Sakaguchi', 'دايسوكي ساكاغوتشي'),
]
LEFT, RIGHT = [240, 460], [500, 780]      # name column (right-aligned to 456) and actor column (from 504)
labels = []
for y0, y1, jc, ec, ac, ja, ea, aa in ROWS:
    common = dict(clear='fill', fill_color=[0, 0, 0, 255], color=[250, 250, 250], outline=None, outline_px=0,
                  size=24, size_ar=21, valign='center')
    # Arabic mirrors the two columns: character name in the right column (aligned to its left edge, next to the
    # gutter), actor in the left column (aligned right, next to the gutter), so right-to-left reading gives
    # "character ... actor" as the Japanese does left to right.
    labels.append(dict(box=[LEFT[0], y0, LEFT[1], y1], box_ar=[RIGHT[0], y0, RIGHT[1], y1], jp=jc, en=ec, ar=ac,
                       align='right', align_ar='left', pad=4, **common))
    labels.append(dict(box=[RIGHT[0], y0, RIGHT[1], y1], box_ar=[LEFT[0], y0, LEFT[1], y1], jp=ja, en=ea, ar=aa,
                       align='left', align_ar='right', pad=4, **common))
dlc = {
    'texture': 'ev_dlc_104.aif',
    'archive': 'patch',
    'note': ('DLC cast card (update 1.05 archive only; source dump/psnova-l10n/scratch/research/uitex/patch/'
             'ev_dlc_104.aif, 1024x1024, format 0x10 = DXT1/BC1 (not DXT3: apply_spec.py needs a DXT1 path for this '
             'one), ID 002d79). Opaque black card: each name box is filled black and redrawn white, no outline. '
             'Character names from the text sheet (30030-30034 Garnet, Sunshout, Glover, Cohen, Zukku with their '
             'Arabic), voice actors in Western order as the credits rows 7500xx (小松 由佳 750039, 阪口 大助 750042; '
             'ゆかな = Yukana, 前野 智昭 = Tomoaki Maeno, 木内 秀信 = Hidenobu Kiuchi are not in the sheet). Arabic '
             'mirrors the columns with box_ar (character right, actor left; both aligned to the centre gutter).'),
    'labels': labels,
}

for spec in (title, dlc):
    p = os.path.join(SPECS, os.path.splitext(spec['texture'])[0] + '.json')
    json.dump(spec, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(p, len(spec['labels']), 'labels')
