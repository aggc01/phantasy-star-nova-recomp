# Phantasy Star Nova: Japanese drawn as pictures in UI textures (research 2026-11-19)

Question: with English or Arabic selected, the character creation screen still shows Japanese: the title banner
"キャラクタークリエイト" (with "CHARACTER CREATE" under it) and the button guide "SELECT カメラ初期化", "L R ズーム".
Message 430060 (カメラ初期化) is translated in our overlay, so these come from somewhere else.

**Answer: they are pictures inside UI textures (`.aif`), not messages.** The banner is in `tex_nova_ui_Title.aif`, the
guide labels are in `tex_nova_ui_common.aif`; both exist in the base archive and in Sega's 1.05 update archive (the
update's copy is the one the game loads). Our language overlays replace only `msg_*.rmd`, so these stay Japanese.
(The arena speaker name "フィルディア" is a different case: Shift-JIS strings in CSV tables, see
`dev/psn-logs/fildia-name-search.txt`; not covered here.)

Research only: nothing was installed, the game was not run. Work files: `dump/psnova-l10n/scratch/research/uitex/`.

## The texture format (.aif)

`.aif` = the same GXM texture chunk set as the message atlases (`text-format.md`): `" FIA"`, `FRap`, `Xgmi`, `FMA`,
`daeh`, `ffub`, `rdda`, 0x1e0 bytes of header, then the pixel data.

| Offset | Meaning |
|---|---|
| `0x91..0x93` | 24-bit texture ID (the game caches textures by it; keep each file's own ID) |
| `0xa0` (u8) | format: `0x10` BC1/DXT1 (4 bpp), `0x12` BC2/DXT3 (8 bpp), `0x14` BC3/DXT5 (8 bpp), `0x08` RGBA8888 linear (only seen in the fan rePatch's title texture) |
| `0xa8`, `0xaa` (u16) | width, height |
| `0xae` (u8) | bits per pixel (8 or 4) |
| `0x1e0..` | blocks in the Vita Morton (Z) order, exactly as the .rmd atlases (`rmdlib._perm`): y bit low, x bit high, non-square textures as square tiles side by side |

All UI textures are BC2 (DXT3) with full RGB colour (unlike the message atlases, whose colour half is white). Event
pictures use BC1/BC3. Decoder: `dump/psnova-l10n/scratch/research/uitex/tools/aiftex.py <out_dir> <file.aif>...`
(renders PNG; checked visually on 376 textures; every picture came out clean, so the block order is right).

Layouts: `ui_*.crbpj` (`CRBD` magic) with a `.crttl` naming the textures it uses, e.g. `ui_common.crttl` =
`tex_nova_ui_common.aif blank_thumbnail.aif blank_icon.aif tex_nova_ui_Title.aif` (`ui_menu_item` uses the same four).
A sprite cell stores its UVs as normalized float32 per vertex: `u0 v0 u0 v1 u1 v0 ...` (pixel = value x texture size).

## Where the two examples live

| What | Texture (archive copy the game uses) | Cell in the layout | Pixels |
|---|---|---|---|
| キャラクタークリエイト banner | `tex_nova_ui_Title.aif` 1024x512 BC2, update copy, texture ID `051e60` (base copy `03f17e`) | `ui_common.crbpj` (update) float UVs at `0x2c9174` | x1-217, y168-196 |
| "CHARACTER CREATE" under it | same texture, block of small English words | (not traced) | inside y~355-505 |
| カメラ初期化 | `tex_nova_ui_common.aif` 1024x1024 BC2, update copy, ID `0515fe` (base `03f28c`) | `ui_common.crbpj` (update) `Cast_Camera` cell `0x259198`; `ui_menu_item.crbpj` (base only) `0x24e9d8` | x925-1023, y636-657 |
| ズーム | same | `0x25c7d4` (ui_common), `0x252014` (ui_menu_item) | x971-1023, y657-678 |

The other `Cast_Camera` cells of the same guide column (update `ui_common.crbpj`): `0x258c14` x917-986 y678-699 (武器回転),
`0x25c168` x987-1023 y678-699 (回転), `0x25a22c` x922-1023 y595-615 (パーツ移動小), `0x25cf34` x907-1023 y615-636 (パーツ45度回転),
`0x25a98c` x938-1023 y574-595 (パーツ拡大), `0x25d4b4` x852-937 y574-595 (パーツ移動), `0x25eb24` x854-922 y636-657 (一括回収, update only).
Page-title banner cells of `tex_nova_ui_Title` (update `ui_common.crbpj`, all x from 1): `0x2c6ca0` y29-56, `0x2c69f0`/`0x2c7ea4`
y56-84, `0x2c7ffc` y84-112, `0x2c8ec4` y140-168, `0x2c9174` y168-196 (character creation), `0x2c9c5c` y196-224, `0x2ca1bc`
y224-252, `0x2ca5b0` y252-280, `0x2c880c` y280-307.

Pictures: `uitex/png/patch/tex_nova_ui_Title.png`, `uitex/png/patch/tex_nova_ui_common.png`, zoom of the guide column
`uitex/sheets/guide_zoom.png` (all under `dump/psnova-l10n/scratch/research/`).

## Scope: which UI textures hold Japanese

Rendered: every texture named in a `.crttl`, all `tex_*`, `ui_*`, `UI_*`, `nova_*`, tutorials, credits, loading screens,
event pictures, captions (base 363 + update 13), plus a sample of 420 of the 2,995 item/skill icons. Read by eye from
contact sheets (not OCR, so counts are +/- a few).

| Group | Files | With Japanese | What | Contact sheet |
|---|---|---|---|---|
| Menu title banners | `tex_nova_ui_Title.aif` | 1 (about 60 labels) | every menu's page title (装備, 武器, スキル, キャラクタークリエイト, ...) in cyan gothic; an English small line for each already exists in the same texture | `sheets/jp_core.png` |
| Common UI parts | `tex_nova_ui_common.aif` | 1 (about 25 labels) | button guide column (9 labels), orange touch buttons カメラ 回転 拡縮 アタッチ 決定 回転1 回転2, yellow tags 装着 右装着 左装着 装備 装備不可 ステルス | `sheets/jp_core.png` |
| Chapter title cards | `tex_Chapter.aif` | 1 (24 Japanese words) | big Japanese chapter names assembled from word pieces; English subtitles already in the texture | `sheets/chapter_top.jpg` |
| Cutscene caption fonts | `MP01_020_040_Caption.aif`, `TE01_020_040_Caption.aif` | 2 | a kana/kanji glyph grid for one scripted caption (not in any .crttl; how it is used is open) | `sheets/jp_core.png` |
| Loading screen | `load024.aif` | 1 | the Vita control diagram 基本操作 (all labels Japanese) | `sheets/load.jpg` |
| DLC cast card | `ev_dlc_104.aif` (update) | 1 | five character + voice actor names | `sheets/events.jpg` |
| Title screen | `nova_ui_title.aif` | 1 (tiny) | "ファンタシースター ノヴァ" small katakana; the menu words are English | `sheets/core.jpg` |
| Tutorial pictures | `ui_tut_*.aif` 512x256 (134 base + 5 update) | **83** | screenshots of Japanese menus, Japanese HUD class names, red Japanese callout labels | `sheets/jp_tutorials.png` (list: `sheets/jp_tutorials.txt`) |
| Credits | `Credit_*.aif` (71) | 0 shown | 0060-0070 are placeholders (リージョン名) and almost certainly unused | `sheets/credits.jpg` |
| Event pictures | `ev_eventImages*.aif` (110), `ev_00x` | 0 shown | two placeholders with 仮 (006, 047) | `sheets/events.jpg` |
| Icons | `ico*.aif` (2,995, 64x64) | 0 in the sample | one placeholder "DLC(仮)" | `sheets/icons_sample.jpg` |
| Other UI | `ui_field`, `tex_nova_ui_Class`, `tex_nova_Result`, `tex_nova_ui_emergency`, `UI_ChainLink`, `UI_ItemShop`, `UI_WorldMap_Base`, `MAP01`, `minimap_icon`, `ui_tut_common` | 0 | English or no text | `sheets/core.jpg` |

**Total: about 92 textures, 9 of them core UI and 83 tutorial pictures.** The core 9 hold every Japanese picture the
player sees on menus; the tutorials appear only inside tutorial pages.

All sheets are under `dump/psnova-l10n/scratch/research/uitex/sheets/`; full-size PNGs of every texture under
`uitex/png/base/` and `uitex/png/patch/`.

The fan rePatch (Arks-Layer English) does **not** translate UI textures: its 432 textures equal Sega's update byte for
byte, except a recoloured title screen (`nova_ui_title.aif`, stored as RGBA8888 `0x08`, "English patch [DEBUG BUILD]"
added) and one icon. It also drops `tex_nova_ui_common.aif` from its patch archive. Its title file does show that the
game accepts a changed format in the same header, but nothing there is reusable for us.

## How a replacement works (and a proof)

1. Decode the texture (update copy if one exists, else base) with `aiftex.py`.
2. Redraw each Japanese label inside its own cell rectangle (table above): clear the cell, draw the English or Arabic
   text in the same colours (button guide: white bold, 1 px near-black outline, right aligned; banners: cyan gothic).
   The layout cells and their on-screen quads stay unchanged, so the text must fit the old rectangle.
3. Re-encode BC2 and put the blocks back in Morton order; keep the 0x1e0 header unchanged (size, format and the file's
   own texture ID). Prototype: `uitex/tools/aif_encode_test.py` (Pillow's DXT3 encoder for the colour half, our own
   exact 4-bit alpha: Pillow 12.2's alpha half came out shifted in about 2 % of pixels). Round trip of
   `tex_nova_ui_common.aif`: alpha exact, mean colour error 0.5/255 (441 of 513k visible pixels off by more than 24;
   a better block encoder would remove those).
4. Put the new `.aif` into the folder of replaced files and build the language overlay archive with
   `dev/psnova/cpk_build.py` (it replaces any entry by name, the same way `build_l10n.py` adds the messages), one per
   language in `dump/decrypted/PCSG00351/lang/<en|ar>/`.

Proof of concept (not installed): `uitex/tools/poc_redraw_guide.py` redraws カメラ初期化 -> "Reset Camera" and ズーム ->
"Zoom" in their cells (Segoe UI Bold 15 px), encodes `uitex/enc/poc_tex_nova_ui_common.aif` (1,049,056 bytes, same as
the source, ID `0515fe` kept) and decodes it again: `uitex/enc/poc_guide_decoded_zoom.png` shows clean English labels
next to the untouched Japanese ones.

Limits and notes:
- Cell widths are small (ズーム 52 px, カメラ初期化 98 px, each 21 px tall). Short English fits; longer words need a
  smaller size or abbreviations. Making a label wider means editing that cell's UVs and its quad size in the `.crbpj`
  (the UV floats are found; the quad vertex positions are not traced yet).
- Arabic: shape and order with `dev/psnova/rmdtext/arabic.py` and draw with the Arabic font from `dev/psnova/fonts.json`;
  the guide column is right aligned already, which suits Arabic.
- Replace the **update** copies of `tex_nova_ui_common.aif` and `tex_nova_ui_Title.aif` (they win over base; their
  content and IDs differ from base: the update adds 一括回収, オペレーターの交代, コア精錬所). `tex_Chapter`, the captions,
  `load024` and the tutorials exist only in base; added to the update overlay they win the same way (as the messages do).
- Base `ui_menu_item.crbpj` uses the same texture cells as `ui_common.crbpj`, so one texture fix covers both screens.

## Recommended plan

1. **Core UI first (9 textures, covers the reported screens):** `tex_nova_ui_common` (guide column, orange buttons,
   yellow tags) and `tex_nova_ui_Title` (all banners; the big Japanese line can simply become the English line in the
   same style, since every banner already has its English name in the small line), then `tex_Chapter`, `load024`,
   `nova_ui_title` (tiny katakana), `ev_dlc_104`. Turn `poc_redraw_guide.py` into a tool driven by a table
   (texture, cell rectangle, English, Arabic, style), so both languages build from one sheet like the messages.
2. Add the step to `build_l10n.py` (or a sibling) so the overlay build writes the textures next to the messages
   before `cpk_build.py` runs; check by decoding the built archive's textures back to PNG.
3. One in-game check on the character creation screen and a menu banner (needs the machine free and my go).
4. **Tutorials (83 pictures) later and separately:** most are screenshots of Japanese menus. Retaking them from our
   English/Arabic build gives the cleanest result (same 512x256 framing); red callout labels alone could be painted
   over. Decide after step 3.
5. Leave placeholders (credits 0060-0070, 仮 pictures, DLC(仮) icon) unless one is seen in the game.
6. Open: how the two `*_Caption.aif` glyph grids are used (scripted caption in MP01_020_040 / TE01_020_040); whether any
   3D model textures (`.axs`) carry Japanese signage (not scanned).
