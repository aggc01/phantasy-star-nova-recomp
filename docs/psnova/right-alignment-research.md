# Right-aligned Arabic: how the game places text, and the best way to right-align it (research, 2026-11-19)

Read-only reverse engineering of the 1.05 program (`dump/decrypted/PCSG00351/recomp/game_part*.c`, one C function per guest
address, the ARM instruction as a comment on every line) plus the game data. No game was run (the user was play-testing).
Work scripts were in the session scratchpad only; nothing in the build, the pack or the tools was changed.

## Summary

- **The game can right-align text natively.** Every text box (the UI's TextBox cast) has an alignment field: box+0x94,
  0 = left, 1 = centre, 2 = right. The routine that places each line (`fn_81905ae0`) does
  `x = 0` / `x = (box width - line width * scale) / 2` / `x = box width - line width * scale`.
  Line widths come from the glyphs actually laid out (per line, max x - min x of the glyph quads), not from the
  message file's header.
- **The alignment comes from the UI layout, not from the message.** It is the `Align` property of the text box in the UI
  project files (`*.crbpj`, CRI "CRBD" format): Align 1/2/3 -> 0/1/2. A box with no `Align` property is left-aligned. The
  message file (.rmd) has no alignment field and no alignment control code.
- **The header float at 0x9c is not a width and is not read by the text-box path.** It is 0 exactly when the file has
  no own glyphs (all 46,591 game and fan files); its meaning is still unknown.
- **Recommendation: (b) a small runtime hook** that turns "left" into "right" for messages we mark as Arabic, with the
  mark carried in the text itself (an unused, game-ignored control code `0x8095` at the start of every Arabic message,
  written by our encoder). One instruction hook at 0x81905b10 and one entry hook on the two message-layout functions.
  Centred boxes stay centred, right boxes stay right, everything else (Japanese, English, numbers) is untouched.
  Confidence: high that the mechanism works as described (all addresses and offsets read from the code); medium on
  details that only a run can show (that every Arabic menu/help/dialogue box is this TextBox class, and that each box's
  width matches its visible frame).
- Side findings that matter for the translation (below): **0x8082 is "colour back to white", not "end of text"**, and our
  reader stops there, so **179 game messages lost the text after it in the sheet** (e.g. msg_21756 lost its last line
  よろしいですか？). 0x8081 xx is a text colour. Own-glyph codes are only right below 111 own glyphs. A message draws at
  most 128 glyphs.

## 1. The header fields near 0x90-0xb0

Checked over every file (21,377 base + 5,158 update + 20,056 fan English = 46,591):

| Offset | What | Evidence |
|---|---|---|
| 0x90 u64 | message id | (known) |
| 0x98 u32 | always 0 | 46,591 / 46,591 |
| 0x9c f32 | **0.0 exactly when the file has no own glyphs** (first glyph record width byte = 0), non-zero otherwise | 46,591 / 46,591, in the game's files *and* the fan tool's files |
| 0xa0 f32 | text height (21 + 20 per extra line; furigana lines more) | (known) |
| 0xa4..0xaf | always 0 | 46,591 / 46,591 |
| f[19..23] (0x7c..0x8f) | always 0 | 46,591 / 46,591 |

0x9c is **not a line width**: against widths computed from glyph advances (max line width, sum of advances) only 7 of
4,000 files matched, by chance. Typical values: 18 (most files with one own glyph), 19, 21, 22, 24, 25; 85-345 for
files with many own glyphs. Tested and rejected: sum of own advances, max own advance (12 %), own-glyph count, last own
glyph's atlas u/v in pixels, glyph ink width. It is a value the font converter derives from the file's own glyph set;
what exactly is still open, and it does not matter for alignment: **the text box path traced below never reads the
message header at 0x9c or 0xa0** (it measures the laid-out glyphs). Consistent with that, our new files written with
0x9c = 0 drew correctly in tests 2-4.

## 2. How a message is decoded, laid out and drawn (guest addresses, 1.05)

### 2.1 Text decoding (the real rule behind the "u16 codes")

All five decoding sites (`fn_817e65fc` twice, `fn_817e8410`, `fn_817e850e`, `fn_817e882e`; found by the bit-insert
pattern `bfi rX, rY, #7, #8`) read the text the same way:

- byte b < 0x80: a one-byte code b (furigana readings use these).
- byte b >= 0x80: code = (b & 0x7f) | (next byte << 7) (so u16 `0x0391` -> 0x191 = 401, `0x8080` -> 0x4000).
- code with bit 0x4000 set: control code (u16 0x80XX -> 0x4000 + (XX & 0x7f)).
- code 1..0x190 (400): BasicCharSet glyph record (code - 1) (`fn_817e6c66` at 0x817e6d68 `cmp r0, #0x190`); above 0x190:
  this file's own glyph record (code - 401). This is why the BasicCharSet order looked "gappy": u16 codes whose low
  byte is below 0x80 cannot be written in the two-byte form.

**Consequence for our writer:** own glyph i is code 401 + i, written as two bytes `0x80 | (code & 0x7f), code >> 7`.
That equals our u16 `0x391 + i` only for i < 111; at i = 111 the right bytes are `80 04`, our writer would write `00 04`
(a 0x00 byte = end of text). Japanese files have at most ~50 own glyphs, and our phrase/word modes stay far below 111,
but the writer should refuse (or encode correctly) i >= 111.

### 2.2 Control codes (dispatcher `fn_817e65fc`, `tbh` at 0x817e6634 over code - 0x4000, 0..0x22)

| u16 in file | Internal | What the game does (case address) |
|---|---|---|
| 0x8080 | 0x4000 | new line: marks the last glyph record as line end (record +0x64 = 1), pen x = 0, y += line step (0x817e667e) |
| 0x8081 xx | 0x4001 | **text colour** id xx (1 black, 2 blue, 3 red, 4 purple, 5 green, 6 cyan, 7 yellow, 8 white, 9 gray, 10 orange, 11 black_g; others -> 8): colour = u32 at 0x823b4b40 + 24*xx, names at 0x823b4a78.. (0x817e688c). Game files use 03 red (497), 07 yellow (153), 06 cyan (138) |
| 0x8082 | 0x4002 | **colour back to the default (white)**, then the text continues (0x817e68b4). Not an end code. |
| 0x8090 .. 0x8091 | 0x4010/0x4011 | furigana start / end (0x817e67aa) |
| 0x8092 | 0x4012 | a number from another game table (`fn_815949ee`), drawn as digits |
| 0x8093 xx | 0x4013 | a string slot (`fn_819568f4`, e.g. a name), its u16 characters mapped by `fn_8194f90e` |
| 0x8094 xx yy | 0x4014 | a number slot: value xx from `fn_8195688a`, at least yy digits |
| 0x8099 xx | 0x4019 | one inserted glyph: xx -> an id through the table in `fn_817e63a4`, then `fn_815949f4` (probably a button/icon picture; guessed) |
| 0x8083-0x8088, 0x808c, 0x808e, 0x80a0 | 0x4003-0x4008, 0x400c, 0x400e, 0x4020 | skip 4 parameter bytes, nothing else (0x817e68c6) |
| 0x808a | 0x400a | skip 2 parameter bytes (0x817e68d8) |
| 0x8098, 0x80a1 | 0x4018, 0x4021 | skip 1 parameter byte (0x817e68e0) |
| **0x8089, 0x808b, 0x808d, 0x808f, 0x8095-0x8097, 0x809a-0x809f, 0x80a2** (and anything above 0x80a2) | 0x4009 .. 0x4022 | **no operation, no parameter** (jump targets 0x817e68ea.. are a plain `b 0x817e67a6`). None of them occurs in any game file. |

### 2.3 Layout of one message into a text box

- Text box requests are run by a worker (`fn_8195148e`): type 1 = a message by id -> `fn_819511ce` / `fn_81950eee` ->
  **`fn_817e850e` / `fn_817e882e`** (the same routine in two variants); type 2 = a u16 string through BasicCharSet
  (`fn_8194f956`, player names and the like); type 4 -> `fn_817e8b68`.
- `fn_817e850e(r0 = font context, r1 = message object, r2 = furigana flag, r3 = parameters (+0x10 id, +0x24 line
  spacing), [sp+0] = output block)`. The text pointer is `[obj+8] + [[obj]+8]`. The **output block is the text box +
  0xa4** (glyph count at +0, glyph index per glyph at +0x6d8, 0x68-byte glyph quads at +0x8d8, flags at +0x3cd8; the same
  three fields are box +0x77c / +0x97c / +0x3d7c in the box constructor). It stops after 128 glyphs (`cmp r0, #0x80`).
- Per glyph `fn_817e6c66`: quad x0 = pen x, x1 = pen x + the glyph record's **width byte** (record byte 0 = the advance),
  then pen x += advance (plus the font's `HalfWordSpace` value for some glyphs). Line step = glyph height + LineSpace.
- `fn_817e8410` counts a message's glyphs (also capped at 128).

### 2.4 The text box (the UI TextBox class)

- vtable 0x8241a0ac (symbol 0x8241a0a4), constructor `fn_819082ec`. Fields: +0x50/+0x54 position offset, +0x58/+0x5c
  box width/height, +0x64 line count, +0x6c FontSize, +0x70 = 21 (base size), +0x74 scale = FontSize/21, +0x78
  LineSpace, +0x80/+0x84 text size, +0x88/+0x8c scaled text size, **+0x94 Align (0 left, 1 centre, 2 right)**,
  **+0x98 vAlign (0 top, 1 middle, 2 bottom)**, +0x3e38 line table (12 bytes per line: end glyph index, width,
  height; at most 32 lines), +0x3fb8 line count.
- `fn_81908e56` (vtable +0x80) reads the layout properties by name: `FontSize` -> +0x6c, `LineSpace` -> +0x78, `Align`
  1/2/3 -> vtable +0xbc (`fn_8176ba7c`: `str r1, [r0, #0x94]`) with 0/1/2, `vAlign` 1/2/3 -> vtable +0xc0 (`fn_81fe09a4`:
  `str r1, [r0, #0x98]`), `Ruby` -> +0x62. Without an `Align` property the constructor's 0 (left) stays.
- `fn_81908c78`: set message by 64-bit id (r2:r3); checks that `msg_%llu.rmd` exists (`fn_81956b96`) and queues it.
- `fn_81909050`: after layout, per line: width = max x1 - min x0 of its glyph quads, height likewise (line table above);
  whole text size -> +0x80/+0x84.
- `fn_81905bf2` (draw): scale = min(box width / text width, box height / text height, 1) (shrink to fit, never grow),
  then for line 0 and every following line calls **`fn_81905ae0`** (6 call sites).
- **`fn_81905ae0(r0 = box, r1 = out x,y, r2 = line, s0 = box width, s1 = box height, s2 = scale)`**:
  - 0x81905b10 `ldr.w r2, [r5, #0x94]` (align); 0: x = 0; 1: x = (s0 - width[line] * s2) * 0.5; 2: x = s0 - width[line] * s2
    (width[line] = float at box + 0x3e3c + 12 * line)
  - 0x81905b58 `ldr.w r2, [r5, #0x98]` (vAlign); 1: y = (s1 - box+0x8c) * 0.5; 2: y = s1 - box+0x8c
  - x += box+0x50, y += box+0x54.

So a right-aligned box right-aligns **each line separately**, measured on the real glyphs. Our Arabic lines (already in
visual order) would sit flush right exactly as the game's own right-aligned numbers do.

## 3. Where boxes get their alignment and width

- UI projects: `*.crbpj` in both archives (101 in the base, 9 replaced by the update: ui_common, ui_field, ui_title,
  UI_ChainLink, UI_WorldMap, nova_ui_Result, 3 tutorials). Format "CRBD" (CRI). Box sizes are in the cast data;
  text-box options are **user parameter blocks**:
  `u32 count, u32 0x10 (types), u32 off_values, u32 off_names; u8 type[count] (padded to 4); u32 value[count];
  u16 count, u16 1, u32 name_offset[count] (from the names table), names`.
  Example ui_field.crbpj (update) at 0x1ff70: count 1, type 1, value 3, name "Align".
- Counts (update archive's 9 projects): `Align` on 476 casts: **3 = right on 320**, 2 = centre on 153, 1 = left on 3;
  `Priority` alone on 2,542, FontSize/LineSpace/vAlign/Ruby on fewer. Base archive: right 545, centre 298, left 6.
  The right-aligned boxes are mostly numbers (result screen, counters).
- **Most left-aligned text boxes have no `Align` property at all** (left is the default), so a data-only change cannot
  just flip a flag: it would need a new parameter block inserted into each box's node (offsets of the whole file move),
  and we would have to know which box shows which message. Only the 3 explicit `Align = 1` boxes could be flipped in
  place.

## 4. Options, ranked

### (b) Recommended: runtime hook, Arabic marked in the message text

1. **Mark**: the encoder writes the no-op control code `0x8095` (bytes `95 80`) as the first two bytes of every Arabic
   message (`encode_text.py`, `lang == 'ar'`, before the text in `_build`). The game ignores it in all five decoders
   (they all hand control codes to `fn_817e65fc`, where 0x4015 is a plain no-op, no parameter bytes); it is not a glyph,
   so it does not count against the 128-glyph limit. Our reader already treats it as `('ctl', 0x8095, b'')`; the sheet
   tag would be `{8095}`. No game file uses 0x8095.
2. **Hook A** (entry hook, `HOOKS`), on `0x817e850e` and `0x817e882e` (same name twice):
   `out = RD32(sp)` (the output block = box + 0xa4), `obj = r1`, `p = RD32(obj + 8) + RD32(RD32(obj) + 8)` (both
   non-zero, as the function itself checks); remember `rtl[out] = (RD8(p) == 0x95 && RD8(p + 1) == 0x80)`. Runs for
   every message laid out, so a box that later gets a non-Arabic message is cleared. Optionally also clear on
   `0x8194f956` entry (`out = r3`) for boxes that switch to a typed string.
3. **Hook B** (instruction hook, `IHOOKS`) after **0x81905b10** `ldr.w r2, [r5, #0x94]` (reg 2, r5 = the box):
   `if (c->r[2] == 0 && rtl[c->r[5] + 0xa4]) c->r[2] = 2;` - only "left" becomes "right"; centre and right are left
   alone, guest memory is not written.

Sketch (not applied; packs/PCSG00351/hooks.c and pack.toml belong to another session, and HOOKS need a recompile):

```c
/* Arabic right alignment (docs/psnova/right-alignment-research.md): text-output block -> Arabic mark */
#define PSN_RTL_N 1024
static uint32_t psn_rtl_key[PSN_RTL_N]; static volatile uint8_t psn_rtl_val[PSN_RTL_N];
static int psn_rtl_slot(uint32_t k, int add) {
	unsigned h = (k >> 2) * 2654435761u % PSN_RTL_N;
	for (int i = 0; i < PSN_RTL_N; i++, h = (h + 1) % PSN_RTL_N) {
		if (psn_rtl_key[h] == k) return (int)h;
		if (!psn_rtl_key[h]) { if (!add) return -1; psn_rtl_key[h] = k; return (int)h; }
	}
	return -1;
}
void recomp_hook_psn_rtl_mark(Cpu *c) {          /* entry of fn_817e850e / fn_817e882e (message layout) */
	uint32_t out = RD32(c->r[13]), obj = c->r[1], hdr = obj ? RD32(obj) : 0, base = obj ? RD32(obj + 8) : 0;
	uint32_t p = (hdr && base) ? base + RD32(hdr + 8) : 0;
	int rtl = p && RD8(p) == 0x95 && RD8(p + 1) == 0x80;
	int s = psn_rtl_slot(out, rtl);
	if (s >= 0) psn_rtl_val[s] = (uint8_t)rtl;
}
void recomp_ihook_psn_rtl_align(Cpu *c, int reg) {   /* after 0x81905b10 ldr.w r2, [r5, #0x94] (line origin) */
	if (reg != 2 || c->r[2] != 0) return;
	int s = psn_rtl_slot(c->r[5] + 0xa4, 0);
	if (s >= 0 && psn_rtl_val[s]) c->r[2] = 2;
}
/* pack.toml: HOOKS += "0x817e850e:psn_rtl_mark 0x817e882e:psn_rtl_mark"   IHOOKS += "0x81905b10:psn_rtl_align" */
```

Why the mark is in the text and not in the header: the hook sees exactly the text pointer the game uses; where the
file header sits relative to it in memory was not established statically (an unused header field such as 0x98 would
work too once a run shows `[obj]`/`[obj+8]` point into the loaded file).

Variant (b'), quickest to try: hook B alone with a setting (e.g. an env/ini switch) that right-aligns **every**
align-0 box in the Arabic build. No encoder change; but Latin-only and number labels that were designed left-aligned
would move too.

What a first test should check (one run, after the user's play test): the class-select menu rows, a help line
(170111), the name dialog (500111, must stay centred), the speaker label and a 3-line dialogue (each line flush right).
Risks only a run shows: a box whose width is larger than its visible frame (text would sit at the far right of the
box, not of the frame); text drawn by another class than this TextBox (would stay left).

### (a) Data only

- In the message file: not possible. No header field is read for placement and no control code changes x (table 2.2).
- In the UI projects: flip `Align` to 3 for the boxes that show Arabic. Only 3 boxes have an explicit `Align = 1`;
  every other left-aligned box would need a parameter block added (a crbpj writer that rebuilds offsets, plus a map of
  which box shows which message). High effort and risk; per box, not per message.

### (c) Padding fallback

Prepend to each Arabic line an empty own glyph whose advance byte is (box width - line width) px (0-255, exact
pixels). Needs each message's box width (only known at run time, and a message can appear in several boxes); if the
padded line is wider than the box, the game shrinks the whole text (scale = box / text). Only worth it if hooks are
ruled out.

## 5. Side findings for the translation tools

1. **0x8082 is not "end of text".** The game resets the colour and keeps reading until a 0x00 byte. `rmdlib.tokens()`
   stops at 0x8082, so the **179 game files with text after it** (the "leftover bytes" in text-format.md) lost real
   text in the sheet. Example msg_21756: the game shows このクエストを開始します。 / (red) パーティーメンバーが選ばれていません。 /
   (white) よろしいですか？ - the sheet has only the first two lines. Others: msg_10910, msg_10915, msg_230062 (two
   red parts), msg_230063. The `{end}` tag (build_sheet.py) should become "colour reset" and the reader should continue;
   the round-trip proof then covers those bytes too.
2. **0x8081 xx is a colour** (ids above), not a layout code. The encoder keeps a 0x8081 at a line start in place (fine:
   the whole line is coloured) but reorders mid-line codes as neutral placeholders, which can move a colour start and
   its 0x8082 reset apart in an Arabic line; a coloured part should move together with its words.
3. **Own-glyph codes**: correct only for own glyph index < 111 (section 2.1).
4. **At most 128 glyphs per message** (layout and count both stop at 0x80), spaces and basic characters included, and
   at most 32 lines per text box. Arabic 'form' mode (one glyph per letter piece) can pass 128 on long help texts;
   'phrase'/'word' modes stay well below.
5. The 2-column race list (ذكر ... بشري) is two separate boxes; right alignment does not swap columns.

## Proven vs not proven

Proven from the code/data: the decoding rule, the control-code table, the per-glyph x rule, the text box fields and the
alignment formula, the `Align` property mapping, the crbpj parameter counts, 0x9c = 0 iff no own glyphs, 0x8082
behaviour and the 179 truncated messages. Strongly supported, to confirm in a run: output block = box + 0xa4 for
message layouts (three field offsets agree), the text pointer formula inside the hook, that menu/help/dialogue boxes
are this class. Guessed: 0x8099 = an inline button/icon; what 0x9c measures.
