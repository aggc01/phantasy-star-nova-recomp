# Movie cleaning v3: per-line masks (2026-11-19)

The user reported, while playtesting the v2 movies: "the Japanese subtitles are showing for a split second before
fading out". This is flaw 1 of v2 (localization-notes.md, "Movies v2 installed and tested in the game"). v3 fixes it.
The 8 story movies are cleaned again into `dump/psnova-l10n/movies_clean_jp_v3/`. **The archive is NOT built or
installed.** The main session does that.

## Why v2 left text

v2 built a new mask for every frame from pixels that are white in at least 8 of the 11 frames around that frame. In the
original movies most lines switch on and off without a long fade. So in the first and last 2-3 frames of every line,
fewer than 8 of the 11 frames hold the text. The mask there was empty or partial, and the whole line (or half of it)
stayed on screen for about 2 frames at each end of every line. Example: MP00_000_000 frames 895-896 still show
"全宇宙の平和を……『ダーカー』", and frame 909 shows the next line with half of it removed. Frames that start a new
line where the previous one ended (a direct change) were hit the same way.

## What v3 changes (dev/psnova/remove_jp_subs_v3.py, new file; v2 untouched)

1. **Detection is v2's.** It uses the same top-hat whiteness, the same persistence test, the same vertical-structure
   removal, presence (kept pixels > thr, smoothed), the same union with the fan copy's English line, and the same bands
   and thresholds.
2. **Lines.** The "core" frames (kept pixels > thr) inside the present frames are split where the persistent mask
   changes abruptly: more than 30 % of the pixels vanish or appear from one frame to the next. Short pieces of fewer
   than 6 frames (ramps at a line's start, flashes) join the neighbour whose mask contains theirs. Pieces of the same
   text split by a gap of 6 frames or less are merged again (mask IoU > 0.6). A present run with no core frame (a weak
   dots-only line) becomes one "weak" line.
   - A first version split on IoU < 0.5 between consecutive masks. On bright still backgrounds (MP00_000_000 2577-3102,
     the pattern/planet scene) the background pieces kept the IoU high, and 4 lines merged into one. The vanish/appear
     rule splits them.
3. **One mask per line.** It holds the pixels in the persistent mask (threshold 30) in at least 40 % of the line's core
   frames (30 % for weak lines).
4. **Extension.** The line mask is applied to every core frame and also to frames before and after the core:
   - as long as the mean whiteness inside the mask stays above background + 15 % of the line's strength (fades);
   - and always at least 8 frames on each side (`--margin`);
   - into a neighbour line's core frames, at most 8 frames.

   Frames covered by two lines get the union of both masks. The first version stopped at the neighbour's core. That
   failed when the neighbour was a false "line" (background pieces) that started while the real text was still on
   screen (MP00_000_000 frames 303 and 356).
5. **Safety net.** In core and present frames, v2's own per-frame persistent pieces are added to the line mask.
6. **Background cut.** A mask pixel is dropped from the line mask and the safety net when it is white in at least 80 %
   of the 15 frames before AND the 15 frames after the line. Such a pixel is still background, not text. This made
   little difference (see below). `--no-bgcut` turns it off.
7. **Fill.** The masks are dilated 9x9 and clipped to rows y0-1..y1 (v2 used y0..y1-1). For each frame, candidate
   background frames come from just outside the lines that cover it: up to 60 frames each side, every 2nd frame.
   - Candidates are kept when the band outside both masks matches this frame: mean abs diff of a 4x downsampled band
     below 4.0 (`--static`). At most 7 are kept.
   - Each masked pixel takes the median of the candidates that neither mask that pixel nor show a white thin pixel
     there. The white-thin test stops text that no line covers from being copied in.
   - A colour offset measured on a ring around each mask region is added.
   - A region whose ring does not match is filled with Telea (radius 3), as in v2. So are pixels that no candidate
     sees.
8. **Output is the same as v2.** The settings are libx264 CRF 19, preset medium, High, level 4.0, yuv420p, audio
   stream copied, faststart. The script exits 1 unless frames in == frames out.
9. **Priority.** The script sets itself to IDLE priority, and ffmpeg inherits it.

## The residue check (dev/psnova/check_sub_residue.py, new)

The check finds the lines in the ORIGINAL with v3's detector. For each line it builds:
- **T**: pixels white (top-hat > 30) in at least 60 % of the line's core frames, inside the persistent mask, rows y0..y1-1;
- **ring**: the pixels 2-6 px around T.

It then looks at every frame from 20 frames before the core to 20 frames after. A frame counts only if the text is
really visible in the original: (share of T white) minus (share of ring white) > 0.25. A bright background makes both
shares high, so it does not count. For each counted frame:
- residue = T pixels still white (> 25) and unchanged (min-channel difference < 15) in the cleaned frame, minus (share
  of ring white in the cleaned frame) x |T|;
- the frame is flagged when residue > max(40, 4 % of |T|).

Flagged frames are split into **edge** (outside the core: the fade and change frames the user saw) and **core**.
"English-confirmed" lines are lines where the fan copy shows an English line in at least 30 % of the core frames. The
other lines are mostly false lines (background) and a few untranslated ones. The check also reruns v2's own detector on
the cleaned movie.

Two earlier versions of the check gave many false hits on bright scenes. The first compared with the original's own
frames 21-45 away. The second compared with the cleaned movie's frames 21-45 away. In both, the bright background
inside the mask counted as residue (for example MP00_000_000 frames 712-728, no text). The visibility test and the
same-frame ring fixed this.

## Residue v2 vs v3 (frames with leftover subtitle pixels)

| movie | lines (with English) | v2 edge | v2 core | v2 other lines | v3 edge | v3 core | v3 other lines |
|---|---|---|---|---|---|---|---|
| MP00_000_000 | 27 (23) | 116 | 26 | 12 | 0 | 0 | 0 |
| MP00_000_010 | 10 (10) | 30 | 8 | 0 | 0 | 0 | 0 |
| MP00_010_050 | 31 (29) | 112 | 0 | 27 | 0 | 0 | 0 |
| MP06_030_040 | 9 (9) | 36 | 0 | 0 | 0 | 0 | 0 |
| MP06_030_050 | 7 (5) | 17 | 2 | 4 | 0 | 0 | 0 |
| MP06_030_070 | 12 (9) | 34 | 0 | 3 | 0 | 0 | 0 |
| MP09_040_040 | 53 (42) | 167 | 87 | 145 | 2 | 0 | 19 |
| MP09_040_070 | 14 (14) | 54 | 2 | 0 | 0 | 0 | 0 |
| **total** | 163 (141) | **566** | **125** | **191** | **2** | **0** | **19** |

- v2's edge residue is the user's flash: about 2 frames at each end of almost every line. The core residue is mostly
  the first frame of a line that starts right after another one.
- The 21 v3 frames were looked at, and none holds text. They are all MP09_040_040 golden-glow scenes:
  - 1762-1763: "お前ってヤツは……" is removed; the bright gold background counts;
  - 1807-1826 and 3804-3808: false lines with no text at all.
- Strips: `dump/psnova-l10n/movies_v3_check/<movie>_line<i>_<cs>-<ce>.png`. Each shows original / v2 / v3 for frames
  cs-2, cs-1, cs, ce, ce+1, ce+2 of the 3 lines with the most v2 edge residue per movie, plus
  `MP09_040_040_worst_v3.png`.
- Strips looked at: MP00_000_000 (lines 23, 24, plus frames 133-2577 by hand), MP06_030_040 line 1, MP06_030_070 line 1,
  MP09_040_040 line 17 and worst. In every one, v2 shows the line at its ends and v3 shows none. v3 also removes the
  "!!" ghosts v2 left (MP06_030_070 frames 443/504).
- All 8 outputs: frame counts equal (checked by v3 and again by the check), durations equal to the originals, H.264
  High 960x544 29.97 fps, AAC audio present. Sizes are within 1 % of v2's (8.3-135 MB).

## Remaining problems

1. **Smears are still there (flaw 2 is not fixed).** Temporal fill covered only 0-21 % of the masked pixels (per movie:
   MP06_030_040 21 %, MP09_040_070 13 %, MP00_000_010 10 %, MP00_010_050 5 %, MP00_000_000 4 %, MP06_030_050 3 %,
   MP09_040_040 1 %, MP06_030_070 0 %). The rest is Telea, as in v2.
   - Most scenes move. In the still pattern/planet scene of MP00_000_000 (game 4600-5000), the masks of back-to-back
     lines plus persistent pattern pieces cover about 70 % of the band, so no candidate frame sees the background.
   - The background cut removed 15 % of that movie's line-mask pixels, but the masked area per frame fell by less than
     1 %.
   - Better quality needs motion-compensated fill (global shift or optical flow) or a video-inpainting model
     (ProPainter / E2FGVI). A model needs a download, which is the user's decision.
2. **False lines are smeared a little more than in v2.** In MP09_040_040's golden-glow scene (frames 1807-1873, no
   text), false lines now get their full line mask plus 8-frame margins. This leaves blotches on the character's legs,
   for example at frames 1871-1873. v2 smeared these frames too, but less.
3. **The check shares v3's detector.** A line that neither the detector nor the English timing finds is invisible to
   both. The check covers every line v2 cleaned (same presence), so it is no worse than v2's verification.
4. Not watched as video and not played in the game. The archive is not rebuilt.

## Commands

Run the commands from the worktree root. Both scripts set IDLE priority themselves. The runner does one movie at a time.

```
bash dev/psnova/run_remove_jp_subs_v3.sh
```

This writes:
- `dump/psnova-l10n/movies_clean_jp_v3/*.mp4`
- `dump/psnova-l10n/run3_<name>.log`
- `dump/psnova-l10n/movies_v3_check/lines_<name>.npz` (line table: cs/ce/a/b/fades/masks)
- `movies_v3_check/residue_<name>.log/.json`
- `movies_v3_check/*.png`
- `run3_done.txt`; a failure goes to `run3_failed.txt`

One movie:

```
python dev/psnova/remove_jp_subs_v3.py dump/psnova-l10n/movies_jp/MP00_000_000.mp4 dump/psnova-l10n/movies_clean_jp_v3/MP00_000_000.mp4 \
    --y0 470 --y1 497 --thr 350 --ref dump/psnova-l10n/movies/MP00_000_000.mp4 --lines dump/psnova-l10n/movies_v3_check/lines_MP00_000_000.npz
python dev/psnova/check_sub_residue.py MP00_000_000 --clean dump/psnova-l10n/movies_clean_jp --clean dump/psnova-l10n/movies_clean_jp_v3 \
    --strips dump/psnova-l10n/movies_v3_check --json dump/psnova-l10n/movies_v3_check/residue_MP00_000_000.json
```

Bands and thresholds (same as v2):

| movie | y0 | y1 | thr |
|---|---|---|---|
| MP09_040_040 | 464 | 491 | 700 |
| MP00_010_050 | 470 | 496 | 350 |
| MP00_000_010 | 472 | 499 | 350 |
| the other five | 470 | 497 | 350 |

Run time on this machine at idle priority: about 2 min for MP00_000_000 (3,407 frames), about 25 min for all 8 plus
checks. Peak memory is about 1.5 GB (MP09_040_040 band crops held in RAM).
