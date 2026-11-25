# Phantasy Star Nova localization: fonts (2026-11-19)

All fonts of the English/Arabic localization are set in **`dev/psnova/fonts.json`** (paths relative to the project
folder). Change a file or size there, then rebuild the part it belongs to.

| Entry | Used for | Now | Rebuild |
|---|---|---|---|
| `game_english` | English letters in every in-game message (menus, dialogue boxes, help, tutorials), drawn as glyph pictures into each message file instead of the game's own fixed-width letters; characters the font lacks keep the game's letter; `null` = the game's own font | `Glenth/glenthregular.ttf` 18 px, baseline row 16 (my font, 2026-11-19) | text archives (below) |
| `game_arabic` | Arabic in every in-game message (phrase pictures) | Segoe UI Bold 16 px, baseline 16 (`tools/fonts/segoeuib.ttf`) | text archives |
| `subs_english` / `subs_arabic` | burned-in movie subtitles | Glenth 28 px / Segoe UI Bold 24 px | `bash dev/psnova/run_burn_subs.sh` (LANGS=en or ar for one) |
| `warning_english` / `warning_arabic` | the boot notice (Attention.mp4) | Glenth / Segoe UI | `python dev/psnova/redraw_attention.py en|ar`, then run_burn_subs.sh (it packs the movie archive) |

Text archives: `python dev/psnova/rmdtext/export_arabic.py <sheet.tsv> dump/psnova-l10n/ar/ar_all.json`, then
`python dev/psnova/rmdtext/build_l10n.py <sheet.tsv> en <out>` (English) and the same with `--arabic
dump/psnova-l10n/ar/ar_all.json` (Arabic); copy `<out>/overlay/NOVA_FileList_Vita_patch.cpk` into
`dump/decrypted/PCSG00351/lang/<en|ar>/`. Movie archives from run_burn_subs.sh go to the same folders. Run Python as
`.venv/Scripts/python.exe -s` from the project folder.

Limits for a game font (game_english / game_arabic): every glyph row is 21 px tall, so the ink must fit rows 0-20
(check ascenders/descenders at the chosen size and baseline); one message's own pictures must fit a 256x128 atlas
(English letters are deduplicated per message, so ~60-100 distinct characters fit). A thin display font can look faint
in the game's small boxes. Glenth has no `~ < >` (they fall back to the game's letters in-game; the English warning
heading was changed from "< Notice >" to "Notice").

Effect of Glenth on size: every English message now carries its own letter pictures, so the text archives grew from
~0.45/0.59 GB to ~0.89/0.78 GB (English/Arabic).

Licensing: Segoe UI is Microsoft's (local copies in tools/fonts for this machine only); check Glenth's licence before
sharing a build. An openly licensed font (OFL) is safer for anything published.
