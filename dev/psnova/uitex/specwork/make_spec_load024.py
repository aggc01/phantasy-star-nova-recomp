"""Write dump/psnova-l10n/uitex/specs/load024.json (loading screen 'basic controls' diagram), 2026-11-19.
Boxes = tight bounds of the Japanese (measure_load024.py) plus 1-2 px, kept off the blue leader lines."""
import json, os
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
OUT = os.path.join(ROOT, 'dump', 'psnova-l10n', 'uitex', 'specs', 'load024.json')

WHITE = [238, 238, 240]
NAVY = [0, 0, 32]
H = dict(color=WHITE, outline=NAVY, outline_px=1, size=16, size_ar=14, clear='inpaint', inpaint_threshold=24, inpaint_dilate=2, valign='center')
D = dict(color=WHITE, outline=NAVY, outline_px=1, size=13, size_ar=12, clear='inpaint', inpaint_threshold=24, inpaint_dilate=2, valign='center')


def L(box, jp, en, ar, base, **kw):
    d = dict(box=box, jp=jp, en=en, ar=ar)
    d.update(base)
    d.update(kw)
    return d


labels = [
    # page title, cyan with a soft blue edge
    L([42, 11, 192, 42], '基本操作', 'Basic Controls', 'التحكم الأساسي',
      dict(color=[115, 206, 213], outline=[20, 40, 110], outline_px=1, glow=[30, 80, 170], glow_px=2, size=None,
           clear='inpaint', inpaint_threshold=24, inpaint_dilate=2, valign='center'), align='left', align_ar='left'),
    # left column
    L([55, 53, 108, 71], 'ボタン', 'Button', 'زر', H, align='left', align_ar='left'),
    L([36, 77, 326, 97], 'カメラリセット／ロックオン ON・OFF 切替', 'Reset Camera / Lock-on ON/OFF',
      'إعادة ضبط الكاميرا / تشغيل قفل الهدف وإيقافه', D, align='left', align_ar='left'),
    L([70, 124, 150, 147], '方向キー', 'D-Pad', 'أزرار الاتجاه', H, align='left', align_ar='left'),
    L([36, 152, 216, 186], '上下…武器パレット切替／カーソル移動', 'Up/Down: Switch Weapon Palette /\nMove Cursor',
      'أعلى/أسفل: تبديل لوحة السلاح /\nتحريك المؤشر', D, align='left', size=13, size_ar=11, line_gap=2, align_ar='left'),
    L([36, 196, 216, 229], '左右…サブパレット切替／カーソル移動', 'Left/Right: Switch Subpalette /\nMove Cursor',
      'يمين/يسار: تبديل اللوحة الفرعية /\nتحريك المؤشر', D, align='left', size=13, size_ar=11, line_gap=2, align_ar='left'),
    L([63, 268, 172, 286], '左スティック', 'Left Stick', 'العصا اليسرى', H, align='left', align_ar='left'),
    L([38, 294, 176, 310], 'キャラクターの移動', 'Move Character', 'تحريك الشخصية', D, align='left', align_ar='left'),
    # top centre
    L([365, 53, 515, 71], 'タッチスクリーン', 'Touch Screen', 'شاشة اللمس', H, align='left', align_ar='left'),
    L([363, 78, 626, 110], 'サブパレットのアイテム使用 / 視点モード切替 / レーダーマップ表示切替',
      'Use Subpalette Item / Switch Viewpoint /\nShow/Hide Radar Map',
      'استخدام غرض اللوحة الفرعية / تبديل المنظور /\nإظهار خريطة الرادار وإخفاؤها', D, align='left', size=13, size_ar=11,
      line_gap=2, align_ar='left'),
    # right column (right aligned in the Japanese; the button word sits right after its letter/icon)
    L([933, 53, 990, 71], 'ボタン', 'Button', 'زر', H, align='left', align_ar='left'),
    L([870, 78, 990, 93], '攻撃 パレット切替', 'Switch Attack Palette', 'تبديل لوحة الهجوم', D, align='right'),
    L([934, 114, 990, 133], 'ボタン', 'Button', 'زر', H, align='left', align_ar='left'),
    L([850, 139, 977, 155], '攻撃 2 ／ ガード', 'Attack 2 / Guard', 'الهجوم 2 / دفاع', D, align='right'),
    L([934, 165, 990, 184], 'ボタン', 'Button', 'زر', H, align='left', align_ar='left'),
    L([900, 190, 990, 206], '攻撃 1', 'Attack 1', 'الهجوم 1', D, align='right'),
    L([934, 216, 990, 235], 'ボタン', 'Button', 'زر', H, align='left', align_ar='left'),
    L([900, 241, 990, 262], '決定', 'Confirm', 'تأكيد', D, align='right'),
    L([933, 278, 990, 297], 'ボタン', 'Button', 'زر', H, align='left', align_ar='left'),
    L([741, 303, 990, 319], 'ジャンプ／キャンセル／前画面に戻る', 'Jump / Cancel / Back', 'القفز / إلغاء / رجوع', D,
      align='right'),
    L([879, 330, 990, 348], '右スティック', 'Right Stick', 'العصا اليمنى', H, align='left', align_ar='left'),
    L([880, 355, 990, 370], 'カメラの旋回', 'Rotate Camera', 'تدوير الكاميرا', D, align='right'),
    # bottom centre: SELECT / START + button word
    L([418, 330, 478, 349], 'ボタン', 'Button', 'زر', H, align='left', align_ar='left'),
    L([309, 355, 400, 370], 'オートラン', 'Auto-Run', 'الجري التلقائي', D, align='left', align_ar='left'),
    L([619, 330, 680, 349], 'ボタン', 'Button', 'زر', H, align='left', align_ar='left'),
    L([520, 355, 640, 370], 'メインメニュー', 'Main Menu', 'القائمة الرئيسية', D, align='left', align_ar='left'),
    # framed hint: [stick] 左スティック+ [circle] ボタン…回避アクション
    L([60, 399, 157, 415], '左スティック+', 'Left Stick +', '+ العصا اليسرى', D, align='left', align_ar='right'),
    L([177, 399, 338, 415], 'ボタン…回避アクション', 'Button: Dodge', 'المراوغة: زر', D, align='left',
      align_ar='left'),
    # red note
    L([56, 437, 700, 461], 'ソード、パルチザン、パイルを装備している際にはガードをすることが可能です。',
      'You can Guard while a Sword, Partisan or Pile is equipped.', 'يمكنك الدفاع عند تجهيز سيف أو رمح أو وتد.',
      dict(color=[250, 129, 131], outline=[0, 0, 24], outline_px=1, size=13, size_ar=12, clear='inpaint', inpaint_threshold=24, inpaint_dilate=2,
           valign='center'), align='left', align_ar='left'),
]

spec = {
    'texture': 'load024.aif',
    'archive': 'base',
    'note': ('Loading screen: PS Vita control diagram (base only; source file is dump/psnova-l10n/scratch/research/uitex/'
             'base/load024.aif, 1024x512 DXT3, ID 03e77d). Opaque picture: every label is inpainted (threshold 30 so the '
             'dark navy text outline goes too) and redrawn white with a 1 px navy outline (title cyan, note red). '
             'Button letters/icons (L, R, SELECT, START, triangle/square/circle/cross, stick and D-pad icons) are pictures '
             'and stay; only the word ボタン after them becomes Button / زر, drawn left-aligned next to the icon in both '
             'languages (Arabic reads زر then the letter/icon on its left = "L button"). The red ※ after ガード stays '
             '(box ends before it). Framed hint: Arabic is ordered for right-to-left reading across the fixed icons: '
             '"المراوغة: زر" [circle] "+ العصا اليسرى" [stick] = "Dodge: circle button + left stick". Terms from the text '
             'sheet (22113-22125 control settings, 10801/10802/10810 Sword/Partisan/Pile, 50019 Guard). Headers size 16, '
             'descriptions 13 (two-line ones fit-to-box).'),
    'labels': labels,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(spec, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(OUT, len(labels), 'labels')
