# RMD message format (Phantasy Star Nova, PCSG00351)

Status: partial. The container, header and file size rules are decoded. The glyph table
and the atlas pixel layout are NOT decoded, so no message can be drawn yet.

Files: `rmd.py` (info, atlas), `extract_pairs.py` (makes the 26 sample files), `samples/`
(6 atlas PNGs). Samples are in the scratchpad `rmd-samples/ja` and `rmd-samples/en`:
13 same-name pairs (JP from patch105, EN from repatch_patch), plus 3 short files.

## Header (little-endian)

| offset | size | meaning | status |
|---|---|---|---|
| 0x00 | 4 | magic `" DMR"` | confirmed, all 26 files |
| 0x04 | 4 | data block offset (same value as 0x0c) | confirmed, all files |
| 0x0c | 4 | data block offset. Varies by file: 0x11e0 to 0x2110 range | confirmed: data_off + data_size = file size (except the EN extra bytes below) |
| 0x10 | 0x1c | ident string `FontConverterDll_1.0.1.3_rc6` | confirmed |
| 0x30 | 4 | 0x80 in all files | confirmed constant |
| 0x34 | 4 | 0x100 in all files | confirmed constant |
| 0x38 | 4 | 0x180 (JP), 0x140/0x1c0 (EN) | guessed: a language-specific size, meaning unknown |
| 0x3c, 0x40 | 4 each | data_off - 0x10 | confirmed relation, meaning guessed |
| 0x44 | 4 | count, 0x175 to 0x187 across files | guessed; identical in all 13 JP/EN pairs, so it is not text-dependent |
| 0x48 | 4 | data block size (0x11e0, 0x21e0, 0x41e0, 0x81e0) | confirmed |
| 0x4c | 4 | data block size + 0x20 | confirmed in all files |
| 0x50, 0x54, 0x58 | 4 each | 21, 25, 25 in all files | confirmed constant, meaning guessed (glyph cell size?) |
| 0x68 | 4 | data block size (same as 0x48) | confirmed |
| 0x6c | 4 | 0x13269dd in all files | confirmed constant, meaning unknown (maybe a version or hash) |
| 0x70 | 4 | atlas width | confirmed by size check (see below) |
| 0x74 | 4 | atlas height | confirmed by size check |
| 0x78 | 4 | 1 in all files | confirmed constant, meaning unknown |
| 0x90 | 8 | 64-bit message ID = the number in the file name | confirmed (0x90 low dword, 0x94 high dword) |
| 0x9c | 4 | float, e.g. 252.0 / 0.0 / 286.0 | guessed: text box width |
| 0xa0 | 4 | float, e.g. 61.0 / 21.0 / 41.0 | guessed: text box height |

## Data block

Starts at data_off (0x0c) and runs to end of file (except the EN extra bytes below).
Its size is `0x1e0 + atlas_w * atlas_h` (confirmed for all 26 files).

- First 0x1e0 bytes: a chunk list. Tags seen: `" FIA"`, `" FRa"`, `"ATIV"`, `"Xgmi"`,
  `" FMA"`, `"daeh"`, `"ffub"`, `"rdda"`. Each chunk has a 4-byte tag, a size and the size repeated
  (for example `" FIA"`, 0xf0, 0, 0xf0). The meaning of the chunks is not decoded.
- Then the atlas: W*H bytes. The atlas size is set by 0x70 and 0x74. Sizes seen:
  128x32, 128x64, 128x128, 256x64, 256x128 (8 bpp = 1 byte per pixel in size).
  The atlas starts at data_off + 0x1e0. This start is confirmed by size only; the
  pixel content is not confirmed.

## Glyph table (between 0x110 and data_off)

Not decoded. Observations:

- Values are 16-bit. In the JP file 100139 the 16-bit values near 0x110 are mostly 0x01b2 to 0x01e5.
  In the EN file they are mostly 0x0080 to 0x00b9, with `0x01e8` at regular spacing.
  Those patterns are not yet understood (glyph IDs? widths? or something else).
- Size from 0x110 to data_off: JP 100139 gives 0x1f80 = 8064 = 384 x 21, but EN 100139 gives 0x2000,
  which is not a multiple of 21. So the record size is not confirmed.
- Not checked: whether a message is a sequence of 16-bit glyph references (the task hypothesis).

## Pixel format

Not confirmed. Tests on JP 100139 (atlas 256x128 at file offset 0x2270):

| reading | result |
|---|---|
| 8 bpp, row-major, 256 px rows | vertical bands and sheared glyph fragments. Not readable. |
| 8 bpp, Morton (Z-order) swizzle | blocks with some glyph-like shapes; large noise areas. Not readable. |
| 8 bpp, 16x8 byte tiles | left part shows glyph-like shapes; right part is bands. Not readable. |
| 4 bpp nibbles, 512 px rows | glyph-like horizontal lines. Not readable. |
| 16-bit texel, low byte only, 256x64 | the top-left shows glyph-like cells; most of the image is still bands. |
| 16-bit texel, high byte only, 256x64 | glyph-like cells too; not readable. |

Byte statistics: stride-16 equality is the strongest repeat (about 25 % of bytes match at stride 16).
Common byte values: 0 (about 59 %), 0x55, 0xff, 0x20, 0x01, 0x40. Values such as 0x77, 0x99 and 0xff
suggest that a nibble may be a pixel unit.

## Proof images (`samples/`)

Six atlas PNGs were written with the 8 bpp linear reading (`rmd.py atlas`): en/ja for msg 360781
(128x128), 60064 (256x64) and 501000020220030 (128x64).

What was seen: all six are grey vertical bands with fine bright fragments. The JP and EN
images look the same at this size. No readable Latin letters and no kana/kanji could be
identified. So the PROOF FAILED for this reading. The images are not evidence of a decode.

## Still unknown

1. Pixel layout of the atlas (swizzle or bit depth). The next test: a font sheet with a known
   glyph should show a clean grid; try the PSP/Vita swizzle used by the game's texture code and 4-bit
   texel sheets with a palette.
2. Glyph table record size and fields (glyph rectangles, advances, IDs).
3. How text references glyphs (16-bit glyph refs with `0x01e8` separators in EN?).
4. Meaning of 0x38, 0x44, 0x50-0x58, 0x6c, 0x78, the floats at 0x9c/0xa0.
5. 64 extra bytes at the end of 8 EN files (sizes 12528 and 12656 bytes); the data block
   ends 0x40 bytes before EOF in those files. Not explained.
6. What is needed to WRITE a new .rmd (for an Arabic translation): the atlas encoding, the glyph
   table, the chunk list in the first 0x1e0 bytes, and the 0x6c field. None is decoded.

## Sample inventory

26 extracted files in the scratchpad `rmd-samples/`: 13 JP, 13 EN, same names, sizes
12528 to 25264 bytes (and 16816 for 501000020220030). Header checks: 26 files,
all with data_off + data_size = EOF except the 8 EN files noted above (the 64 extra bytes).
The 501000020220030 "id != name" flag is only because the ID is 64-bit.
