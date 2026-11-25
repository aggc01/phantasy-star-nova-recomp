# Frame rate (2026-11-18, late)

The game runs at 30 fps on the Vita. The recomp runs at about **25 fps** almost everywhere: title, menus, movies,
the ship and the arena. A few loading moments drop to 17-21.

## Runs

| Run | What | Log |
|---|---|---|
| test56 | title to the arena (frame 24,300), `RECOMP_METRICS=1 RECOMP_GPU_STATS=1 RECOMP_GPU_FENCE_STATS=1 RECOMP_WAIT_STATS=300 RECOMP_GPU_PRESENT_NOSYNC=1`, shots every 1500 | `dev/psn-logs/test56-timing-full.log` (29 MB), report `test56-timing-report.txt` |
| test57 | title only (frame 3,000), `RECOMP_GPU_TRACE_SYNC=1` | `dev/psn-logs/test57-sync-full.log` |

Report tool: `python dev/psnova/timing_report.py <test.log> [window]` gives fps, draws, readbacks and the renderer's
host time per 300-frame window, plus the busiest threads from the wait stats.

## Where the time goes

- The renderer's host time is 15-23 ms per frame **even with 11 draws** (the title screen). Almost all of it is
  "texture binding", and **11-13 ms of that is "target sync"**: render targets copied from the GPU to guest memory, the
  CPU waiting for the GPU each time.
- The game's main thread (Aska) does that work while it holds the renderer lock, and is blocked 14-21 ms per frame. Its
  own CPU work is 30-55% busy. Without the syncs it would fit in 33 ms.
- The per-scene readbacks of targets the game reads on the CPU (`cpu_reads`, the read watch) are **not** the cost:
  0.0-0.1 readbacks per frame in test56.

## Why the syncs happen (test57)

Every frame the game runs a blur/bloom chain: it draws a 960x544, a 240x136 and a 120x68 target and reads each back as
a texture. The targets are colour format `0x00100000` (U8U8U8U8 with the ARGB colour swizzle); the textures are format
`0x0c009000` (U8U8U8U8 with texture swizzle 1, ARGB). In 3,000 frames:

| Target | Downloads | "no view" misses |
|---|---|---|
| 0x1d7e5290 120x68 | 6,002 (2 a frame) | 27,009 |
| 0x1e960040 240x136 | 6,002 (2 a frame) | 9,003 |
| 0x1e760080 960x544 | 3,001 (1 a frame) | 6,002 |

`target_view` (gfx_gpu.c) can't bind these targets directly. The exact path wants colour swizzle bits
`(format >> 20) & 3 == 0`, and the view path (`view_mode`, case `0x00000000`) refuses
`(tgt_fmt & 0x00300000) != 0`. So each read goes "decoded from guest memory": a synchronous download, a CPU decode and
a re-upload, 5 times a frame.

## Fix (done 2026-11-18 late, game_dev.exe)

`view_mode` (gfx_gpu.c, case `0x00000000`) now accepts a U8U8U8U8 target with any colour swizzle. The texture's selectors
(which name guest bytes) go through `enc[cs]`, the guest-byte-to-component map of `gfx_soft.c target_write_raw_of`.
ARGB written and ARGB read compose to the identity. `RECOMP_GPU_NO_SWIZZLED_VIEWS=1` brings back the old path. The math
is the same as the Luufen fork's 1deb30f (`view_swz.h`). In the fork's measurement, the arena went from 117 ms to
33.6 ms a frame.

It was reviewed twice. Both reviews found the math right for all 8 texture modes and all 4 colour swizzles. Their two points
were taken:

- **Kept pages.** The noisy-texture fix (`kept_pages_find`) works only on the guest-memory path. A view of a dead target
  whose pages the game has since rewritten would sample stale GPU pixels. `target_rewritten_under()` now sends such a
  texture to the guest path, before the exact bind and before any view. This also covers ABGR targets, which had the
  same gap.
- **Swizzled sRGB targets.** A view is refused when the composed selectors would move alpha into a colour slot, or a
  colour into alpha. The guest path decodes by slot.

### Results

- **test58** (same route, title to frame 24,300): "(texture view)" downloads went from about 15,000 to 11.
  "target sync" is 0.0-0.2 ms a frame, down from 11-13. The renderer's host time is 2-10 ms a frame, down from 15-23.
  fps is **27-30**, up from 24-28. Report: `dev/psn-logs/test58-fix-report.txt`.
- **Picture check.** Frame 2500 was captured and replayed with the views on, with them off
  (`RECOMP_GPU_NO_SWIZZLED_VIEWS=1`), with no views at all (`RECOMP_GPU_NO_VIEWS=1`), and on the software renderer:
  **all four byte-identical**. The views were used: 13 view builds, against 2 downloads.
- **What's left.** The game's main thread (Aska) is now 6-30% busy and blocked 23-35 ms a frame: it is waiting for the
  vblank, not working. The shortfall below a steady 30 is pacing (vblank edges missed), not speed. Title and movie frames
  still spend about 8.4 ms uploading one texture a frame, the decoded video frame.

## 60 fps (done 2026-11-19, game_dev.exe and game_host.exe)

The user asked for 60. The engine is built for 60, and game time comes from measured vblanks, so nothing runs double
speed. Research with each finding checked a second time: [60fps-sites.md](60fps-sites.md). Four changes:

1. **The game's own target.** `psn_frame_rate`, a HOOKS entry at fn_81a7756c (packs/PCSG00351/hooks.c). Each frame,
   with the `frame_rate` setting at 60, it writes T+0xcc = 60 and the cloth/physics step 0x82474334 = 0.016 (the data
   default). The boot code sets 30 and 1/31. Switching back to 30 restores the game's own values. The F10 menu applies
   it at once. `RECOMP_PSN_FPS_TRACE=1` prints the game clock's measured vblanks per frame every 300 frames.
2. **One edge per flip** (display.c `h_wait_vblank`, `setbuf_latched`). In a window, SetFrameBuf presents at the
   vblank; the game's WaitVblankStart right after it then waited for the edge *after* that one. Every flip took 2
   edges (3 when the present ran long). That alone capped windowed play at 30. It now returns at once, as the console's
   SetFrameBuf(NEXTFRAME)+WaitVblankStart does. Any other display wait clears the latch.
   `RECOMP_SETBUF_WAIT_LATCHED=0` turns it off.
3. **Precise DelayThreadCB / CB vblank sleeps** (kernel.c `kernel_cb_sleep`). The condition variable's timed wait
   rounded to Windows' timer: whole milliseconds, up to a 15.6 ms tick. The game polls with DelayThreadCB(200 us)
   loops, and its main thread lost 19-30 ms a frame to them, out of sight of every counter. The vblank callback was
   0.4-1.4 ms late, sometimes 10-15. The last 2 ms are now slept with the high-resolution timer in 250 us slices,
   callbacks checked between them, off the scheduler's run slot. `RECOMP_CB_SLEEP_COARSE=1` turns it off. This change
   also turned 30 fps mode from 27-30 into a **flat 30.0**.
4. **Review fixes.**
   - The CB vblank waits compared a pause-adjusted edge time with the raw clock. After the F10 menu had been opened
     once, they stopped sleeping, an old bug: the game's VSync thread would have counted vblanks as fast as it could
     loop. Now `edge_raw_us`.
   - The latch leaked into later waits; now cleared by every display wait.
   - The precise tail took the scheduler slot per slice; now it stays off the slot.

**A crash found on the way.** Two runs crashed in the NVIDIA driver during character creation (frames ~9000 and
~9600), at the batch submit. A target evicted from the 64-entry LRU (get_target_at) released its textures while a
hoisted view pass in the pending batch still named one. The swizzled views made such passes common.
`target_release` now retires each of its textures from the batch first (`batch_retire`), and so does the depth table's
eviction. With that fix, test67 ran title to arena with no crash.

**Measured (test67, headless with RECOMP_PRESENT_AT_VBLANK=1, 30 fps up to frame 21,900, then 60):**
- **30.0 fps** every window from the title to the arena.
- In the arena at 60: **56-60 fps** (59.4-59.8 most windows). The game clock reads 1 vblank = 0.0167 s per frame.
- The title at 60 (test63): 53-59 fps.
- Pictures correct (test67-last.png: HUD, damage number, quest text).

Not measured: windowed play at the launcher's 2x render scale, where the GPU has 4x the pixels; and a full 60 fps
route. The scripted inputs are keyed to frame numbers, so a 60 fps run needs inputs at twice the frame numbers. The
user's `recomp/settings.ini` has `frame_rate = 60` (the old file is in `dev/psn-logs/settings.ini.before-60fps`); test
runs never read it.

The movies also spend about 8 ms a frame decoding each video frame on the CPU (`gpu uploads: decode`). That's a second,
smaller item.

## Windowed crash and the startup freeze (2026-11-19 early morning)

The user's first windowed play of the 01:51 build crashed on the title right after Start skipped the third movie:
`SDL_CreateGPUTexture failed: vkQueueSubmit VK_ERROR_DEVICE_LOST`, then an access violation in `batch_flush`. Their log
is kept in `dev/psn-logs/user-crash-2026-11-19-0327.log`. Headless tests (test68: 60 fps, render scale 2, the same route)
never showed it.

**Repro.** `dev/psn-logs/run_window_check.sh <name> <secs> [env...]` runs the dev exe in a real window (`vitarecomp run`)
with Start pressed during the third movie, then prints the last frame and any crash. The bisect:

| Runs | Setting | Result |
|---|---|---|
| test70, test71, test73 x4 | as built | 5 of 6 crashed (device lost, most by frame 3-300) |
| test72 x4 | `RECOMP_GPU_NO_SWIZZLED_VIEWS=1` | 0 of 4 |
| test74 x3 | `RECOMP_GPU_ASYNC=0` | 3 of 3 crashed |
| test75 x3 | `RECOMP_GPU_VIEW_FAST=0` | 0 of 3 |

**Cause.** On Vulkan, VIEW_FAST changes only the view texture's format: narrow (RGBA8 for these targets) when the
texture is point-sampled, RGBA32F when it is filtered. `view_entry` keyed its cache without the format and, on a format
change, freed the entry's texture and made a new one in place. A draw that samples one bloom texture through two units,
one filtered and one point-sampled, freed the texture its first unit had just bound. That draw isn't in the batch yet,
so `batch_retire`'s flush couldn't protect it. It was submitted naming a released texture, and the GPU lost the
device. The swizzled views made the bloom chain's targets views, so it happened within seconds.

**Fix.** The view's format is now part of `view_entry`'s key: each format gets its own entry, and nothing is freed under
a draw. test76 x4 (two runs past the Start press, to frame 3900) and test78/test79 (the rebuilt game_host.exe, to frame
4800): no crash.

**The startup freeze.** The user saw a black screen for 16-17 s before the first warning screen. Every windowed run had
it, about ten frames of 1.3-4.8 s each before frame 25, while the renderer drew about 1 ms a frame. In a window, the
recipes' warm-up runs a *predicted pipelines* pass (NVIDIA + Vulkan only, `pipe_predict_on`): 192 pipelines for
fragment programs not yet drawn, "18.1 s". The game stands still until it ends, on every launch, warm cache or not
(game_dev.exe's 6th start froze as long as its 1st). With `RECOMP_PIPE_PREDICT=0` (test77), frame 300 comes at 6.8 s
instead of 23.5 s and no startup frame takes more than 0.8 s. The pack's `RUN_ENV` now sets it, built into game_host.exe
and game_dev.exe. Other games are unchanged.

Open: why the game thread waits on that pass at all (two build workers, the render thread almost idle). It's shared
runtime code, so look into it before turning the pass off for other games.

**Answered the same evening** (docs/psnova/external-fix-list-check.md): not the pipelines. usse.c looped over GXP header
counts unbounded, and 9 "fragment programs" in the game's files (not programs: absurd counts, one with 2,702,302,092
uniform buffer entries) took ~18 billion loop steps on the render thread under gfx_lock. With the counts bounded the
pass takes 1.0 s, frame 300 comes at 6.4 s, and RECOMP_PIPE_PREDICT=0 is gone from the pack. Also that evening: the
CB sleep tail 2 ms -> 20 ms (winpthreads' timed wait waits in GetTickCount64 steps of ~15.6 ms): 43 % of the vblank
waits came back 2-16 ms late before, none after.

## The texture crash 20 minutes in (2026-11-19 05:18)

The user's play of the 03:55 game_host.exe crashed in a Filldia cutscene at frame ~71,900 (60 fps, about 21 minutes):
an access violation at 0x4c inside `SDL_UploadToGPUTexture`, called from `upload_texture`'s BC path
(`upload_texture_bc`, inlined), from `bind_unit`. The log is in `dev/psn-logs/user-crash-2026-11-19-0518.log`. No
earlier run had played this far.

**Cause (old shared code, not the frame-rate work).** The texture cache keys an entry by address, format and size, not
by mip count. The game put a texture with another mip count at the same address, format and size. `upload_texture` then
uploaded into the entry's existing GPU texture, and levels past the old object's count went to subresources it doesn't
have. A non-cube texture got there through `get_texture`'s "another layout or extent: re-decode in place" (its span
counts the mips; only a layout change made a new object). A cube got there through the plain re-check, because its
faces reserve the whole chain whatever the count, so its span doesn't change.

**Fix.** `upload_texture` remembers the mip count the GPU texture was made with. When the count changes, it releases the
texture and makes a new one. It also logs `gpu: texture ... N mip levels, was M -- a new texture object` (up to 20
times), so the next long run can confirm the case happens. In game_dev.exe since 05:24. Not yet confirmed in game: no
scripted route reaches that cutscene.

The 10-13 fps seen in the arena in test55 (shots every 300 frames, presents synced) didn't repeat in test56: 25.5 there.
