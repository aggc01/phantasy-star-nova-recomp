# Nova frame-rate investigation

Done by Codex, 22 November 2026.

## What the player's run recorded

The normal launcher used Vulkan mailbox presentation, a 60 FPS target and 4× rendering on the RTX 5060 Ti. The save list remained at roughly 60 FPS for about 2 hours and 25 minutes. The player then loaded slot 1, Force Lv6 in Steel Giants. The slowdown began after the load and varied during the following gameplay.

| Frame interval | Elapsed time | Game FPS |
| --- | ---: | ---: |
| 525000–529500, save list | 75.97 s | 59.23 |
| 529800–530100, just after load | 18.84 s | 15.93 |
| 535800–536100 | 35.34 s | 8.49 |
| 537000–537300 | 35.88 s | 8.36 |
| 537300–537600 | 35.21 s | 8.52 |
| 571500–571800 | 9.90 s | 30.31 |

The log records ordinary game frame intervals, with no F12 capture during this run. After frame 3000, it contains 1,243 hitches of at least 100 ms. The median hitch took 163.7 ms, with 3.4 ms of median recorded rendering work on the CPU. Frame 535077 took 288.4 ms with 5.3 ms of recorded rendering and no shader or pipeline builds, readbacks, texture uploads, or file I/O. The older F12 stalls and bloom target downloads are separate documented cases.

The hitch counter's `gpu` field measures host renderer time. This log has no GPU fence timing or per-thread wait samples for the slowdown. The missing time could be game-thread work, scheduling or waits, or a window or driver wait outside the measured renderer. The Windows stall profiler selected by the default launcher is a no-op on this platform. The attempt to read the Windows System log for the affected interval was denied by the execution environment, so no system event correlation is established. [Preserved launcher log](../../dump/codex-fps-20261122/live-11-45.log)

## Reproduction tests

Codex ran the installed `game_host.exe` in a window against copied saves. The runs kept the real clock, the 60 FPS setting, and the pack's graphics defaults. Both runs confirmed the requested slot loaded. The second run copied the player's updated Lv7 save and used scripted walking and camera inputs at the base. The scripts checked live save hashes and restored the reusable fixture.

| Test and interval | Scale | Game FPS |
| --- | ---: | ---: |
| Lv6 base, frames 3600–4200 | 4× | 59.99 |
| Lv6 base, frames 4500–4800 | 2× | 60.02 |
| Lv6 base, frames 5100–5700 | 4× | 60.00 |
| Lv7 base with scripted input, frames 2400–3000 | 4× | 60.00 |
| Lv7 base with scripted input, frames 3300–3600 | 2× | 60.01 |
| Lv7 base with scripted input, frames 3900–4200 | 4× | 60.00 |

The first run's typical measured GPU time was 6.2 ms at 4× and 3.2 ms at 2×. Median present-fence latency was 0.5 ms at either scale with no measured frames in flight at present. The variation around scale changes was excluded from the listed intervals. [Lv6 comparison](../../dump/codex-fps-20261122/windowed.log) · [Lv7 comparison](../../dump/codex-fps-20261122/moving.log)

An offline replay reused the player's earlier ruins capture `frame_116550.vfc`, 27 scenes and 975 draws across three frames. GPU fence estimates were 5.9 and 6.5 ms per frame on two 4× runs, and 4.2 ms at 2×. Replay does not run the game threads or the window swapchain and does not establish the GPU workload during the newer 8 FPS interval. [4× replay](../../dump/codex-fps-20261122/replay-4x-115538.log) · [2× replay](../../dump/codex-fps-20261122/replay-2x-115536.log)

The preserved log confirms the sustained drop. It did not recur in either fresh base test. The exact mission and input route through the slow interval were not recorded.

## Measurements enabled for normal play

Done by Codex. Nova's normal launcher now sends the existing measurements to `session.log`. `gpu fence` reports once a second and records estimated GPU busy time, present submit-to-completion latency and frames in flight. `waits` reports every 120 presented frames and records per-thread CPU time, kernel blocking, sleeps, renderer-lock contention and wake latency. `metrics` adds one-second frame and present timing, and `psn clock` records the game's 60 FPS target and vblanks every 300 frames. Per-frame present and fence traces remain opt-in to keep long session logs manageable. The diagnostic GPU fences add queue submissions and a polling thread.

The ordinary windowed launch path was verified with the installed executable and isolated saves and preferences. The test logged all four streams and preserved both save trees. Explicit values for the GPU fence and wait settings override the defaults. The existing executable, graphics options and save files do not need a rebuild or migration. [Launcher verification log](../../dump/codex-fps-20261122/launcher-check/session.log)
