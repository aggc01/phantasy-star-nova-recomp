# Another port's fix list, checked against ours (2026-11-19 evening)

The user pasted a fix list from another Phantasy Star Nova port on Project Nativ (commits d21405d, 6897b42, d2a85c5,
4ee0cb3, 92fcebb: in none of our checkouts). Workflow psnova-external-fixes-check: one checker per item reading our code,
logs and game data (read-only), and a second checker trying to refute every claimed gap or conflict. Raw results:
the workflow transcript (wf_ed9ea690-864).

**Their addresses are the 1.00 eboot's.** 0x81dd110c, 0x81a028a8 and 0x82256c1c are function starts in app0/eboot.bin.elf
(1.00, sha f4b3a669...) and fall inside other functions in the 1.05 eboot we build (elf/eboot.bin.elf, abb45e17...).
Their port runs 1.00 (or labels it wrongly); none of their addresses can be pasted into ours.

| # | their fix | we have it? | problem in ours? | verdict |
|---|---|---|---|---|
| 1 | entry inside a Thumb-2 instruction | yes (recomp.py:1337-1352, 2 such entries logged) | no | skip |
| 2 | missed varargs function + ARM seeds | no | **yes**, at 1.05 addresses | **take, adapted** |
| 3 | shader loops -> SPIR-V | yes, more general (block dispatcher, usse_spirv.c) | no (0 software draws in 14 M) | skip |
| 4 | CancelEventFlag / lookup cache / views per format | 2 of 3 (no lookup cache: not needed) | no | skip |
| 5 | mip-count re-upload crash | yes, same fix (gfx_gpu.c upload_texture) | fixed | skip (2 small gaps) |
| 6 | bound GXP header counts in usse.c | **no** | **yes: our startup freeze** | **take** |
| 7 | old target written back over new textures | partly (whole pages) | edge pages only | adapt |
| 9 | SceIme typing | partly (types "Nova" automatically) | no keyboard name entry | adapt (user-facing) |
| 10 | replace the bloom | no | no | **don't take** (conflicts) |
| perf | precise CB sleep tail | partly | **yes** (vblank waits) | **take their 20 ms tail** |

## The ones that matter

**6. The real cause of our 16-18 s startup freeze.** usse.c loops over GXP header counts without bounds. 18 of the
programs in the game's index (disc1/f00001.bin) have absurd counts; one has 2,702,302,092 uniform buffer entries, the
same number the other port quotes. The predicted-pipelines pass decodes them on the render thread while it holds
gfx_lock: about 18 billion loop iterations, during which the game and window threads wait. Our RECOMP_PIPE_PREDICT=0
(pack RUN_ENV) hid this by skipping the pass; frame-rate.md blamed the 192 pipeline builds (every pass actually
reports "0 shaders built"). Inferred from counts and timing, not traced. Fix: bounds in usse_gxp_sane and at each loop
(find_container, parse_vertex_layout, literals_load, usse_setup_registers), then one windowed run with predicted
pipelines back on: if the start stays fast, they can come back (fewer hitches in new areas).

**perf. Our CB sleep tail is too short.** kernel_cb_sleep waits on a winpthreads condvar until 2 ms before the
deadline, then sleeps precisely. But winpthreads' timed wait re-waits while GetTickCount64() < end, and GetTickCount64
moves in ~15.6 ms steps whatever timeBeginPeriod says. In the pre-fix trace (test62) about 31 % of the VSync thread's
WaitVblankStartCB returns came 2-16 ms late. An overshoot past the 2 ms tail skips the precise part. The other port's
20 ms tail keeps vblank waits out of winpthreads entirely. Fix: tail >= 20 ms, slices of max(250 us, left/2) (as
display.c's vb_sleep_until), then a per-edge trace. May matter at 60 fps (recording 9 showed 38.7 fps roaming).

**2. A missed function, same shape at 1.05 addresses.** 0x81e53e70 (`mov ip, sp; push.w {r0-r3}`, the twin of their
0x81dd110c) is not in our build; its pointer is built in FUN_814ef956 (movw/movt through a register copy the analyzer
doesn't follow) and stored in a Function object, so a call through it would stop the game. Also 5 ARM entries
(0x81a687a0, 0x81a688e8, 0x81a698a4, 0x81a698b4, 0x81a698c4: switch heads and thunks). Of 22,651 Thumb code pointers in
the ELF's relocations, 0x81e53e70 is the only one that lands on uncovered code. Fix: FUNCTION_SEEDS for 1.05 in
pack.toml, re-analyze, recompile, check_labels, rebuild.
Found on the way (item 1): **fn_8213e768 is compiled as ARM but is Thumb** (recomp.py:1312 collects blx targets from
the Thumb misdecode of an ARM function); its first instruction is UNIMPL, a latent stop if the game reaches its two
callers. Fix in the same recompile.

**9. Name entry.** Ours answers the name box with "Nova" (or RECOMP_IME_TEXT); the player can't type a name. An
overlay text card (ImGui InputText, Enter/Esc/paste, 10 characters) would; keep the scripted answer for windowless runs.

**10. Don't take the bloom replacement.** Their chain description is right (240x136 bright pass, 120x68 blur, ~1.4x),
but their "textures were fine" is not: 18 of 85 textures in our frame-17600 capture are sRGB, and without RECOMP_SRGB=1
they are sampled raw (washed out). With sRGB on and the original bloom, our frames match the real Vita. A thresholded
bloom on top would darken mid-tones by roughly 30-35/255. At most an opt-in "Modern" look option, never the default.

## Smaller follow-ups found by the checkers

- Item 5: the in-place texture release can still hit a binding in the draw being built (bind before batch_add); a cube
  with the same bytes keeps its old object. Fix: the mip count in the texture key, or a pending-release list.
- Item 7: our kept pages are whole pages; a target's partial first and last page are not checked (hash them at arm time).
  The "12 downloads keeping pages" in the journal is the log cap, not a count.
- Item 3: the only software-path draws in all our logs: 3 a frame in the Filldia cutscene, fragment programs 0x11155700
  and 0x1113f150, "SMP: texture unit -1 has no sampler slot".
- README.md:57-59's reason for the two mid-instruction entries is wrong (they come from bl encodings read from the
  middle of real bl instructions, not data words).

## Taken (2026-11-19 evening, user: "Yes, all three")

1. **Header bounds** (runtime/gfx/usse.c: h_table_count / h_table_count_at, used by find_container, parse_vertex_layout,
   literals_load, usse_setup_registers, usse_param_resource; usse_gxp_sane rejects blobs whose tables don't fit).
   test95 (windowed, predicted pipelines ON): the predicted pass "45 fragment programs ... 0 not translated ... 220
   pipelines ... **1.0 s**" (was 9 not translated, 192 pipelines, 17.8-18.7 s, test76); frame 300 at **6.4 s** (23.5 s
   before with the pass, 6.8 s without it); the startup hitches are the same as test77's with the pass off. So the freeze
   was the loops, as the check inferred. Pack RUN_ENV no longer sets RECOMP_PIPE_PREDICT=0.
2. **20 ms CB sleep tail** (runtime/core/kernel.c kernel_cb_sleep; RECOMP_CB_SLEEP_TAIL_US, default 20000; slices of 1 ms,
   250 us in the last 1.25 ms). Windowed title at 60 fps, RECOMP_LOG_IMPORTS=WaitVblankStartCB, ~4400 waits each
   (scratchpad scripts vsync_iv.py / late.py):

   | | p10 | p50 | p90 | p99 | max | > 18.7 ms | returns 2-16 ms after the edge |
   |---|---|---|---|---|---|---|---|
   | 2 ms tail (test96) | 11.8 | 16.5 | 22.4 | 30.2 | 31.7 | 729 | 1893 (43 %) |
   | 20 ms tail (test97) | 16.4 | 16.6 | 17.0 | 17.3 | 17.8 | 0 | 0 |

3. **Missed functions** (pack.toml FUNCTION_SEEDS for 1.05; recompiler/recomp.py: blx targets only from functions that stay
   Thumb). Re-analysed: 6 functions added (0x81e53e70 and the five ARM ones). 21 dropped: the 20 case blocks of the two
   seeded ARM switch heads (each referenced only by its switch's table at 0x81a687c0 / 0x81a68904; the recompiled table
   jump goes to them as labels: `JUMP(t)`), and 0x81e53e76, now the second instruction of 0x81e53e70 (nothing refers to
   it). ARM functions 446 = the analysis' 446 (was 462 against 461: the misdecoded one is gone); fn_8213e768 decodes as
   Thumb (`push.w {r4-r11, lr}`). check_labels: 115 files, 0 missing. Review: one over-read in the new sane check
   for 128-151-byte blobs, fixed (fields beyond the blob are skipped), plus usse_param_resource and junk-ARM blx sources.
   The junk refinement in recomp.py came after this recompile; it changes nothing here (no junk-ARM function adds a blx
   target: the ARM count equals the analysis').
