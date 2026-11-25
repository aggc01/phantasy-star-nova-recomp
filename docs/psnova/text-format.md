# Phantasy Star Nova: how the game stores its text (decoded 2026-11-18)

Tools: `dev/psnova/rmdtext/` (rmdlib.py reader, learn_map.py, ocr_kanji.py, make_review.py, build_sheet.py, check_sheet.py,
xlsxw.py, map_manual.json). Earlier partial notes: `dev/psnova/rmd/RMD-FORMAT.md` (superseded by this file).
Work files: `dump/psnova-l10n/text/` (extracted .rmd, maps, review sheets), the sheet in `dump/psnova-l10n/sheet/`.

## Where the text is

| Place | What | Count |
|---|---|---|
| `NOVA_FileList_Vita.cpk` (base) `msg_<id>.rmd` | every message: menus, help, items, dialogue | 21,377 |
| `NOVA_FileList_Vita_patch.cpk` (Sega's 1.05 update) `msg_<id>.rmd` | newer or changed messages; win over base | 5,158 |
| the fan rePatch's patch archive | the English translation, same file names | 20,056 |
| `novamessagedictionary.mdic` (1.05 update) | the FIRST LINE of messages in UTF-16, by id | 26,709 entries |
| `BasicCharSet.rmd`, `BasicRubySet.rmd` (base) | the shared font (373 glyphs) and the furigana font (180) | |
| `.csv` tables, `.lua` | mostly sources and developer labels; 85-100 % of the dialogue/help lines in them also exist as messages (checked 2026-11-18). Exception to watch: `charactermake_resource_database_*.csv` (ja_name/en_name columns) | |

Together (update over base): **25,484 Japanese messages.**

## .rmd layout (little-endian)

- `0x00` `" DMR"`; `0x04` u32 header size = offset of the texture chunks; `0x10` `FontConverterDll_1.0.1.3_rc6`.
- `0x30..` u32 fields f[0..23]: `f[1]+0x10` = text start, `f[2]+0x10` = glyph table, `f[5]` = glyph record count,
  `f[16]`,`f[17]` = atlas width, height. `0x90` u64 = message id (= the file name number). `0xa0` float = text height in px
  (21 per line + 20 per further line); `0x9c` float: unknown (not the width).
- Glyph table: `f[5]` records of 20 bytes: u8 width, u8, u16 0, float u0, v0, u1, v1. The first records (non-zero width) are
  this file's own glyphs, in the order the codes 0x391, 0x392, ... use them.
- After the header: 0x1e0 bytes of GXM texture chunks (`FIA`, `FRap`, `Xgmi`, `FMA`, `daeh`, `ffub`, `rdda`), then the
  atlas: **DXT3 (BC2), blocks in Morton (Z) order; the font is in the 4-bit alpha** (the colour half is constant white).
  (The earlier attempt read it as plain 8-bit pixels; the byte statistics - nibbles, stride 16 - pointed at DXT3.)

## Text codes

The text is read **byte by byte**, as the game's decoder (fn_817e65fc) does: a byte b < 0x80 is a one-byte code; b >= 0x80
starts a two-byte code (b & 0x7f) | (next << 7); bit 0x4000 = control (u16 0x80XX). Codes 1..400 = BasicCharSet glyph
code-1, above 400 = own glyph code-401. The table below gives codes in their u16 (little-endian) spelling; own glyph i is
game code 401 + i, which equals u16 0x391 + i only for i < 111:

| Code | Meaning |
|---|---|
| `0x0081..0x0390` | one fixed character table (ASCII, hiragana, katakana, punctuation, full-width letters). Learned (324 codes) by lining up first lines with the dictionary; the rest by hand from context (`map_manual.json`). Hiragana じ..ぽ have two codes each (0x100-0x112 and 0x180-0x192). The BasicCharSet atlas is in the same order with gaps (around 0x285-0x2b4 the atlas index + 0x100). |
| `0x0391 + i` | this file's own glyph i (kanji, some symbols like ※ →, a few kana in another style) |
| `0x8080` | new line |
| `0x8090 <reading bytes> 00 <base codes> 0x8091` | furigana: reading byte b = BasicRubySet glyph b-1 (惑星 = ほし `1e 0c`, 艦 = ふね, 相棒 = バディ) |
| `0x8081 <1 byte>` | text colour: 03 red, 06 cyan, 07 yellow (found 2026-11-19, right-alignment-research.md) |
| `0x8099 <1 byte>` | unknown (params like 1c, 65, 79) |
| `0x8094 <2 bytes>` | a value slot filled in by the game (00 00, 01 00, ...) |
| `0x8082` | **colour back to white; the text goes on** (until 2026-11-19 read as an end, which lost the text after it in 179 files). A 0x00 byte ends the text. |
| `0x8095` | no-op in the game; our encoder puts it first in Arabic messages as the right-alignment mark (pack hook psn_rtl_*) |

## The dictionary

`novamessagedictionary.mdic`: magic `BMVN`, u32 count, then entries `u16 length, UTF-16LE text, u32 id low, u32 id high`.
It holds the **first line** of messages, keyed by the **next** id: short ids +1 (msg_530171's first line is entry 530172),
dialogue ids +10000 (msg_100010020030008 -> 100010020040008). It is the answer key that made the decoding possible.

## How the kanji were read

Every per-file glyph is a 21x21 picture; the same kanji is the same picture everywhere (hash of its pixels), 2,527 distinct.
1. Dictionary votes (learn_map.py): 1,743 pictures labelled from first lines. A first run that let pictures take kana
   labels in relaxed rounds was 12 % wrong on those (caught by a font-match audit) and was replaced.
2. Font matching (ocr_kanji.py, Yu Gothic Bold 32 px, ink box to 24x24, correlation): 75 % top-1 on known pictures; used
   only to propose 5 candidates.
3. Review (workflows psnova-kanji-review, -2): 898 pictures (784 unlabelled + 114 doubtful labels), each read by two
   independent readers (picture-first and sentence-first) with the sentences and the fan English; a judge for the 8
   disagreements. 813 high confidence; 85 medium/low are listed in the sheet's notes column ("check kanji reading").
   112 of the 114 doubtful vote labels were confirmed (2 corrected: 昏, 徳).
4. Spot check (workflow psnova-kanji-spotcheck): 100 unreviewed vote labels (50 where the font match disagreed, 50 at
   random), two independent checkers each: **all 100 confirmed by both**. The vote labels are reliable.

## Checks of the finished decode

- No unknown code and no unread picture in the 25,484 Japanese messages; no unknown code in the 20,056 English ones.
- 21,254 decoded first lines (85 %) equal a dictionary entry character for character; the remaining ones are messages
  the dictionary does not hold (a sample read as normal Japanese).

## Writing message files (the re-encoder, 2026-11-18 night)

Tools in `dev/psnova/rmdtext/`: `rmdwrite.py` (writer), `encode_text.py` (sheet cell -> .rmd), `arabic.py` (shaping +
right-to-left order), `build_l10n.py` (sheet column -> .rmd files -> overlay archive), `roundtrip.py` (proof), and
`dev/psnova/cpk_build.py` (rebuilds Sega's update archive with replaced/added entries). Arabic test lines: `ar_test1.json`.

Layout rules found from all 46,591 files (game + fan):
- header size hs: the smallest value >= end of the glyph table with hs % 0x80 == 0x10 (Sega's tool; the fan tool used
  0x50 and the game accepts it too). f[5] = 373 + own glyphs; f[6] = f[14] = 0x1e0 + W*H; f[7] = f[6] + 0x20; atlas size
  by own glyph count: <=5 128x32, <=10 128x64, <=16 128x128, <=20 256x64, <=50 256x128 (25-px slots).
- glyph record byte 2 is a character class (kanji 15, kana 12, small kana 11, Latin 10, digits 9, punctuation 1-8);
  byte 1 is the width (= advance).
- **texture chunk bytes 0x91-0x93 = a 24-bit texture ID, unique in every game file; the game caches textures by it.**
  The first in-game test copied one template's ID into every new file of the same atlas size, and those messages showed
  each other's pictures (an empty menu row, garbled help lines, a dialog showing slices of another message's glyphs).
  New files now take the ID (and the 16-byte IDs at 0xc0/0x190/0x120 and the value at 0x4c) of the message's original
  file; messages without an original get IDs from 0x800000 up (game IDs end at 0x525ff).
- The colour half of the DXT3 blocks is written white; only the alpha is drawn.
- A text that fills its region exactly has no terminator; bytes after the terminator are leftovers (179 game files).

Proofs: rebuilding every Japanese file from its parts gives byte-identical files (apart from those leftovers) with the
same font pixels; every sheet cell (25,483 Japanese, 20,055 English) encodes and decodes back to the same text; the
archive builder's no-change rebuild of the update archive reads back entry for entry (and keeps Sega's shared data).
A code review (workflow psnova-encoder-review, 30 passes; dump/psnova-l10n/build/encoder_review.json) confirmed 24
problems in the first version; all fixed (atlas packing limits, control codes inside Arabic lines, bidi neutrals and
brackets, hamza joining, extra letters پ چ گ ڤ ک ی ٱ, tag checks, text height with furigana, same-path guard).

Arabic in the game (test 1, 2026-11-18 23:30): letters join and lines read right to left in menus, help lines and
dialogue boxes (Segoe UI Bold 16 px, our own shaping; drawn as each file's own glyph pictures). Two drawing modes:
'form' (one picture per joined letter piece, <= 21 px, in the game's slots) and 'word' (one picture per word). Results
were mixed in test 1 only because of the shared texture IDs above.

**Test 2 (2026-11-19, unique texture IDs; shots in dump/psnova-l10n/ingame_text2/): both modes work everywhere seen.**
Menu rows (500001 form, 500002 word), help lines (170111 form, 170112 word, 170113 form), the name-confirmation dialog
(500111 word, two centred lines), the speaker label (30008 form, "ريتيا" above every dialogue box) and a 3-line dialogue
(100010020040008 word) all show joined, right-to-left Arabic. The English of the rest of the route (menus, descriptions,
dialogue, through our encoder) shows correctly. Not caught by the 100-frame screenshots: 100010020050008 (form) and
100010020070008 (word), short lines between shots. Default mode: 'word' (falls back to 'form' when the pictures do
not fit a 256x128 atlas).

## Not done yet

- What 0x8081 / 0x8099 do; whether the game needs the furigana readings for Arabic (no: drop them in translations).
- Writing .rmd files back (the re-encoder): needs the code table (done), new glyph pictures in each file's own atlas
  (DXT3 + Morton, known), and the glyph table records. Arabic needs joined letter forms drawn as pictures.
