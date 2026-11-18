# Phantasy Star Nova: localization notes (English + Arabic)

Living log, started 2026-11-18. Every step of the localization work goes here, with its strength:
**proven**, **single run**, **untested**. Scratch output is in `dump/psnova-l10n/` (not part of the project).

## Question 1: what language is the game?

- The game is the **Japanese release** (PCSG00351, JP0177 content id). Base text, voices and UI art are Japanese.
- The player's copy has a `rePatch` folder: the **Arks-Layer English fan translation** (replaces
  `NOVA_FileList_Vita_patch.cpk` and `_movie.cpk`; 2,257 translated files, 5,875 identical to 1.05).
  The recomp layers it on top (`app0_repatched`), so **the build we play shows English text with Japanese voices**
  (proven by the journal's test46/47 notes: "Japanese text" without the rePatch's files, "English" with the merged archive).
- `RECOMP_NO_REPATCH=1` at import plays the pure Japanese game.
- English therefore already exists as a "language" only because a fan patch overwrote Japanese. The game has no
  language switch of its own (single-language Japanese Vita release; no language-select code or per-language
  folders seen in the archive list).

## Where the text lives (archive survey, 2026-11-18, single run)

Tool: `pipeline/cri/cpk.py list|extract` (CRI CPK reader). Lists in `dump/psnova-l10n/{patch,base}.tsv`.

| Archive | Entries | Notes |
|---|---|---|
| `NOVA_FileList_Vita.cpk` (base, 2.8 GB) | 87,268 | 21,379 `.rmd`, 9,735 `.csv`, 5,756 `.lua`, 6,580 `.aif` (images), 18,759 `.aet`, 18,763 `.aai` |
| `NOVA_FileList_Vita_patch.cpk` (English merged) | 23,034 | 20,056 `.rmd`, 1,580 `.csv`, 423 `.lua`, 433 `.aif`, `novamessagedictionary.mdic` |

- **`msg_*.rmd`**: message files (dialogue/menus/etc.), the bulk of the text (about 20,000 files).
- **`novamessagedictionary.mdic`**: magic `BMVN`, UTF-16-looking strings (e.g. "ジャンクション") with ids: a word dictionary.
- **`.csv`** (Shift-JIS) hold tables, some with Japanese labels (e.g. `guide_message_parameter.csv`).
- **`.lua`** scripts (423 patched): may hold some text; not yet checked.
- **`.aif`**: texture/UI images. Text baked into pictures (titles, menu art) must be redrawn per language.

## The `.rmd` format (first look, single run)

Header magic `" DMR"` (bytes `20 44 4d 52`), producer string `FontConverterDll_1.0.1.3_rc6`.
Text is stored as **16-bit little-endian glyph indices, not Unicode**. The same sentence has different codes in the
Japanese file and the English file:

- JP `msg_100001.rmd` (25,072 bytes): codes like `0x019f 0x019e 0x01a6 ...`.
- EN `msg_100001.rmd` (25,200 bytes): codes like `0x008e 0x01e8 0x00a0 ...`, with **`0x01e8` = space**.
  Latin letters sit in a low range (about 0x8e to 0xc0), `0x8080` and `0x8002` are control/line codes.
- Header size field differs (0x2010 vs 0x2090): the EN file carries 128 more bytes.

So the glyph-index table is defined by a **font** (the FontConverter output), and the English fan patch likely ships
its own font + code mapping. **Open**: where that glyph table / font lives (probably a font texture `.aif` plus a map
inside an `.rmd`-adjacent file or the executable), and whether the game's renderer can draw right-to-left text.

## The font lives in `.rmd` files too (found 2026-11-18, single run)

`strings` on `eboot.bin.elf` shows `BasicCharSet.rmd`, `BasicRubySet.rmd`, `llu.rmd` and many `Cast_FontSizeNN` names.
`BasicCharSet.rmd` (270,320 bytes) and `BasicRubySet.rmd` (140,400) are **only in the base archive** (the English patch does
not touch them), so English and Japanese text use the **same glyph set**; the English patch only re-encodes each message
with the codes of Latin letters that already exist in it.

Layout seen in `BasicCharSet.rmd` (same header magic `" DMR"` and `FontConverterDll_1.0.1.3_rc6`):

- header of 0x1e10 bytes holding a **per-glyph table**: records of 16-bit flags + two corner pairs of **float UVs**
  (`0x3d28...`, `0x3e48...` = texture coordinates 0..1) in code order;
- after the header, about 262,000 bytes that look like an **8-bit 512 x 512 glyph bitmap** (the rendered font).
- A message `.rmd` has the same kind of header (0x2010 to 0x2090 bytes: UV records, then the 16-bit text codes at about +0x110).

So the game has **no TrueType font and no Unicode**: text is pre-rendered by a tool (Sega/tri-Ace's *FontConverter*) into
bitmap glyph pages plus code tables. Anything new (Arabic) must be added to these bitmap pages and code tables, and every
message re-encoded. **Not yet decoded** (next steps): the exact record layout, the mapping code -> character,
what `BasicRubySet` (furigana) holds, how the 512 x 512 page is sampled (format, palette), and how `Cast_FontSize*` picks sizes.

## "Native" English: the Japanese subtitles burned into the story movies (2026-11-18, single run)

The user noticed the English subtitles appear **below the Japanese ones** and wants English to be native (Japanese gone).
Cause, checked on frames: the subtitles in the story movies are **part of the video picture**. Sega's Japanese subtitle line
is burned in; the fan patch re-encoded the movies and burned its English line under it. Nothing can switch the Japanese off at
runtime, so the video itself must change.

- `NOVA_FileList_Vita_movie.cpk` (21 entries, 960x544, H.264 29.97 fps + AAC). The patch's copy differs from the
  base in **8 files**: `MP00_000_000`, `MP00_000_010`, `MP00_010_050`, `MP06_030_040`, `MP06_030_050`, `MP06_030_070`,
  `MP09_040_040`, `MP09_040_070` (plus `Attention.mp4`, the patch credit). The other 12 (`OpeningDemo`, `Trial_*`,
  `MP09_030_*`, `MP09_040_025/030`, `Logo_SEGA_triAce`) are identical to the base, i.e. untranslated.
- Frames of `MP00_000_000.mp4` (extracted to `dump/psnova-l10n/movies/`): Japanese line at about **y 465-505**, English
  line at about y 515-535 (both centred; Japanese is thin white with a dark outline).
- **Test, 3 frames (single run):** mask = near-white pixels in the band y 462-508, dilated 7 px, `cv2.inpaint` (Telea, radius 4)
  removed the Japanese line cleanly on a plain and a moving background (result image `dump/psnova-l10n/movies/inpaint_test.png`),
  leaving the English line untouched. Not yet tried on a whole movie (flicker between frames, bright backgrounds, subtitle
  lines that sit at another height).
- **Plan:** script per movie: decode with OpenCV, inpaint the band on frames where text is detected (white-pixel count in the
  band), re-encode H.264 960x544 with `libx264` + copy the AAC track, write a patched movie archive (`cpk_merge.py` style), run through
  the game's movie player (`runtime/media/video.c` decodes H.264). Optional later: move the English line down to the Japanese
  line's spot.
- Tools: OpenCV (system Python 4.13); ffmpeg with libx264 + mp4 muxer at
  `F:\Antigravity Proj\animation\node_modules\ffmpeg-static\ffmpeg.exe` (the one in `recomp library\metroidprimeport` has no
  H.264 encoder and no png/jpg muxer).
- **Other Japanese left over in the English build:** the "PSO2 Save Bonus Award" dialog on the title screen (progress picture
  panel 3) is still Japanese: a message the patch did not translate; find its `.rmd` or `.csv`. Texture art with baked Japanese
  (`.aif`, e.g. `tex_nova_ui_Title`) not surveyed yet.

## Plan for English and Arabic as options (not yet built)

1. **English/Japanese switch**: cheapest of all. Both sets of files already exist (base archive = Japanese,
   rePatch = English). Add a runtime/launcher setting that picks which archive layering the file layer serves
   (the `REPATCH` layer on or off, per run). Voices stay Japanese either way.
2. **Arabic**: needs three pieces
   - a text export of all ~20,000 `.rmd` (decode glyph indices -> Unicode using the font map; Claude does menus/short labels,
     the user fills dialogue, as for Wonder; see `memory: every-recomp-standard`);
   - an Arabic **font** with joined/contextual forms (presentation forms) added to the game's font texture + glyph map;
   - **right-to-left layout** (reverse order, mirrored alignment) in the text drawing code, and a re-encoder that writes
     `.rmd` files back with the new glyph codes, then a patched archive (`cpk_merge.py` already copies/merges entries).
   - UI art with baked-in text (`.aif`) is Japanese/English only; Arabic versions would need redrawn textures.
3. **Selection at launch**: a `language = ja | en | ar` setting in the game's ini plus a launcher option.

Reusable reference: `Super Mario Bros Wonder\tools\arabic\README.md` (pipeline for the same job).

## Decisions and cost rule

- The user's rule (2026-11-18): **use scripts and Haiku subagents to cut usage when possible**. So far everything was done by
  scripts (`cpk.py list/extract`, `xxd`, `grep -a`). Bulk work to come (decode ~20,000 messages, code tables, Arabic
  export workbook) is script work; Haiku fits spot checks and indexing, results verified before use.
- Document every step in this file (the user asked, 2026-11-18).

## Log

- 2026-11-18 (later): user asked for "native" English; confirmed Japanese hard subtitles in the 8 patched story movies,
  inpaint test on 3 frames looked clean, found a libx264 ffmpeg. Nothing in the game or build changed.
- 2026-11-18: surveyed archives, extracted `msg_100001.rmd` (JP and EN), `novamessagedictionary.mdic`, `guide_message_parameter.csv`
  to `dump/psnova-l10n/sample/`; found the glyph-index text format. Nothing in the game or build was changed.
