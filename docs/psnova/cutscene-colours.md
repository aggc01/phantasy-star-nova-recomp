# Washed-out cutscenes and magenta glow (2026-11-19)

The user played to the Filldia landing and saw two things: cutscene characters looking pale and white, and saturated
magenta streaks in the sky. Their reference frames from a real Vita playthrough (one frame a second, outside the repo:
`C:\New PATH\screenshots\`, part 1 = character creation + intro, part 2 = mission 1) show the same shots in normal colour.

## Reference comparison

| Shot | Vita (reference) | Recomp |
|---|---|---|
| Lutina + Fildia close-up, part 1 at 18:00 = capture frame 28,200 | Lutina's outfit deep red and white, Fildia's suit black and red | red shows pale pink, black shows grey |
| After the landing, part 1 at 21:58-22:20 | skin and hair in normal colour; the sky has a soft pink-violet glow | skin white, saturated magenta streaks and a white blown-out patch where the glow is |
| Arena gameplay, part 1 at 14:36-15:16 | cyan floor, grey walls, white crates | about the same |

Tools: `dev/psnova/jpg_sheet.py` (any image format, PIL) tiles reference frames and shots;
`dev/psn-logs/ref-*.png` are the sheets used here (game imagery, git-ignored).

## What it isn't

- **Not last night's renderer change.** Capture frame 28,200 (test81) replays byte-identical with the swizzled views on,
  off, with no views at all, and on the software renderer. Yesterday's take 7 video (before the views) is just as pale in
  the same scene.
- **Not the final composite's constants.** The composite (fragment program 0x110fbee0: `csvConst_0`, `csvConst_1`,
  `sTex_0` = scene, `sTex_4` = 120x68 bloom) gets the same constants in gameplay and in the cutscene: (0, 0, 2.682, 0)
  and (0.286, 0.271, 0.257, 0.714), half precision. It's a fixed curve.
- **Not a different character shader.** Cutscene characters use fragment program 0x11107a90, gameplay characters
  0x111085c0: byte-identical code (5 + 1 instructions). Same vertex program 0x11107130. Same `cvHDRTransform`
  (2.0488, 0.4883). Same lights: one directional light of 4.775 and the same spherical-harmonics ambient.
- **Not uneven frame times or the 60 fps mode.** The capture was at 30 fps.

## Where it happens

Stepping the capture with `RECOMP_REPLAY_DRAWS=k` (software renderer): after draw 96 (the scene target 0x1e760080,
before post-processing) the characters are deep red, near-black and grey, like the reference. After draw 104 (the
composite) everything is lifted. The curve maps scene values 25-73 to 129-234. The scene target holds the characters
about twice as bright as the curve expects for the Vita's colours. The background walls in the same frame match.

## The likely cause: sRGB texture modes are off for this game

`runtime/gfx/gxm_sony.c` takes the texture gamma mode (control word 0 bits 27-28) and the colour surface gamma mode only
with `RECOMP_SRGB=1` (opt-in per game). Uncharted, Unit 13 and Killzone set it in their packs. Uncharted's note: "without
them sunlit scenes blew out yellow-white against the real Vita". Phantasy Star Nova's pack doesn't set it, so textures the
game marks sRGB are sampled raw, too bright, and the tone curve lifts them further. The magenta is the soft pink-violet
glow pushed to saturation.

A capture can't test this: it records texture formats with the gamma bits already dropped. Test: test86, a live run with
`RECOMP_SRGB=1` to capture frame 28,200, compared with the reference at 18:00.

## Result: fixed by RECOMP_SRGB=1 (2026-11-19 07:31)

- **test86** (sRGB on, the route to frame 28,200): the Lutina cutscene in the Vita's colours. Fildia's suit is deep red
  and black, Lutina's outfit red and white. The arena (shots every 300 frames) still matches the reference.
  `dev/psn-logs/srgb-compare.png`, `srgb-arena.png`.
- **test87** (sRGB on, title to character creation, shots every 500): tri-Ace logo, intro movie, title, the movies and
  character creation all in normal colour. `dev/psn-logs/test87-sheet.png`.
- `packs/PCSG00351/pack.toml`: `RUN_ENV` and `TEST_ENV` now have `RECOMP_SRGB=1`. Built into game_host.exe (07:31:35)
  and game_dev.exe (07:32). test88: the launcher exe windowed, no crash, frame 300 at 6.6 s.
- Not yet seen with sRGB on: the after-landing cutscene where the magenta was. Expected fixed with the rest (the same
  lift saturated its pink glow), to be confirmed in play.

## The dark band (still open)

The user's 04:21 screen recording (Steel Wastelands, 60 fps) shows it clearly: a long, straight, bluish shadow from the
character's feet. The arena's directional light is low (direction y = -0.28, about 16 degrees above the horizon, from the
captured `cvDirContext`), which makes a shadow about 3.5 times the character's height. So it may be the game's own shadow.
The reference arena frames don't show a clear long band, but the video quality is low. Headless scripted runs (30 and 60
fps, steady or loaded) never showed it. Next: an F12 capture from the user while it shows, then compare its shadow-map
draws with the same frame on the software renderer.

## Tools built for this (Windows, in build/, from runtime/debug)

- `build/usse_dis.exe`: GXP disassembler (instruction names, parameters, iterators).
- `build/usse_run.exe`: runs a fragment program on chosen inputs (`RECOMP_USSE_TRACE=1` for the step-by-step trace). Its
  iterator inputs didn't reach 0x11107a90's texture and lighting, so its numbers for that program aren't meaningful.
- Build line: clang with `runtime/debug/usse_dis.c` (or `usse_run.c`) + `runtime/gfx/usse.c` +
  `runtime/platform/win32_compat.c` + `runtime/platform/platform_win32.c`, `-lpthread -lwinmm -lws2_32`, the includes and
  `-include` lines of `dev/build_replay_win.sh`.
