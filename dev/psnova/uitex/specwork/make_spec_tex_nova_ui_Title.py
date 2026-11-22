"""make_spec_tex_nova_ui_Title.py - writes dump/psnova-l10n/uitex/specs/tex_nova_ui_Title.json (menu page-title banners).

Boxes = the sprite cells of update ui_common.crbpj (float UVs, pattern u0 v0 u0 v1 u1 v0 u1 v1) where traced; the
others follow the same row grid (row heights 27-28 px, cell widths per row) and the glyph extents. The small English
line block (y 340-512) and the icons are not touched; GA / PA (row 0) are already Latin and stay.
Style sampled from the texture: glyph colour ~(140,242,255) at alpha 221, soft 1-2 px halo (41,182,255) at low alpha.
Size: the largest that fits (one line, or two lines when that is larger), capped at CAP_* so the English is not
taller than the Japanese gothic.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.dirname(HERE))
import apply_spec as A  # noqa: E402

CAP_EN, CAP_AR = 24, 20
COLOR, GLOW, GLOW_PX = [140, 242, 255, 221], [41, 182, 255, 150], 1

# (box, jp, en, ar[, extra keys])
L = [
    # row 0: 48-px cells, y 1-28
    ([1, 1, 48, 28], '装備', 'Equip', 'المعدات'),
    ([49, 1, 96, 28], '武器', 'Weapons', 'الأسلحة'),
    ([97, 1, 144, 28], '防具', 'Shields', 'الدروع'),
    ([145, 1, 192, 28], '習得', 'Learning', 'التعلم'),
    ([193, 1, 240, 28], '惑星', 'Planet', 'الكوكب'),
    ([241, 1, 288, 28], '製作', 'Crafting', 'الصنع'),
    ([289, 1, 336, 28], '食堂', 'Restaurant', 'المطعم'),
    ([337, 1, 384, 28], 'ラボ', 'Lab', 'المختبر'),
    ([385, 1, 432, 28], '開発', 'Develop', 'التطوير'),
    ([433, 1, 480, 28], '配置', 'Layout', 'الترتيب'),
    ([481, 1, 528, 28], '倉庫', 'Storage', 'المخزن'),
    ([529, 1, 577, 28], '端末', 'Terminal', 'الطرفية'),
    ([673, 1, 739, 28], '捕獲所', 'Capture Facility', 'منشأة الأسر'),
    # row 1: 66-px cells, y 29-56
    ([1, 29, 67, 56], 'スキル', 'Skills', 'المهارات'),
    ([68, 29, 134, 56], 'ボード', 'Board', 'اللوحة'),
    ([135, 29, 201, 56], 'マキア', 'Mahkia', 'ماكيا'),
    ([269, 29, 335, 56], 'クラス', 'Class', 'الفئة'),
    ([336, 29, 402, 56], 'エステ', 'Makeover', 'التجميل'),
    ([403, 29, 469, 56], '探索隊', 'Search Team', 'فريق الاستكشاف'),
    ([470, 29, 536, 56], 'ノヴァ', 'Nova', 'نوفا'),
    ([537, 29, 611, 56], '/ヘルプ', '/Help', 'مساعدة/', {'align_ar': 'left'}),
    # row 2: 85/102-px cells, y 57-84
    ([1, 57, 85, 84], 'アイテム', 'Items', 'الأغراض'),
    ([171, 57, 255, 84], 'ショップ', 'Shops', 'المتاجر'),
    ([256, 57, 341, 84], '人員配属', 'Assignment', 'التعيين'),
    ([341, 57, 443, 84], 'ギガンテス', 'Gigantes', 'جيغانتس'),
    ([444, 57, 546, 84], '設定', 'Settings', 'الإعدادات'),
    ([547, 57, 649, 84], 'カウンター', 'Counter', 'المكتب'),
    # row 3: 122-px cells, y 85-112
    ([1, 85, 123, 112], 'コスチューム', 'Costumes', 'الأزياء'),
    ([124, 85, 246, 112], 'サブパレット', 'Subpalette', 'اللوحة الفرعية'),
    ([247, 85, 369, 112], 'カスタマイズ', 'Customize', 'التخصيص'),
    ([370, 85, 492, 112], 'オブジェクト', 'Objects', 'المجسمات'),
    ([493, 85, 615, 112], 'マルチプレイ', 'Multiplayer', 'اللعب الجماعي'),
    ([616, 85, 738, 112], 'コア精錬所', 'Core Refinery', 'مصفاة النواة'),
    ([739, 85, 861, 112], '/テクニック', '/Techniques', 'التقنيات/', {'align_ar': 'left'}),
    # row 4: y 113-140
    ([1, 113, 145, 140], '協力プレイ履歴', 'Co-op History', 'سجل اللعب التعاوني'),
    ([146, 113, 286, 140], 'アタッチパーツ', 'Attachments', 'الملحقات'),
    ([287, 113, 465, 140], 'オペレーターの交代', 'Change Operator', 'تبديل المشغّل'),
    # row 5: 160-px cells, y 141-168
    ([1, 141, 161, 168], 'コールドスリープ', 'Cold Sleep', 'السبات البارد'),
    ([162, 141, 322, 168], 'シアタースコープ', 'Theater Scope', 'منظار المسرح'),
    ([323, 141, 505, 168], 'フレンドパートナー', 'Friend Partner', 'رفيق صديق'),
    # row 6
    ([1, 169, 217, 196], 'キャラクタークリエイト', 'Character Creation', 'إنشاء الشخصية'),
    # row 7: y 197-224
    ([1, 197, 103, 224], 'あらすじ', 'Synopsis', 'الملخص'),
    ([105, 197, 152, 224], '約束', 'Promises', 'الوعود'),
    ([155, 197, 257, 224], 'ステータス', 'Status', 'الحالة'),
    ([261, 197, 383, 224], 'ゲストクルー', 'Guest Crew', 'طاقم الضيوف'),
    # row 8: y 225-252
    ([1, 225, 123, 252], 'メニュー画面', 'Menu', 'القائمة'),
    ([125, 225, 265, 252], 'チュートリアル', 'Tutorials', 'الدروس التعليمية'),
    ([267, 225, 465, 252], 'ギガンテスバトルデモ', 'Gigantes Battle Demo', 'عرض معركة جيغانتس'),
    # row 9
    ([1, 253, 163, 280], 'キャラクター選択', 'Character Select', 'اختيار الشخصية'),
    # row 10: y 280-307
    ([1, 280, 112, 307], '施設の開発', 'Develop Facilities', 'تطوير المنشآت'),
    ([119, 280, 227, 307], 'クルー配属', 'Crew Assignment', 'تعيين الطاقم'),
    ([235, 280, 406, 307], '施設の設置と移動', 'Facility Placement', 'تركيب المنشآت ونقلها'),
]


def fit(lines, lang, bw, bh, pad=1):
    for s in range(3 * bh, 5, -1):
        w, h, _ = A._measure(lines, A.font_for(lang, s), 0, 0)
        if w <= bw - 2 * pad and h <= bh:
            return s
    return 6


def best(text, lang, box, cap):
    """one line, or the two-line split (at a space) that allows the largest size; capped; one line wins ties."""
    bw, bh = box[2] - box[0], box[3] - box[1]
    cands = [(min(cap, fit(A._lines(text, lang), lang, bw, bh)), 0, text)]
    words = text.split(' ')
    for i in range(1, len(words)):
        t2 = ' '.join(words[:i]) + '\n' + ' '.join(words[i:])
        cands.append((min(cap, fit(A._lines(t2, lang), lang, bw, bh)), -1, t2))
    s, _, t = max(cands)
    return s, t


def main():
    labels = []
    for row in L:
        box, jp, en, ar = row[:4]
        extra = row[4] if len(row) > 4 else {}
        se, te = best(en, 'en', box, CAP_EN)
        sa, ta = best(ar, 'ar', box, CAP_AR)
        lab = {'box': box, 'jp': jp, 'en': te, 'ar': ta, 'clear': 'transparent', 'align': 'left',
               'color': COLOR, 'outline': None, 'outline_px': 0, 'glow': GLOW, 'glow_px': GLOW_PX,
               'size': None, 'size_en': se, 'size_ar': sa, 'valign': 'center'}
        lab.update(extra)
        labels.append(lab)
        print('%-12s en %-24s %2d   ar %2d' % (jp, te.replace('\n', '/'), se, sa))
    spec = {
        'texture': 'tex_nova_ui_Title.aif',
        'archive': 'patch',
        'note': ('Menu page-title banners (cyan gothic, soft blue halo). Boxes are the sprite cells of update '
                 'ui_common.crbpj where traced (rows of 27-28 px: 48-px cells in row 0, 66 in row 1, 85/102 in row 2, '
                 '122 in row 3, 160 in row 5); the rest follow the same grid and the glyph extents. The small English '
                 'line block (y 340-512), the icons and the Latin GA / PA pieces stay. English left-aligned like the '
                 'Japanese; Arabic right-aligned except the two suffix pieces "/Help" and "/Techniques" (appended to '
                 'another title piece), which stay left so the slash meets it. Sizes: largest fit (two lines when '
                 'larger), capped at %d px (en) / %d px (ar). Written by '
                 'dev/psnova/uitex/specwork/make_spec_tex_nova_ui_Title.py.' % (CAP_EN, CAP_AR)),
        'labels': labels,
    }
    out = os.path.join(ROOT, 'dump', 'psnova-l10n', 'uitex', 'specs', 'tex_nova_ui_Title.json')
    json.dump(spec, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(len(labels), 'labels ->', out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
