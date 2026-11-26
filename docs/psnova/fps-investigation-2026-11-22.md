# Nova frame-rate investigation


## What my run recorded

The normal launcher used Vulkan mailbox presentation, a 60 FPS target and 4× rendering on the RTX 5060 Ti. The save list remained at roughly 60 FPS for about 2 hours and 25 minutes. I then loaded slot 1, Force Lv6 in Steel Giants. The slowdown began after the load and varied during the following gameplay.

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

The installed `game_host.exe` was run in a window against copied saves. The runs kept the real clock, the 60 FPS setting, and the pack's graphics defaults. Both runs confirmed the requested slot loaded. The second run copied my updated Lv7 save and used scripted walking and camera inputs at the base. The scripts checked live save hashes and restored the reusable fixture.

| Test and interval | Scale | Game FPS |
| --- | ---: | ---: |
| Lv6 base, frames 3600–4200 | 4× | 59.99 |
| Lv6 base, frames 4500–4800 | 2× | 60.02 |
| Lv6 base, frames 5100–5700 | 4× | 60.00 |
| Lv7 base with scripted input, frames 2400–3000 | 4× | 60.00 |
| Lv7 base with scripted input, frames 3300–3600 | 2× | 60.01 |
| Lv7 base with scripted input, frames 3900–4200 | 4× | 60.00 |

The first run's typical measured GPU time was 6.2 ms at 4× and 3.2 ms at 2×. Median present-fence latency was 0.5 ms at either scale with no measured frames in flight at present. The variation around scale changes was excluded from the listed intervals. [Lv6 comparison](../../dump/codex-fps-20261122/windowed.log) · [Lv7 comparison](../../dump/codex-fps-20261122/moving.log)

An offline replay reused my earlier ruins capture `frame_116550.vfc`, 27 scenes and 975 draws across three frames. GPU fence estimates were 5.9 and 6.5 ms per frame on two 4× runs, and 4.2 ms at 2×. Replay does not run the game threads or the window swapchain and does not establish the GPU workload during the newer 8 FPS interval. [4× replay](../../dump/codex-fps-20261122/replay-4x-115538.log) · [2× replay](../../dump/codex-fps-20261122/replay-2x-115536.log)

The preserved log confirms the sustained drop. It did not recur in either fresh base test. The exact mission and input route through the slow interval were not recorded.

## Measurements enabled for normal play

Nova's normal launcher now sends the existing measurements to `session.log`. `gpu fence` reports once a second and records estimated GPU busy time, present submit-to-completion latency and frames in flight. `waits` reports every 120 presented frames and records per-thread CPU time, kernel blocking, sleeps, renderer-lock contention and wake latency. `metrics` adds one-second frame and present timing, and `psn clock` records the game's 60 FPS target and vblanks every 300 frames. Per-frame present and fence traces remain opt-in to keep long session logs manageable. The diagnostic GPU fences add queue submissions and a polling thread.

The ordinary windowed launch path was verified with the installed executable and isolated saves and preferences. The test logged all four streams and preserved both save trees. Explicit values for the GPU fence and wait settings override the defaults. The existing executable, graphics options and save files do not need a rebuild or migration. [Launcher verification log](../../dump/codex-fps-20261122/launcher-check/session.log)

## Instrumented open-field run reviewed on 2026-11-22

I identified the trigger as the open fields in planet missions. The newer normal-play log contains the GPU-fence, wait and metrics streams missing from the earlier long session. A fixed snapshot is retained at `dump/codex-fps-20261122/telemetry-review/session-snapshot.log`; the line references below refer to that snapshot.

| Metrics line | Nearby hitch frames | Reported game FPS / average frame | GPU fence estimate | Present latency / queued frames |
| --- | --- | --- | --- | --- |
| 53790 | 289104-289110 | 7.5 FPS / 126.3 ms | 6.6 ms/frame at line 53785; 6.7 at 53792 | 0.4 ms / 0 |
| 56495 | 302763-302774 | 8.5 FPS / 117.5 ms | 4.7 ms/frame at line 56496 | 0.4 ms / 0 |

Adjacent ordinary-game hitches have roughly 2-3 ms of recorded host drawing, zero target downloads, zero ring/readback waits and sub-millisecond to low-single-millisecond file-read totals. The window continues at about 60 FPS. GPU work of approximately 5-7 ms and an empty measured present queue do not explain the 118-126 ms game frame times in these intervals. This identifies a CPU-side delay for these two troughs; it does not identify the exact guest or host function.

The 120-present wait report after the first trough (line 53800) spans 4.17 s at 28.8 FPS. It records CRI Server Manager at 92.2% CPU, an unnamed `(host)` thread at 72.0%, and Aska::RenderCallBack at 6.0% CPU with 31.78 ms blocked per game frame. After the second trough (line 56512), the 4.78 s report records `(host)` at 76.4%, CRI Server Manager at 71.2%, and the render callback at 10.1% with 36.12 ms blocked/frame. Renderer-lock queueing and wake latency are small in those reports. These wider windows suggest additional CPU work and blocked downstream rendering, but cannot assign an individual slow frame to a particular thread. CRI also runs near a full core during some healthy intervals.

The label `(host)` is not a stable identity: unnamed native threads share it. Existing aggregate waits do not record the waited object's ID or a call stack. Resolving the exact cause therefore requires function samples correlated with the next reproduced field interval. `dev/psnova/win_cpu_sample.py` provides bounded external x64 PC sampling without replacing the installed game; an independent owned CPU-loop test captured 54 samples, 41 in the expected `hot_loop` range, with no API errors. PC samples can perturb scheduling and do not provide complete stacks.

The separate 5.8 FPS wait report at line 41307 overlaps an F12 capture (frames 218985-218987). Those frames took 5.5-7.7 seconds and recorded multi-second I/O plus about one second of target downloads each. Exclude that event from the ordinary field slowdown.

A fresh isolated probe copied my saves and loaded the Lv8 character at the base. It was stopped before a field route when F: reported zero free bytes. Both before/after live-save hash checks passed. This disk-space condition was observed during the new probe; it is not an established explanation of the earlier FPS drops. CPU function capture in a reproduced field remains pending.

### Field reproduction after freeing space

After I removed the old `recomp/video_take7` recording folder, F: had approximately 8 GB free. A new isolated ten-minute run used copies of the current Lv8 saves, the installed executable, 4x rendering, the 60 FPS target, private settings and the normal pack graphics defaults. I navigated to a planet field mission and moved/fought there. I reported no FPS dip in this run. The captured non-startup metrics likewise contain no interval below 20 FPS. The bounded probe finished and the live save hashes remained unchanged. The captured inputs, telemetry, CPU PCs and `probe-summary.json` are under `dump/codex-fps-20261122/telemetry-review/field-probe-03`.

External PC sampling ran in two bounded windows and recorded telemetry on the same monotonic timeline. These provide a healthy field baseline, not a slow-frame function profile. The probe had the legacy input-trace variable present with value `0`; that trace checks presence, so it was enabled. Disable it entirely for a final comparison. The isolated filesystem and shader cache are also different from an aged normal session.

The current page file is `C:/pagefile.sys`, allocated 16,000 MB with 739 MB used (peak 3,817 MB). The machine had approximately 24 GB available RAM, 42.0 GB committed against a 68.2 GB limit, and zero page reads per second at the sampled moment. Those current values do not reconstruct memory pressure during the earlier drops. Windows page-file growth depends on available space on its volume ([Microsoft documentation](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/how-to-determine-the-appropriate-page-file-size-for-64-bit-versions-of-windows)). F: also holds the game's data, private shader cache and logs. Its earlier zero-free-space state caused an observed profiler write failure, but no captured evidence establishes that it caused the earlier frame-rate drop. Freeing space and restarting the process happened together, so the successful fresh run does not isolate either factor.

The older slow wait windows show much more CPU work in CRI Server Manager and an unnamed host thread than this fresh field run, while the render callback remains around a few milliseconds of CPU per frame. Source inspection found two unconfirmed accumulation mechanisms: NGS rack release is a no-op and the audio update scans the accumulated voice array; callback checks scan a kernel-object table that retains deleted entries. Both logs contain only 11 NGS rack initializations, and neither records kernel object counts or callback scan duration. These are measurement targets, not established causes. The exact CPU-side cause remains unresolved until a slow interval is reproduced with the function sampler.
