# Phantasy Star Nova: Arabic style guide for the translation (2026-11-19)

This file sets the rules every Arabic line in the text sheet follows: for the first-pass menu/label translation and for the user's dialogue. The
term list that goes with it is `dump/psnova-l10n/ar/glossary.json` (core terms below + the names list).

## Register and tone

- Modern Standard Arabic (فصحى مبسطة), the register of official Arabic game releases. No dialect in menus.
- Menus and buttons: short nouns or verbal nouns (مصدر), not commands: «تجهيز» not «جهّز», «حذف» not «احذف».
  Help lines that address the player ("Select a weapon you want...") use the polite imperative: «اختر السلاح الذي تريد...».
- No diacritics (تشكيل) except where a word is ambiguous without them (one shadda or tanween at most). The game font is
  small (16 px), and marks crowd the line.
- Arabic punctuation: ، ؛ ؟ and the Arabic full stop is the Latin "." Exclamation "!" stays.

## Numbers, codes and Latin

- Digits stay Western (0-9), as in most Arabic game releases; the game's value slots ({8094:...}) print Western digits anyway.
- Tags like `{8094:0000}`, `{8081:03}`, `{8099:1c}`, `{end}` are control codes: every tag of the Japanese cell must appear in the
  Arabic cell, the same number of times, unchanged. Furigana tags (`{ruby:...}`, `{/ruby}`) are dropped (Japanese only).
- Kept in Latin letters: HP, PP, GP, EXP, Lv., DLC, Roman numerals (I, II, III, IV, V...) at the end of item and skill names,
  letter grades and ranks (S, A, B, C, Rank 1 = «الرتبة 1»), button names (○ × △ □, L, R, START, SELECT), PS Vita, "R" in "R Core"
  where it is a grade.
- Grade letters and single Latin letters inside a name (Memory Fragment J, G-Krahda) keep the Latin letter and its place:
  «شظية ذاكرة J», «G-كراهدا».

## Names

- Characters, places, enemies, brands and made-up words: written in Arabic letters by sound (transliteration) from the Japanese
  pronunciation, matched with the fan English spelling (リョーマ Ryoma = ريوما). The list in glossary.json is binding.
- Descriptive item names are translated by meaning: "Large Gem" = «جوهرة كبيرة», "Colorful Sushi" = «سوشي ملوّن».
  Mixed names: name part transliterated, describing part translated: "Rappy Super Wing" = «جناح رابي الفائق».
- Arabic word order: the head noun comes first (إضافة / صفة after the noun).

## Length

- A label should not be wider on screen than the Japanese original (21 px per Japanese character). The check script
  (`dev/psnova/rmdtext/check_arabic.py`) measures every line with the game's Arabic font and lists the ones that are wider.

## Core terms (binding)

| English (fan) | Japanese | Arabic |
|---|---|---|
| Hunter | ハンター | صياد |
| Ranger | レンジャー | رامي (not رامٍ: the tanween is not drawn and «رام» reads wrong; seen in the game 2026-11-19) |
| Force | フォース | ساحر |
| Buster | バスター | مدمّر |
| Human | ヒューマン | بشري |
| Newman | ニューマン | نيومان |
| Cast / CAST | キャスト | كاست |
| Deuman | デューマン | ديومان |
| Male / Female | 男性 / 女性 | ذكر / أنثى |
| ARKS | アークス | آركس |
| Darker | ダーカー | داركر |
| Gran / Gran Energy | グラン / グランエナジー | غران / طاقة غران |
| Photon | フォトン | فوتون |
| Photon Art / PA | フォトンアーツ | فن فوتوني |
| Technique / Tech | テクニック | تقنية |
| Gigantes | ギガンテス | جيغانتس |
| Nova (the planet) | ノヴァ | نوفا |
| Emergency Trial | エマージェンシートライアル | التحدي الطارئ |
| Quest | クエスト | مهمة |
| Subjugation / Subdue | 討伐 | إخضاع |
| Collect / Gather | 採集 / 収集 | جمع |
| Core | コア | نواة |
| Rare | レア | نادر |
| Weapon / Unit / Armor | 武器 / ユニット / 防具 | سلاح / وحدة / درع |
| Item | アイテム | غرض |
| Material | 素材 | مادة |
| Shop / Facility / Base | ショップ / 施設 / 拠点 | متجر / منشأة / قاعدة |
| Costume | コスチューム | زي |
| Lobby action | ロビーアクション | حركة الردهة |
| Fire / Ice / Lightning / Wind / Light / Dark | 炎 / 氷 / 雷 / 風 / 光 / 闇 | نار / جليد / برق / رياح / ضوء / ظلام |
| Resist (element) | 耐性 | مقاومة |
| S-ATK / R-ATK / T-ATK | 打撃力 / 射撃力 / 法撃力 | قوة الضرب / قوة الرمي / قوة التقنية |
| S-DEF / R-DEF / T-DEF | 打撃防御 / 射撃防御 / 法撃防御 | دفاع الضرب / دفاع الرمي / دفاع التقنية |
| DEX | 技量 | البراعة |
| ... Up I / Down II | ～アップⅠ / ダウンⅡ | زيادة ... I / خفض ... II |
| Yes / No / OK / Cancel | はい / いいえ / OK / キャンセル | نعم / لا / موافق / إلغاء |
| None | なし | لا شيء |
| Delete / Back / Confirm / Select / Equip | 削除 / 戻る / 決定 / 選択 / 装備 | حذف / رجوع / تأكيد / اختيار / تجهيز |
| Status / Power | ステータス / 威力 | الحالة / القوة |
| Class | クラス | الفئة (plural الفئات) |
| Counter (a facility desk) | カウンター | مكتب (Class Counter = مكتب الفئات) |
| Partner / Buddy | パートナー / バディ | رفيق |
| Mag | マグ | ماغ |
| Rappy | ラッピー | رابي |
| Sword / Partisan / Wired Lance | ソード / パルチザン / ワイヤードランス | سيف / رمح / رمح سلكي |
| Twin Daggers / Double Saber / Knuckles | ツインダガー / ダブルセイバー / ナックル | خنجران / سيف مزدوج / قبضات |
| Assault Rifle / Launcher / Twin Machine Guns | アサルトライフル / ランチャー / ツインマシンガン | بندقية هجومية / قاذفة / رشاشان |
| Rod / Talis / Wand | ロッド / タリス / ウォンド | عصا / تعويذة / صولجان |
| Gunslash | ガンスラッシュ | سيف ناري |
