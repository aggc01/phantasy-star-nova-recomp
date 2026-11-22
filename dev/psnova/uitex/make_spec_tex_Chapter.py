# Writes dump/psnova-l10n/uitex/specs/tex_Chapter.json (chapter title cards). Boxes = the sprite cells of
# base UI_Chapter.crbpj (float UVs x 1024), so each clear matches exactly what the game crops.
import json, os
JP = [  # (box, japanese piece)
    ((0, 4, 144, 68), "滅び"), ((143, 4, 285, 68), "歴史"), ((298, 4, 656, 68), "穿ち拓く希望"),
    ((664, 4, 864, 68), "生存へ"), ((864, 4, 1008, 68), "挑戦"),
    ((4, 68, 223, 132), "ほんとう"), ((232, 68, 376, 132), "約束"), ((437, 68, 581, 132), "惑星"),
    ((581, 68, 725, 132), "洗礼"), ((726, 68, 870, 132), "鋼焔"), ((870, 68, 1014, 132), "巨獣"),
    ((11, 134, 305, 198), "より永遠に"), ((315, 134, 576, 198), "命令違反"), ((584, 134, 659, 198), "私"),
    ((658, 134, 802, 198), "選択"), ((796, 134, 940, 198), "英雄"), ((940, 134, 1015, 198), "証"),
    ((6, 200, 133, 264), "脱出"), ((151, 200, 278, 264), "真実"), ((302, 200, 370, 264), "の"),
    ((394, 200, 424, 264), "「"),
]
# English sprites: (box, english on the texture, arabic, size). en = None: left untouched in the English build.
EN = [
    ((933, 209, 981, 244), "Us (suffix cell: The Demon Above + Us)", "", None),
    ((27, 266, 87, 301), "The (prefix cell: The + Value of Friendship / Demon Above / Endless Chapter / Enemy Before Us)", "", None),
    ((457, 205, 628, 248), "Grand Act", "الفصل الكبير", 26),
    ((745, 209, 933, 244), "Enemy Before (Us)", "العدو الذي أمامنا", 24),
    ((8, 266, 474, 301), "The Battle for Survival Begins", "تبدأ معركة البقاء", 24),
    ((483, 266, 713, 301), "Youth and Trust", "الشباب والثقة", 24),
    ((13, 310, 285, 345), "Endless Chapter ∞", "الفصل اللانهائي ∞", 24),
    ((291, 310, 493, 345), "Tipping Point", "نقطة التحول", 24),
    ((503, 310, 716, 345), "A Planet's End", "نهاية كوكب", 24),
    ((21, 354, 293, 389), "Value of Friendship", "قيمة الصداقة", 24),
    ((308, 354, 493, 389), "Demon Above", "الشيطان الذي فوقنا", 22),
    ((496, 354, 570, 389), "Juno", "يونو", 24),
    ((574, 354, 717, 389), "My Choice", "اختياري", 24),
]
labels = []
for box, jp in JP:
    labels.append({"box": list(box), "jp": jp, "en": "", "ar": "", "clear": "transparent", "align": "center",
                   "color": [255, 255, 255], "outline": None, "outline_px": 0, "size": None, "valign": "center"})
for box, en_src, ar, size in EN:
    labels.append({"box": list(box), "jp": "", "en_source": en_src, "en": None, "ar": ar, "clear": "transparent",
                   "align": "center", "color": [255, 255, 255], "outline": None, "outline_px": 0, "size": size,
                   "valign": "center"})
spec = {
    "texture": "tex_Chapter.aif",
    "archive": "base",
    "note": ("Chapter title cards (layout base UI_Chapter.crbpj; boxes are its sprite cells). 21 Japanese word pieces "
             "(the 24 words of the research count; 穿ち拓く希望 and より永遠に are single cells): en and ar both erase "
             "them (transparent), so the card shows only the English subtitle (en) or its Arabic redraw (ar). The 13 "
             "English-sprite labels have \"en\": null = not applied in the English build (texture left as is); in the "
             "Arabic build each is cleared and redrawn in Arabic, white, no outline, centred (Segoe UI Bold). Subtitles "
             "are assembled from pieces: the 'The' cell (27-87, inside the Battle line) is a prefix and the 'Us' cell "
             "(933-981, inside 'Enemy Before Us') a suffix; in Arabic both become blank, the Arabic article/pronoun is "
             "inside the main piece (Demon Above -> 'الشيطان الذي فوقنا'), and 'Enemy Before Us' is drawn only in "
             "745-933 so the Us cell stays empty. Roman numeral pieces II and I (634-672, 685-712) stay Latin. "
             "The Battle line's Arabic (about 161 px wide, centred) stays clear of the 'The' cell. The card reads "
             "'Enemy Before Us' while message 410327 says 'The Enemy Below'; the Arabic follows the card."),
    "labels": labels,
}
out = "dump/psnova-l10n/uitex/specs/tex_Chapter.json"
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(spec, f, ensure_ascii=False, indent=2)
print(out, len(labels))
