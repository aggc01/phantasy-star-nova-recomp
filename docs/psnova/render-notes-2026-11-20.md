# Render work, 2026-11-20

Other render work the same day is in `render-investigation-2026-11-20.md`; the long-form
diary of everything is `picture-faults.md` (sections dated 2026-11-20). This file is the short map.

## What is in the playable build (`dump/decrypted/PCSG00351/recomp/game_host.exe`)

Each change keeps a switch to turn it off and a backup of the previous exe in the same folder (`game_host-before-*.exe`).

| Change | File | Switch | Why |
|---|---|---|---|
| Instanced draws expanded one draw per instance | runtime/gfx/gxm_sony.c `o_draw_instanced` | `RECOMP_GXM_ONE_INSTANCE=1` = old | particle strips joined every particle (orange stripes, beams). The instance-stream handling was later extended to single draws (the real cause of the coloured wedges). |
| LINES: 2D lines as GPU quads | runtime/gfx/gfx_gpu.c `lines_as_quads` | `RECOMP_NO_LINES=1` drops lines | the shadow image's border lines (dark bands on the ground) without the software round trip |
| LINES: 3D lines natively (LINELIST pipeline) | gfx_gpu.c `g_lines_draw` (pipe key/PipeEntry.lines, cull none, no motion pass, no recipe) | `RECOMP_GPU_SOFT_LINES=1` = software path | battle hit sparks were ~120 software draws a frame: 60-190 ms frames ("fps tanks when the team attacks") and native-resolution frames ("blurred frames") |
| Partial edge pages of render targets protected | gfx_gpu.c `edge_arm`, `kept_pages_find`, `target_rewritten_under` | none | a stale write-back overwrote the start of Nova's costume texture ("clothes change") |
| Draws held until their scene ends | runtime/gfx/gfx_dispatch.c `defer_draws`, `draws_flush` | `RECOMP_DEFER_DRAWS=0` = draw at the call; on via packs/PCSG00351/pack.toml RUN_ENV | was aimed at the coloured wedges; the instance-stream fix addresses the actual cause there. Kept on: it matches the console's timing. One unexplained 82 s freeze in one of three test runs (test111); not seen since. |
| Launcher log pump decodes UTF-8 incrementally | pipeline/vitarecomp.py `tee_run` | none (old script: `vitarecomp.py.before-tee-fix`) | half a Japanese character in a chunk made Python's console writer spin forever; the game blocked in fprintf (freeze at the load-game list) |
| Depth clip switch | gfx_gpu.c `pipe_create_info` | `RECOMP_GPU_DEPTH_CLIP=1`, OFF by default, not in RUN_ENV | tried for the Fildia fault below; changed nothing |

## Open faults (user screenshots and F12 captures, evening of 2026-11-20)

Captures: `dump/decrypted/PCSG00351/recomp/captures/frame_*.vfc`; work files: `dump/user-captures-2026-11-20e/`.
Replay: `build/gfxreplay-gpulines.exe <vfc> out.ppm` with `RECOMP_GFX=gpu RECOMP_SRGB=1`, and
`RECOMP_REPLAY_KEEP_TARGETS=1` when stopping mid-frame with `RECOMP_REPLAY_DRAWS=k` (without it the stop picture can be
a restored snapshot, not the real result). Real-Vita frames: `C:\New PATH\screenshots\...` (1 fps, 1080p) and contact
sheets in `dump/reference/part1|part2/`, index in `reference-index.md`.

1. **Scenery drawn over the characters in some cutscenes** (same pattern twice, software and GPU replays agree, so it is in
   the data as recorded at scene end):
   - Fildia "I have a request" (frame_74253; Vita part2 13:17/13:22): correct after draw 1045, then the ground
     (draw 1046, v 0x1110a2a0 f 0x1116f8b0, GREATER_EQUAL no write, cull none, default uniforms in GAME memory
     0x237eda20/0x237edb90 double-buffered) covers the screen. Reversed depth (0.5 + 0.5 * ~30 / w); the ground's vertices
     land at w ~ 100-160 (some behind the camera), the characters much further. Still wrong at 30 fps (user, 2026-11-20).
   - Bridge, Kisara "Report from the engine room ... down to 20%" (frame_49261/25983; Vita part1 18:45): the bridge
     draws (consoles visible at draw 30), then big stage meshes (draws 34-35, v 0x11112fd0 f 0x11122ec0, depth 6/1,
     shared user uniform buffer 0 = 0x23ab4a90 in game memory) cover it; the final picture is grey with a teal floor.
   - Common: stage geometry whose transforms come from game-memory uniform buffers ends up in front of the camera.
     Candidates: the stage's transform data is wrong when the draws run (timing of when the game writes it vs. when we
     read it), or game code computes it wrong. A/B test tried: `dev/psn-logs/run_bridge_ab.sh` (slot 2 of a COPY of the
     user's saves, RECOMP_DEFER_DRAWS 1 vs 0, shots every 100 frames to `dump/user-captures-2026-11-20e/bridge/d1|d0`). Inconclusive: slot 2 starts at the dream
     sequence ("And then...") and the bridge needs the player to walk there; scripted inputs stop in the corridor. Both runs
     drew the dream and the corridor correctly. Next: the user plays to the bridge with RECOMP_DEFER_DRAWS=0, or a
     movement script is written, or an F12 capture is made with draws at the call (defer 0) to compare stage matrices.
2. **White haze on the captain shot** (frame_74696): the cutscene composite (fprog 0x11109e00: main image + 120x68 blur
   through csmMat3x4) gets a colour matrix with +0.42 on every channel: the game is mid fade-to-white. Gone at 30 fps in
   the user's run, so a 60 fps timing issue. Suspect from 60fps-sites.md: fn 0x8186ec1c / 0x81fcc168 compute a fade step
   of 1/30 per frame. Not fixed.
3. **"Ghost" halo around characters:** the real Vita has the same soft glow outline (part2 frame 13:22, pale band beside
   Fildia's hair), so it is the game's own effect; 4x makes it more visible. Not a bug; a later option could soften it.
4. **Subtitle box offset to the right of its text** (English, "And then..."): text layout, the localization session's area
   (`docs/psnova/localization-notes.md`), not changed here.
5. **Frames that appear without the enhancements:** not caught yet; press F5 right after one (keeps the previous frames).

## Rules this session followed

Game imagery stays out of git; nothing committed; user saves backed up before test runs
(`dump/save-backups/`), tests start from copies (`TEST_SAVES`); the l10n session's files are not edited.

## Update, late 2026-11-20

- **User test: bridge shot still grey with RECOMP_DEFER_DRAWS=0** (and the Fildia shot was broken at 30 fps). So neither
  the draw holding nor the frame rate causes "scenery over characters". The renderer draws what the game gives it
  (software = GPU).
- The one untranslated program in that session (0x110ff3c0, "SMP: texture unit -1 has no sampler slot", software path) is
  in none of the bad captures: unrelated. The "game reads target ... on the CPU" lines are memory reuse of old targets.
- **Bridge (frame_49261):** the room pieces that cover the shot are draws 36-37 (v 0x11112fd0 f 0x11122ec0, cull CW,
  depth GE+write, user uniform buffer 0 = 0x23ab4a90 in game memory, shared by all stage draws 34-60); grey by draw 38.
- **Lead for the Fildia ground (frame_74253 draws 1046-1048, vprog 0x1110a2a0, the same vprog as the sky at 764):** the
  vertex uniforms hold a view-projection whose rotation rows equal every other draw's (same camera) plus a model block.
  The sky's model block translates by (-13500.1, 0, 0); the ground's has no x/z translation (0, -2.48, 0, and a 5.0)
  while its vertices sit at x ~ -13600, z ~ -8400. If the ground should share the sky's world offset, its block is missing
  it and the mesh lands ~13500 units off, near the camera. The ground's block lives in game memory (0x237eda20 /
  0x237edb90, written by game code, double-buffered), unlike most draws' (SceGxm ring). Next step: find the game code
  that writes 0x237eda20 (watch the address, e.g. guestwatch or a write trace) and compare its inputs with the sky's.

## Fade check, late 2026-11-20

- New diagnostic: `RECOMP_LOG_FPROG=<hex>` (gfx_dispatch.c `draw_now`) logs, for each draw whose fragment OR vertex program
  has that address, the time and the first 8 words of its default fragment uniforms. Off by default. The cutscene
  composites share vprog 0x110fbc20 (gameplay composite fprog 0x110fbee0, cutscene ones 0x11109e00 and 0x11109830).
- `dev/psn-logs/run_fade_ab.sh` (slot 2 of a save COPY, 60 vs 30 fps) did not reach the captain scene: the dream sequence
  uses the gameplay composite, without a colour-matrix fade. Inconclusive.
- Re-read of the evidence: on the real Vita the captain shot (part2 13:29-13:38) cuts to a very bright sky shot (13:39);
  frame_74696's +0.42 offset may be that transition caught mid-way, not a wrong fade. The user's 30 fps run simply may not
  have caught the moment. The 1/30 step at 0x8186ee46 belongs to PileFadeOut (a UI/pile fade-out), not obviously the
  cutscene's. NOT changed: no evidence a fix is needed. To settle: at 60 fps, does the captain shot stay white for long,
  or only flash white just before the cut to the sky?
- Scenery placement trace: the ground's uniform block (0x237eda20) is written by game code; finding the writer needs a
  live session at that shot with a write watch (guestwatch on the page, reporting the writing guest function). Not done.
