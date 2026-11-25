# Picture faults (2026-11-20, in progress)

Me: dark bands while walking, "magenta", haze, "sun rays from random places" (Recording 2, Recording 4B, rec 9).
Plan: C:\Users\<user>\.claude\plans\c-users-user-onedrive-desktop-recordin-glowing-meadow.md.
My F12 captures: `dump/decrypted/PCSG00351/recomp/captures/frame_4466/4505/5110/5908.vfc` (copies of the session log
and work files in `dump/user-captures-2026-11-20/`). 5110 and 5908 show the bands; 4466/4505 (bridge) don't.

## Dark bands

- The character's shadow is an image (scene 1, 512x512 8-bit target at 0x1f8e0040: red = lit, black = shadow) projected
  onto the ground by a perspective projector (`eProjector_Projection_Matrix0`, fragment iterator: unit 1, coord src 3,
  projective mode 2 = divide by .w; sampler CLAMP both ways). GPU and software renderers draw the image identically.
- **Line primitives were dropped by both renderers.** The shadow pass ends with draw 12: four LINES at the image's edge
  pixels (0.5 .. 511.5), white = lit, so the ground the projected image doesn't reach repeats a lit texel. Without it the
  edges kept the character's head and feet. Fixed: `gfx_soft.c render_lines_interp` (one-pixel quads through the game's
  own programs), `gfx_gpu.c` hands LINES draws to the software path (`RECOMP_NO_LINES=1`: drop them as before). Checked
  in replay: all four edges lit after the pass in every frame of 5908.
- **The bands remain after that fix**, identical on GPU and software replays, so they come from the game's data as we
  run it, not from the GPU translation. Not back-projection: `RECOMP_PROJ_BEHIND=out` (experiment switch, off by default,
  usse_spirv.c) changed nothing. The projector looks almost horizontally (its w row's y ~ 0.004) in every capture,
  bands or not; the ground pixel traced so far reads outside the image (lit). Next: find which ground pixels read the
  silhouette and why (per-pixel trace, `RECOMP_DEBUG_DRAW=all RECOMP_DEBUG_PIXEL=x,y` on the software replay).

## Not the cause (checked)

- Border address modes: no texture in any capture uses GXM modes 5-7 (gfx_gpu.c maps them to clamp-to-edge; Vita3K
  doesn't implement them either).
- Our soft-shadow filter: it applies only to samplers named "shadow"; this game's are `sTex_0/sTex_1`.
- Visibility tests (for the light beams): none in any capture or in the scripted route to frame 23000 (`RECOMP_LOG_VIS=1`).

## Open

Blue-violet flicker, haze, light beams: their captures are still to be analysed (my four captures are all field
walking; the flicker and beams were in a cutscene).

## Orange striped panels, yellow-white wedges and beams (2026-11-20, FIXED in game_host.exe 11:03)

My second batch of F12 captures (34, `dump/user-captures-2026-11-20b/sheet_*.png`): stripes in 39805, 39862, 41509,
42340, 44995; wedges/beams in 27537-27749, 37353, 39914-40913. The real-Vita desert fights (Part 2, 225-360 s) show
neither. GPU and software replays draw them alike (data, not translation). Bisect of 41509 (pixel 622,279): draw 292, a
particle effect (32x32 sprite texture) as a TRIANGLE_STRIP of 92 indices with a second stream of 4-byte records: an
**instanced** draw (sceGxmDrawInstanced, index wrap 4 = one quad per particle, the per-particle data an instance-index
stream). `gxm_sony.c o_draw_instanced` drew it as ONE instance of all 92 indices: one long strip joining every particle to
the next. Fixed: one draw per instance (count / wrap of them), instance streams (index source bit 1 in the vertex
program's {stride, index source} table) stepped one stride per instance and read with stride 0 inside it.
`RECOMP_GXM_ONE_INSTANCE=1` = old behaviour. Captures can't show the fix (they record the merged draw); the arena route
(test99, to 25000) runs with normal attack effects and no crash; the desert needs my play test.

## Still open
- Dark bands (above): the line fix is in, the bands remain; next is the per-pixel trace of a band pixel.
- Blue streaks / glow (32386, 39510, 39540), "blurry frames", costume changes: not analysed yet.

## Slowdown after the 11:03 build, and the costume blocks (2026-11-20 afternoon)

- **30 fps, down to 0 (me):** the line fix's software path round-tripped the 512x512 shadow image every frame (4 MB down
  and up at render scale 4x): render 16 ms, 30 fps (test103); without lines 2.7 ms, 60 fps (test102); instancing costs
  nothing. Now `gfx_gpu.c lines_as_quads`: 2D lines (F32 position in the target's pixels, z 0, w 1, one stream) become a
  triangle list in a guest scratch buffer and draw on the GPU; anything else still uses the software path. test107:
  60 fps, render 2.5 ms, "lines drawn as quads on the GPU".
- **Costume blocks (me: "clothes change"):** F12 capture frame_7093: Nova's costume texture 0x1fa70040 has its first ~3 KB
  as coloured blocks (GPU and software replays alike: the bytes in memory). The texture starts in the partial last page of
  an old render target; kept pages covered whole armed pages only, so a stale download overwrote it. Now `edge_arm` hashes
  a target's partial first/last page at arming and `kept_pages_find` / `target_rewritten_under` keep them when the game
  rewrote them. test109: fires on three old targets right after loading the save (0x1fa80040, 0x1fb90040, 0x1fc80040);
  60 fps.
- **Spamming Start at launch:** no crash in test108 (100 s); no Windows crash record for my crash.

## Freeze at the load-game list (2026-11-20 13:xx, FIXED in pipeline/vitarecomp.py)

Not the game: the launcher. `tee_run` copied the game's log to its console in raw 64 KB chunks; a chunk ended in the middle
of a Japanese character (the save slot name `Nova/フォー…`), and Python's Windows console writer loops forever on half a
character (python.exe at 100 % of a core). It stopped reading the pipe, the pipe filled, and the game blocked in its next
`fprintf` (lldb: the main thread and a loader thread both in fprintf; session.log and the console end on the same half
character). Now the console gets whole characters through an incremental UTF-8 decoder and a console that refuses a write is
dropped (the log file still gets every byte). Old script: `pipeline/vitarecomp.py.before-tee-fix`. Tested with a child that
splits a character across two writes. Likely also the "stale black screen" after spamming Start (any Japanese log line can
trigger it).

## Battle slowdown + "blurred frames" + rainbow streak (2026-11-20 afternoon)

- **Slowdown (me: fps tanks when the team attacks, boss fight to 0 fps):** the hit sparks are instanced 3D LINES draws
  (frame_27118: 373 line draws, ~120 per 960x544 scene, n 2 each, instance stream stride 0). `lines_as_quads` only takes 2D
  lines, so every spark went to the software path: the 960x544 main target and a 512x512 one downloaded and re-uploaded
  2-3 times a frame (session log: 17-25 ms of target downloads a frame, frames of 60-190 ms). Now `g_lines_draw`: a
  LINELIST pipeline (pipe key/PipeEntry.lines, cull none, no motion pass, no recipe), the game's own line indices.
  One pixel wide at the render scale (SDL_GPU has no line width). `RECOMP_GPU_SOFT_LINES=1` = the old software path.
  Replay of 27118: final picture identical to the old path (framediff 0.00). test110 (base, 4x): 60 fps, 0 sw draws.
  game_host.exe 13:39 (old: game_host-before-gpulines.exe; source backup runtime/gfx/gfx_gpu.c.before-gpulines).
- **Blurred frames:** most likely the same software detour: a software draw renders into the target's 960x544 copy, so
  that frame loses the 4x detail. Expected gone with the lines on the GPU; to be confirmed by me.
- **Rainbow wedge (OPEN):** draw 572 of 27118 (scene 12, 480x272 2x2 MSAA; a trail/ribbon strip, v 0x1111af40 f 0x1111b590,
  strip n 4, stream 0x23d798d0 stride 56). Only the first two vertices are written; the rest is stale memory with another
  layout (64-byte records, NaN/1e12). Hypothesis: the game fills the ribbon's vertices AFTER sceGxmDraw (legal on the Vita,
  whose GPU reads them after the scene is kicked) while our observer draws at call time. Fix would be deferring a scene's
  draws to EndScene. Report: dump/user-captures-2026-11-20d/wedge-bisect.md.
- Fog capture (me: "positional fog"): not analysed yet.

## Draws held until their scene ends (2026-11-20 14:00, game_host.exe 13:51)

For the rainbow wedge: `gfx_dispatch.c` `RECOMP_DEFER_DRAWS=1` queues a scene's GfxDraw copies and draws them at
EndScene (also before the next BeginScene, a present, sync-to-guest, a guest read, a transfer downscale), so vertices,
indices, uniforms and textures are read when the console's GPU would read them. On in PCSG00351's RUN_ENV only; other
games unchanged. Old: game_host-before-deferdraws.exe, gfx_dispatch.c.before-deferdraws.
- test112 (base, 4x): 60 fps steady, 202 draws, 0 software. test113 (arena route to frame 25000, fights): no abort, the
  weapon-swing trails (the same ribbon effect) are clean arcs (dump/user-captures-2026-11-20d/arena/sheet_small.png).
- test111 (same as test112) had ONE 82 s freeze entering the base (frame 3667, nothing in the log); not seen again in
  test112 or the 14-minute arena run. Watch for it; RECOMP_DEFER_DRAWS=0 in the environment turns the holding off.
- Old captures recorded memory at the draw call, so they still show the wedge; a new F12 capture records it at scene end.

## Cutscene faults from my 16:5x F12 captures (2026-11-20 evening; other render work is in render-investigation-2026-11-20.md)

Twelve new captures (49261 ... 74696), replayed with build/gfxreplay-gpulines.exe, RECOMP_SRGB=1; contact sheet and work
files in dump/user-captures-2026-11-20e/. Software and GPU replays agree for both faults below (the game's data, as recorded
at scene end since RECOMP_DEFER_DRAWS). Real-Vita reference: dump/reference/part2/sheet_00-13-09/-13-25/-13-57.jpg.

- **White haze (74696, the captain lying on the ground; Vita 13:29-13:38 shows it vivid):** the main scene is fine; the
  cutscene composite (scene 10, draw 351, fprog 0x11109e00: main image + the 120x68 blur through csmMat3x4) gets a colour
  matrix with ~+0.42 added to every channel (fragment uniforms as halves, columns 4 = 0.429/0.423/0.416) -- the game is
  mid fade-to-white. 74253's matrix is a normal grade (offset -0.02). On the Vita the white-out comes later, on the sky shot
  (14:01-14:05). Suspect: a fade stepped per frame at 60 fps (60fps-sites.md: fn 0x8186ec1c / 0x81fcc168 compute colour
  x 1/30 per step, "if added once per frame, the fade runs 2x fast at 60 fps"). NOT proven: needs the scene at 30 fps.
- **Fildia missing (74253; Vita 13:17/13:22 shows her in full against a cloudy sky):** after draw 1045 the picture is
  right; draw 1046 (ground, v 0x1110a2a0 f 0x1116f8b0, n 96, depth GREATER_EQUAL no write, cull none, uniforms in game
  memory 0x237eda20/0x237edb90, double-buffered) covers the whole screen; only her hair and gauntlets, drawn after it,
  remain. The same happens in all three frames of the capture (draws 316, 681, 1046). Depth is reversed (depth =
  0.5 + 0.5 * ~30 / w): the ground's vertices come out at w ~ 100-160 (some behind the camera), the characters' far
  further away, so the ground is genuinely nearer in the data we draw. Depth clipping does not change it
  (RECOMP_GPU_DEPTH_CLIP=1, new switch in gfx_gpu.c, off by default, not in RUN_ENV; replay identical). So either the
  ground's matrix is wrong (game code) or the draw should not happen on this shot.
- **Engine-room shots (49261, 25983; Vita part1 20:29-20:33 shows the wrecked ship in dust):** ours shows grey haze only;
  not analysed yet, possibly the same family.
- Next: a live run of this cutscene at 30 fps (F10 menu) and one with RECOMP_DEFER_DRAWS=0, to split "60 fps timing" from
  "draws held to scene end". My slot 2 (15:39, 0:04 play time) is just before it.
- 2026-11-20 late: my 30 fps run -- captain shot no longer white (haze = 60 fps timing), Fildia "request" shot and the
  grey bridge shot unchanged (not frame rate). Ghost halo is in the real Vita too (game effect). Bridge A/B from slot 2 did
  not reach the bridge (needs walking). Summary: render-notes-2026-11-20.md.
- 2026-11-20 late: bridge still grey with RECOMP_DEFER_DRAWS=0 (me). Not the draw holding, not 60 fps. Lead (model block
  of the Fildia ground lacks the sky's -13500 world offset) in render-notes-2026-11-20.md.
