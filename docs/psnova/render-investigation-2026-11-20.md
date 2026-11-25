# Nova color and present investigation, November 20

## Playable fix for Kisara and Fildia

The normal Nova GPU launcher now enables `RECOMP_GPU_DEPTH_CLIP=1` in `packs/PCSG00351/pack.toml`. The rebuilt game_host.exe embeds the same default for direct launches. The executable SHA-256 is 32D2027E80D0E2EBB6B97BED4D451398E6CF2D7FC3EF8415B79C64CD7E971CA2. The prior executable is preserved under bridge-camera/game_host-before-clip-default.exe. Restart through the usual launcher to pick up the setting.

The GPU was clamping geometry outside the camera's depth range, allowing near surfaces to cover the characters. In saved-frame tests on the RTX 5060 Ti, clipping restores Kisara at her console in both frame 22815 (immediate) and 49261 (deferred), and Fildia with her body, weapon and sky in frame 74253. Confirmed at 4x internal resolution for 22815 and 74253 against the matching Vita views. The camera matrices and mesh submissions are the originals. In a separate intermediate test, omitting only draw 37 brought Kisara back but left other incorrect foreground geometry along the bottom. Enabling clipping across the scene also corrected the foreground.

To reproduce, run `python dump/codex-render-20261120/bridge-camera/full_check.py` from the Nova repository. Use build/gfxreplay-depthclip.exe with the same capture, Vulkan, sRGB and RECOMP_REPLAY_KEEP_TARGETS=1 while varying only RECOMP_GPU_DEPTH_CLIP between 0 and 1. The older build/gfxreplay-gpulines.exe lacks the switch entirely. Keep rendered targets through the final present so recorded render-target memory cannot overwrite the replay result. The software interpreter has a different clipping implementation and cannot test this GPU switch. The previous conclusion about needing a game camera change is superseded.

At 960x544, the changed RGB pixel counts were 512,957 (22815), 512,999 (49261), 170,186 (50497 working crew shot, foreground console exposed) and 520,286 (74253). The original and corrected settings produced byte-identical image pixels for combat 9761 and the last completed present of truncated captain capture 74696. The captain haze and intermittent flash remain separate issues.

The rebuilt game_host.exe also booted at 4x with the normal pack settings supplied to a headless smoke test, loaded an isolated copy of slot 1, reached the outdoor base and exited successfully at frame 4720. The two cutscenes were verified in F12 replay, while the live check covered loading and gameplay. [Live smoke image](../../dump/codex-render-20261120/bridge-camera/play-smoke/smoke.png)

[Full-frame pairs](../../dump/codex-render-20261120/bridge-camera/full-comparison.png) · [Kisara at 4x](../../dump/codex-render-20261120/bridge-camera/final-22815-4x.png) · [Fildia at 4x](../../dump/codex-render-20261120/bridge-camera/final-74253-4x.png) · [Bridge draw isolation](../../dump/codex-render-20261120/bridge-camera/world-tests.png)

The ten post-deferred-draw F12 frames are the primary evidence. Earlier renderer fixes are documented separately in picture-faults.md. Baseline log copied from the live game folder to dump/codex-render-20261120/session-original.log. The capture session reports 4× render scale. This document records each result as it is verified.

## Ten F12 captures

Evidence paths below are relative to the Nova repository. Scratch directory `dump/codex-render-20261120/`. Frame IDs: 9685, 9761, 9788, 12675, 15533, 16646, 16913, 17250, 17429, 17798. See `contact.png` in scratch. The archived session log contains the ten corresponding capture events, render scale 4×, deferred draws enabled, and zero software draws in all 62 sampled counters. These are sparse counters. F12 captures guest rendering commands. Replayer screenshots are 960×544 and omit final window post-processing.

## Colored geometry — verified cause and source change

Frame 9761's software replay introduces a wedge between draws 935 and 936. Frame 9788 shows the same defect at 846, immediately after clean draw 845. The relevant vertex/fragment programs are 0x1111af40 and 0x1111b590. Four corners of a billboard have distinct UVs (stream 1), but should share one particle position and color (stream 0). The observer emitted a stride of 56 bytes on stream 0 of a single-instance quad. Later corners read the next particle or unrelated data. Previous work on scene-end timing and multi-instance splitting did not cover this fetch.

`runtime/gfx/gxm_sony.c` was changed to honor the active program's declared instance-index source on every emitted draw. Its base advances between instances; the attribute stays constant across vertices of the instance. Vertex-indexed streams retain their original stride. The old diagnostic `RECOMP_GXM_ONE_INSTANCE=1` retains its legacy behavior. No shader addresses are hardcoded in the runtime fix.

### Reproduce and check

From the repo, use the local Python and prepend `toolchain/llvm-mingw/bin` to PATH. For an ordinary replay use `RECOMP_GFX=gpu`, `RECOMP_SRGB=1` and `build/gfxreplay-gpulines.exe <capture.vfc> <output.ppm>`. Logs confirm NVIDIA Vulkan and the native GPU line path. For the causal A/B, run `.venv/Scripts/python.exe dump/codex-render-20261120/paired.py`. It uses diagnostic **copies** with only the affected shader family's captured stream-0 stride changed from 56 to zero and preserves prior replayed targets with `RECOMP_REPLAY_KEEP_TARGETS=1`. Without that flag a subsequent snapshot restores the original bad picture; in frame 17798 the ordinary A/B outputs have identical SHA-256 despite the changed draw.

See `paired.png` in scratch (original on left, corrected on right). The red/rainbow geometry disappears in 9761, 9788 and 16646, and the black/violet wedge disappears in 17798 while the central light effect remains. At a threshold of 24/255 on any RGB channel, changed pixel counts were 20,147; 26,773; 14,286; and 108,064 respectively. The clean control 16913 had 24 changed pixels out of 522,240. This demonstrates the fetch correction on captured inputs; the VFC edits simulate the observer change and are never installed as game data.


## Build and rollback

The stock command `.venv/Scripts/python.exe -s -B pipeline/vitarecomp.py build PCSG00351` rebuilt the playable `dump/decrypted/PCSG00351/recomp/game_host.exe` (SHA-256 7D6010B01B04D3F0BD3CD3E0F9D86F56B3E164F3182222CAA83111B82AA7583E). Prior binary copied before the build to scratch as `game_host-before-codex-instance.exe` (6ABE52D5362ACB3D92B130FE93D9B94AA8AED52E0DB52FDB2A16C57C6193E642). Initial sandboxed builds hit Windows access-denied replacing the executable/SDL DLL. The approved normal build completed. The stock launcher uses game_host.exe; no save or launch setting change is required for the fix.

## Intermittent loss of enhancements

The previous binary was run headlessly against an isolated copy of slot 1. With 4× and FSR forced off it reached the outdoor base. All 180 F5 history images (4621–4800) were present. All had 58 draws into the displayed buffer, zero skips and zero software draws. No obvious flash appeared in that static sample. The 480×272 PNGs precede the final window effects; the full-resolution pre-window sample is 3840×2176. See `flash/findings.md` and `flash/gameplay.log` in scratch. The log copied into the F5 folder in this headless test was an earlier startup log; use gameplay.log.

The window presenter normally sends the high-resolution GPU texture. If it uses guest memory instead, the game supplies a native-resolution image. The path is observable in an F5 history row ('from the GPU' / 'from guest memory'). An F12 replay cannot establish the path taken on a neighboring live present. Skipped FSR is unconfirmed; the Nova pack does not enable it by default. No presentation change was made on either hypothesis.


### Verification details

Draws 9761/936 and 9788/846 were isolated on the software interpreter. On an independent read of the 9761 draw outputs, draw 936 changed 9,113 pixels by at least 24/255 compared with draw 935. With only that draw's stride corrected, 244 pixels changed. The intended particle still draws. The independent multi-capture Vulkan replay above verifies the end-to-end visual effect. A second isolated headless history reached gameplay, and its PNG count, range and dimensions were checked directly.

The windowed test initially paused after its first present on both fixed and real clocks. Inspection of `runtime/ui/overlay.cpp` identified the first-run touch intro triggered by the isolated settings. Setting `touch_intro_shown=1` **only in the temporary test settings** let the same rebuilt executable advance. Two early diagnostic windows were closed by process ID. The fixed-clock process stack snapshot is in scratch/window-test/startup-stacks.txt. These first-run pauses are separate from the reported flash.

### Rebuilt playable host — live verification

- Both scripted runs of the newly built `game_host.exe` loaded the copied slot 1 and reached the outdoor base. The headless fixed-clock run saved three consecutive 3840×2176 pre-window render targets. Their mean absolute adjacent grayscale changes were 0.041 and 0.040 on a 0–255 scale.
- The real-clock **windowed** run recorded frames **4521–4700** in `window-gameplay/session.log`: all 180 came from the GPU, 59 draws each into the displayed buffer, zero skipped and zero software draws. The three subsequent 3840×2176 target dumps numbered 4721–4723 had mean absolute adjacent changes of 0.031 and 0.031 and nearly identical mean edge strengths (3.5131–3.5134). These full-resolution samples are before window post-processing. The window test exited successfully at the requested shot limit. Its background F5 encoder had written 74 PNG files on exit; all 180 source/counter rows were already in the live log. The earlier headless history has all 180 PNGs.
- Scripts in scratch: `fixed_base.py`, `window_test.py real`, `check_history.py fixed-base window-gameplay`. They use isolated settings, a copy of the game data and save, and separate logs. The archived original log and the player's session.log had the same SHA-256 after testing.
- **Status:** colored polygon fault corrected in the normal playable binary, demonstrated by controlled replay in four affected captures. Live smoke test reached the base. The exact desert encounter was not rerun on the patched binary. The separate intermittent visual loss was not reproduced. For the next occurrence, press **F5 immediately after the flash** and keep the resulting `captures/f5_<frame>` directory with its session.log; F12 can additionally capture a persistent color defect. Compare history source and skips on the affected frame with its neighbors. If the source is consistently GPU and the pre-window image is stable, capture the final window output to test the post-processing stage.

[All ten F12 frames](../../dump/codex-render-20261120/contact.png) · [Original and corrected replay pairs](../../dump/codex-render-20261120/paired.png) · [Single-draw software evidence](../../dump/codex-render-20261120/wedge/README.md) · [Windowed live test log](../../dump/codex-render-20261120/window-gameplay/session.log)


## Evening screenshot and F12 cross-check

Reviewed all 19 direct screenshots from the user-image batch sent at 17:41 Baghdad time and replayed the 13 evening F12 captures. The original attachments were recovered from the scoped Nova session as `dump/codex-render-20261120/review/direct/user-20261120-144149-01` through `-19` in their original formats. Nothing from the conversation text was copied into the report. Direct sheets `direct-sheet-1.jpg` through `direct-sheet-3.jpg` and `f12-review.png` are in the review directory. The batch’s frame inventory in `review.py` confirms 11 complete captures. Frames `62149` and `74696` end without a DONE record, with one and two complete presents respectively. Their images on the sheet come from the last completed present.

- **Kisara’s bridge report.** Direct screenshot 05 matches the grey and teal picture in F12 frames 49261, 25983, and the newest 26877. The bridge is also grey at Macgas’s reply in 49754. The later crew angle in 50497 and 50863 renders consoles and the seated character. Vita Part 1 at 18:45 is the matching reference, with Kisara visible at her console and the same 20% report. The wrecked-ship image in `ref/engine_pair.png` is a different shot.
- **New draw isolation in frame 26877.** The software replay shows bridge geometry after draw 36. Draw 37 introduces the large occluding surface and draw 38 leaves it in place. Draw 37 uses vprog `0x11103520`, fprog `0x1111ac80`, and 1,752 indices. The 363/1,752/1,932-index sequence at draws 36–38 matches frame 49261 despite changed shader and buffer addresses between sessions. Use the mesh sequence to match the draws across captures. See `bridge-review.png`, `draws-26877.txt`, and the relevant stop-draw logs. This narrows the bridge failure to the stage draw before the composite. It does not establish whether the underlying camera transform or a mesh transform is wrong.
- **Fildia’s “I have a request” shot.** Direct images 08 and 09 show the red-brown ground hiding her face and body with the 30.0 FPS overlay visible. F12 74253 shows the same shape and surviving hair and arm pieces. The Vita Part 2 13:17 reference shows her in front of the sky. Direct 11 and 13 show her clearly in nearby angles. This agrees with the earlier draw 1046 isolation and narrows the fault to specific shots.
- **Captain’s haze and enhancement flash.** Direct 10 and 12 show the captain clearly while the replayed present in 74696 is white. The stills do not establish that they are the same instant or reveal how long the haze lasted. None of this evidence isolates the previously reported one-frame loss of enhancements. The direct dream subtitle in 01 also shows the offset against its background box. That is a separate localization layout issue.

[Cuts compared against the Vita reference](../../dump/codex-render-20261120/review/cutscene-comparison.png) · [Bridge software draw steps](../../dump/codex-render-20261120/review/bridge-review.png) · [F12 contact sheet](../../dump/codex-render-20261120/review/f12-review.png)


## Correction to the bridge draw-timing test

The manual run reported as “defer off” actually ran with deferred draws enabled. I previously repeated the incorrect conclusion. The pasted excerpt matches the live log at frame 24649 (669.9 ms), frame 24650 (719.8 ms) and frame 27245 (78.7 ms). The same log says `gfx: draws held until their scene ends (RECOMP_DEFER_DRAWS)` at line 142. The run that recorded frame 26877 also logged deferred draws enabled. The scripted off/on tests stopped in the corridor before the bridge. The 30 FPS screenshot evidence for Fildia still stands.

I tested the environment construction in-process using the actual Nova pack and the launcher's game_env function. An inherited RECOMP_DEFER_DRAWS=0 became 1 when cmd_run applied RUN_ENV. Adding RECOMP_DEFER_DRAWS=0 as the last EXTRA_ENV word produced 0. To run a true immediate-draw control from PowerShell, use `$env:EXTRA_ENV = ($env:EXTRA_ENV + ' RECOMP_DEFER_DRAWS=0').Trim()` before launching the batch file from the project. Keep the same frame-rate setting and capture the same dialogue. Save the session log with the capture and check that the startup “draws held” line is absent. Close this test shell to discard its environment override.

If immediate draws restore the shot, compare the covering mesh's uniform values at submission and at scene end to identify the overwritten input. If it stays broken, check camera/model buffer binding, offsets and decoded matrix data against a working shot before tracing the game's matrix writer. The sky and ground can use different model origins. The observed difference alone does not justify applying a 13,500-unit offset. The review did not identify a confirmed fade-timer change or a visual scenery fix.

## Verified immediate-draw bridge capture, 23:24 Baghdad

The player's screenshot of Kisara's 20% report matches the newly completed F12 capture `frame_22815.vfc`. The startup log records 4×, reaches the first draws without the deferred-draw enable message, and records 60 FPS mode at frame 1698. It records capture start and completion (112.7 MB) and later reaches frame 25500. The 0.0 FPS readout in the supplied still is insufficient evidence of a lasting freeze. The previous enabled run explicitly logged draw holding. The corrected launcher override was verified above.

The new capture replays on Vulkan through 21 scenes and 570 draws. I stopped the software interpreter immediately after draws 36 and 37 in both 22815 (immediate) and 26877 (deferred). Draw 36 shows the consoles in each, and draw 37 covers most of the view in each. The covering draw uses the same 1,752-index mesh, index buffer 0x239dcb80 and vertex stream 0x23bbc25c/20 in both sessions. The first 256 bytes of vertex uniform buffer 0 were also saved at the two draw stops; the buffer address moved from 0x23a0cb10 to 0x23a2e090 between runs. These are separate moments and addresses, so a raw difference does not establish a bad writer. Use the mesh and draw signature to match later captures.

The bridge fault is now reproduced under both timing modes. A further toggle test for this bridge is unnecessary. The remaining diagnosis is the camera and mesh placement data or its interpretation in the shared draw path. This test does not identify a defective matrix or establish a common cause with Fildia.

[Immediate and deferred draw comparison](../../dump/codex-render-20261120/bridge-immediate/draw-comparison.png) · [Archived test log](../../dump/codex-render-20261120/bridge-immediate/session-22815.log)


## Kisara bridge camera comparison

The matching bridge mesh is draw 37 in failing frames 22815 and 49261 and draw 41 in working frame 50497. The 1,752 indices (3,504 bytes) and the 744-vertex span (14,880 bytes) are byte-identical across all three captures. The vertex shader binaries also match. The earlier provisional draw 609 candidate is a different batch. The shader declares cmWVS at offset 0 and cmWorld at offset 64 in its default vertex uniform buffer, container 14. Inspecting user vertex buffer 0 alone misses the transform used here.

In software replay at 960 × 544, the original wall draw changes 395,134 pixels in 49261 and 1,265 in 50497 relative to the image immediately before that draw. In diagnostic copies, replacing just the 64 cmWVS bytes immediately before the matched draw with the other shot's values gives 0 changed pixels in 49261 and 397,469 in 50497. These counts measure RGB changes at this draw stop. Both cameras belong to different scripted angles. Mixing them for one draw is a diagnostic control only.

In failing frame 49261 all 12 scenery draws from 29 through 40 use byte-identical cmWVS and cmWorld at their respective submission points. This rules out a unique captured matrix on draw 37 relative to those neighbors. The next diagnostic is to check which wall faces survive clipping, face culling and depth testing in Kisara's shot, and compare the intended camera framing with the Vita reference at the same dialogue before changing the game camera. These tests cover the bridge only. No runtime or launcher change was made in this comparison.

[Before, original and exchanged matrix for each shot](../../dump/codex-render-20261120/bridge-camera/camera-ab.png) · [Matrix replay script](../../dump/codex-render-20261120/bridge-camera/matrix_ab.py) · [Mesh and neighboring matrix verification](../../dump/codex-render-20261120/bridge-camera/check_mesh.py)
