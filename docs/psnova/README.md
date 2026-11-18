# Phantasy Star Nova (PCSG00351): state of the recomp

The one state file for this game. Correct it in place when a finding changes; give every claim its strength:
**proven** (repeated, or seen by the user), **single run**, or **untested**.

The journey behind it (what was tried, the dead ends, the techniques and the traps): [journal-2026-11-18.md](journal-2026-11-18.md).
Read that before debugging anything here.

## The game

| | |
|---|---|
| Title | ファンタシースター ノヴァ (Phantasy Star Nova), tri-Ace / SEGA, PS Vita, 2014 |
| Title id / content id | PCSG00351 / JP0177-PCSG00351_00-NOVAAPPLICATION0 (Japan) |
| Player's copy | `F:\RECOMP GAMES\Phantasy Star Nova (v1.05)`: `app` (1.00, encrypted, NoNpDrm `work.bin`), `patch` (1.05), `rePatch` (English fan translation: two CPK archives) |
| Main program | NovaMRom, `eboot.bin` (28.4 MB as ELF); 1.05 SHA-256 `abb45e17...edcf3`, 1.00 `f4b3a669...2542` |
| System libraries it imports | 33 libraries, 500 functions: GXM, libc, kernel, NGS (sound), AvPlayer (movies), Fiber, SaveData/IME/NetCheck dialogs, NP Trophy, Net (offline) |
| Data | CRI CPK archives: `NOVA_FileList_Vita.cpk` (2.8 GB), `_movie.cpk` (395 MB), the update's `_patch.cpk` (155 MB) |
| Code size | 39,840 functions found; 7.7 M instructions translated to 1.1 GB of C in 100 parts |

## How it is built here

Everything runs from this worktree with the main Uncharted checkout's Python and toolchain, read by path:

```bash
bash dev/psn_build_all.sh                    # import -> analyze -> recompile -> build, logs in dev/psn-logs/
STAGES="build" bash dev/psn_build_all.sh     # one stage
```

The pipeline driver by hand: `"<main checkout>/.venv/Scripts/python.exe" pipeline/vitarecomp.py <stage> PCSG00351`
with `ATIV_WIN_TOOLCHAIN=<main checkout>/toolchain`.

Stages as run on 2026-11-18 (single run each):

| Stage | Result |
|---|---|
| `add app` (decrypt 1.00 with `work.bin`) | 32 s, 6 programs decrypted, 0 failed (one `sce_sys/about/right.suprx` hash note, not game code) |
| `add patch` (1.05) + import | update decrypted, `app0_patched` = 98 hard links, version recognised as 1.05 |
| `analyze` | 248 s; main 39,840 functions; libc 1,562, libgxm 470, libgpu 65, SceMp4 273, SceAvPlayer 299 |
| `recompile` | 278 s; 5,541 of 7.7 M instructions "unsupported" (coprocessor/`svc` forms: data decoded as ARM in literal pools, judged harmless until a run reaches one) |
| `build` | ~6 min after a recompile, ~30 s after a runtime-only change; `game_host.exe` 164 MB |

## Changes made to Project Nativ on this branch

- `pipeline/vitarecomp.py`: **`repatch <title> <folder>`** copies a rePatch folder to
  `dump/decrypted/<title>/repatch0`; `import` layers it over the game and update into `app0_repatched` (hard links).
  `RECOMP_NO_REPATCH=1` at import plays without it. Untested at the time of writing.
- `recompiler/recomp.py`: **a function is never switched to ARM when its ARM decode has no instruction at its entry.**
  The first build failed in 3 of 100 parts (`goto L_8102e9dc` and two more with no label): analyze.py gives some entries
  chunks of a Thumb switch's shared tail that start *below* the entry; the junk test reads a literal pool there as
  coprocessor code, the function was re-decoded as ARM, and the ARM decode skipped the entry. Only functions that failed
  to compile change, so builds that worked before are unaffected. The recompile prints the functions it kept Thumb
  (one: 0x8102e9dc). With it, "unsupported" instructions fell from 5,541 to 842: far fewer data words decoded as code.
- `recompiler/recomp.py`: **an entry that falls inside an instruction of its own linear decode is decoded from the entry
  itself.** The other two failures: 0x819b2852 is the second half of a `bne.w`, 0x811cc1f6 the second half of a `movt`,
  inside ordinary Thumb code, so these entries come from data words that look like code pointers and are never jumped
  to. Again only functions that failed to compile change; the recompile prints them.
- `runtime/platform/platform_win32.c` `plat_gpu_cache_private()` (called first in `main()` and before the GPU device):
  **NVIDIA's shader cache goes to `nvidia-cache\` beside the program**, 4 GiB, unless `__GL_SHADER_DISK_CACHE_PATH` is
  set. Every Nativ program is `game_host.exe`, the same name as the Uncharted build; NVIDIA keeps one 1 GiB cache per
  exe name and deletes other names' caches when full (memory note `nvidia-shader-cache-limit`).
- `dev/psnova/check_labels.py`: checks the generated C for gotos without labels (23 s), before a build; part of
  `dev/psn_build_all.sh` after every recompile.
- `recompiler/analyze.py` `arm_pointer_targets()`: **ARM functions reached only through even words** (ARM code
  pointers) are found. The first boot stopped at `call to 0x8209d688: neither recompiled code nor an import`: a vtable
  slot (`ldr r2, [r1, #8]; blx r2`) holding an even address, i.e. an ARM method, in a 36-byte gap no body covered. The
  whole vtable is ARM methods. `dev/psnova/even_pointers.py` found 84 such uncovered, cleanly decoding ARM accessors
  (one rebuild instead of ~84 crash-and-reseed rounds of ~15 min), and showed that no existing function was decoded in
  the wrong mode (the 500 "Thumb" targets of even pointers that also decode as ARM are all import stubs).
- `runtime/core/main.c` `RECOMP_IMPORTS=1`: the report now scans the main program up to the modules (0x88000000); it
  stopped at 0x82000000 and missed most of this 20 MB program's imports (186 listed instead of 649).
- The run's own miss log recorded 0x8209d688 as `thumb` (its rule: Thumb when the caller is Thumb); a `blx` to an even
  address enters ARM. Corrected by hand in `dump/decrypted/PCSG00351/analysis/seeds.txt` (old file kept beside it).
- `runtime/core/kernel.c` **`sceKernelCancelEventFlag`** (was a stub): wakes every waiter with WAIT_CANCEL, sets the
  pattern, writes the count. The game hung after frame 1 without it: the Aska engine starts each worker thread by
  "cancelling" its flag with pattern 2 (the worker waits for bit 2, runs its job, exits when the job returns).
- `runtime/audio/ngs.c`: **the NGS voice definitions this game uses** (ATRAC9 voice = the Scream ATRAC9 player,
  Template1 = the PCM player, mixer/EQ/delay/distortion/pitch-shift busses passed through, said once each).
  `runtime/gfx/display.c` **`sceAudioOutReleasePort`** (frees the slot, keeps the host device for a same-format reopen).
- `runtime/core/sysmem.c`: **memory blocks aligned by type as on the console** (CDRAM 256 KiB, phycont 1 MiB, others 4 KiB;
  the log line shows the type). The AvPlayer carves its H.264 decoder's memory out of the game's block at 1 MiB
  alignment; at 4 KiB alignment it no longer fitted and every movie played sound over a black screen.
- `runtime/media/video.c` `sceAvcdecQueryDecoderMemSize`: **whole MiB** (was 256 KiB rounding): the AvPlayer sizes the
  block as library + this rounded up to MiB, which only fits the aligned carve when this is a whole MiB; the second
  movie (0x240000) lost its video otherwise. With both: all three start-up movies decode (150, 240 and the opening's
  pictures), proven by screenshots of each.
- `runtime/gfx/display.c` `RECOMP_CTRL_BACKTRACE=1`: the native stack of the first controller read per caller (the
  guest call chain, symbolised with llvm-nm on the program).
- `runtime/gfx/display.c` **`SceCtrlData` written as 0x20 bytes, not 64** (the fix that made buttons work): see "The
  button problem" below. Every Nativ game had this overflow; the Uncharted copies still do.
- `packs/PCSG00351/hooks.c` + pack `HOOKS`/`IHOOKS`: input-thread trace hooks (`RECOMP_PSN_INPUT_TRACE=1`, off by
  default), kept for the next input question.
- `recompiler/analyze.py` `arm_function_at`: the ARM rule only needs the *first* instruction unconditional and rejects
  text by its bytes; a run-recorded "thumb" miss that is 4-aligned, stored as an even pointer and an ARM function is
  taken as ARM. Fixed the character-creation crash (`0x822b0d6c`, `cmp r1, #0; beq ...`); 100 ARM functions found.
- `runtime/gfx/usse_spirv.c`: **loops in GPU shaders** (a dispatcher for programs with backward or unstructured
  branches). Character creation's skinned characters were drawn by the software path before (slow, broken).
- `runtime/core/apputil.c`: **`sceImeDialog*`** answers at once ("Nova", the game's initial text, or `RECOMP_IME_TEXT`).
- **Gameplay recorder**: `RECOMP_VIDEO_DIR=<dir>` (gfx_gpu.c frames, display.c audio) + `dev/psnova/make_video.py`
  (H.264 + AAC via the ffmpeg already on this PC).

## Game data (CPK archives)

`dev/psnova/cpk.py` (written by a Haiku agent, spot-checked: counts and the 1.05/rePatch comparison reproduced, a
message file extracted from both archives) lists and extracts CRI CPK archives, CRILAYLA included. Full inventory:
[dev/psnova/CPK-INVENTORY.md](../../dev/psnova/CPK-INVENTORY.md).

- All five archives are plain TOC archives with bare file names (no folders); base 87,268 files, 1.05 patch 8,133,
  rePatch patch 23,033 (20,056 of them `.rmd`).
- **Text is pre-rendered.** `msg_*.rmd` (magic ` DMR`) carry the string `FontConverterDll_1.0.1.3_rc6`: each message is
  text already drawn into glyph images by the developer's font converter, one file per message, indexed by
  `novamessagedictionary.mdic` (magic `BMVN`). The English rePatch changes 2,254 and adds 14,898 `.rmd` files, i.e. it
  redrew the messages. Consequence for Arabic (proven only as far as the magic and the string go): we can draw shaped,
  right-to-left Arabic ourselves into the same format, with no in-game font or shaping limits.
- RMD decode so far (Haiku agent, `dev/psnova/rmd/RMD-FORMAT.md`, `rmd.py info|atlas`; 13 Japanese/English pairs):
  header confirmed (message id at 0x90 = the file name's number; atlas size at 0x70/0x74, seen 128x32 to 256x128;
  data block = 0x1E0 bytes of tri-Ace chunks ` FIA`, ` FRa`, `ATIV` + width x height bytes). **Not decoded:** the atlas
  pixel layout (8-bit linear, Morton, tiles and 16-bit readings all unreadable: at 1 byte a pixel it may be DXT5/BC3 or
  the Vita's swizzle) and the glyph table. Next: read the texture format the renderer logs when the game draws a message,
  rather than guessing offline.
- Other formats: CRI ADX2 sound (`.acb` @UTF, `.awb` AFS2), Lua 5.1 bytecode scripts (`.lua`), CSV tables, tri-Ace
  formats with reversed four-letter tags (` FIA` .aif, ` FAA` .aai, ` FSA` .axs). The rePatch movie archive changes 9 of
  21 movies (MP00/MP06/MP09 and `Attention.mp4`).

## Status

| Area | State | Strength |
|---|---|---|
| Decrypt, import, analyze, recompile | done | single run |
| Build | `game_host.exe` 164 MB, 0 missing labels | proven (several builds) |
| Imports | 649: 245 runtime, 331 Sony's recompiled libraries, 73 stubs (below) | single run |
| First boot (headless, GPU) | 4 modules start, the game runs 30,821 system calls on 30 threads, then calls a missed ARM function (fixed, see above) | single run |
| Boot to title | **reached**: the title screen renders correctly (`docs/psnova/title-2026-11-18.png`), ~28 fps headless on the GPU | proven (many runs) |
| English (rePatch) | applied (`vitarecomp repatch`): "English patch [DEBUG BUILD]" on the title, the patch's own credit movie plays | proven (screenshots) |
| Movies (the firmware's AvPlayer + host H.264) | the three start-up movies decode and show (after the block alignment and decoder-size fixes); the opening movie's "garbled" lines are SEGA's own in-universe script (checked against Chrome's decode of the same file) | proven (screenshots) |
| Buttons | **work** after the SceCtrlData fix: Start skips the movie and opens the menu, Cross closes dialogs, Circle confirms (Japanese layout) | proven (scripted runs, screenshots) |
| Main menu, NEW GAME, story intro | reached: NEW GAME / CONTINUE / OPTION, the PSO2 bonus dialog, then the intro movie with the patch's English subtitles | proven (screenshots) |
| Windowed launch | `Play Phantasy Star Nova.bat` started through Explorer: window, 2x render scale, movies | single run (nobody has played it by hand) |
| Saves of other titles | "not found" (PSO2 bonus and demo import no longer offered: neither save exists here); this game's own slots listed by the slot search | single run |
| Character creation | all steps, skinned characters on the GPU (shader loops), the name typed through SceIme ("Nova" by default, `RECOMP_IME_TEXT`) | proven (screenshots) |
| Sound (NGS, ATRAC9) | **starts** since the NGS memory-size fix (CRI ADX2 refused > 0x1ff0): 11 NGS systems, the game's port carries the title music (rms 1,500-3,700); its mixer needed `vqmovn`/`vzip`/q `vshr.u64` in the recompiler (journal, sound section) | single run (levels, not by ear) |
| After "Start the Game" | **fixed** (2026-11-18 afternoon): the abort was a recompiler bug -- tail calls set lr (journal, abort section; recomp.py `tail()`). Now: the save, the warp cutscene, the ship corridor and Rietheia's dialogue | single run (screenshots) |
| Saves (savedata0 in `recomp/fs/`) | the character-creation save writes (569,108 bytes through the save dialog, slot 0); a copy in `dump/saves/after-creation-2026-11-18/` for runs that CONTINUE; loading not tried | single run |
| Dialogue box, HUD, Filldia, Nova's armour | **fixed** (2026-11-18 evening): the renderer downloaded character creation's stale RGBA targets over textures the game later copied into the same memory; downloads now keep the pages the game rewrote (gfx_gpu.c `kept_pages_find`, journal "Noisy textures") | two runs (screenshots), reviewed by two agents |
| NOW LOADING screen (and the UI file the rePatch dropped) | **fixed**: the English rePatch's patch archive lacks `tex_nova_ui_common.aif`; `REPATCH_KEEP` (pack.toml) makes import merge it in (`pipeline/cri/`, `dump/decrypted/PCSG00351/repatch_merged/`) | three runs |
| Line primitives | `prim LINES` draws are skipped by both renderers (4,014 from frame 15,565 into a U8 target); no visible effect found yet | open |
| Arabic text (every-project standard) | not started | n/a |
| Keyboard keys in button prompts (every-project standard) | not started | n/a |
| Real-game reference pictures | none yet: needed before any visual change | n/a |

## Real-game reference (from the user, 2026-11-18)

`C:\New PATH\screenshots`: two YouTube walkthroughs of the real Vita game, one frame a second at 1920x1080 --
part 1 "Character Creator + intro" (1,419 frames, 0:05-23:43), part 2 "mission 1" (1,117 frames, 0:05-18:41).
Contact sheets (16 s each, timestamped) in `dump/reference/part1|part2/` (git-ignored: someone else's video), made by
`dev/psnova/make_ref_sheets.py`; the index (Haiku agents, spot-checked) in [reference-index.md](reference-index.md).
Use it before any visual change and to script runs past character creation.

## Stubbed imports that matter (return 0 today)

From `RECOMP_IMPORTS=1` (dev/psn-logs/imports-run.log). Network, ad hoc, NP, trophies and screenshots are expected
stubs (offline play; the runtime returns "not initialised" for the network families).

| Import | Why it matters |
|---|---|
| `sceNgsVoiceDefGetAtrac9Voice`, `...MixerBuss`, `...Template1`, `...EqBuss`, `...DelayBuss`, `...DistortionBuss`, `...PitchShiftBuss` | NGS voice definitions: with a null definition the game's sound racks can't be made (Uncharted and Killzone only used the master/reverb/compressor ones) |
| `sceAppUtilSaveDataSlotSearch`, `sceAppUtilSaveDataMount`, `...Umount` | loading saves |
| `sceImeDialogInit/GetStatus/GetResult/Term`, `sceImeOpen/Update/Close` | text entry (likely naming the character) |
| `sceKernelCancelEventFlag`, `sceAudioOutReleasePort` | small kernel/audio calls |
| `sceJpegCsc`, `sceJpegMJpegCsc`, `sceJpegGetOutputInfo` | JPEG decoding (use not known yet) |
| `sceKernelLoadStartModule`, `sceSysmoduleLoadModule` | answered 0 (success); the modules it loads (libsmart, libface...) are not imported by the main program |

## Controls (Project Nativ's defaults)

D-pad: arrow keys · Cross/Circle/Square/Triangle: Space/C/F/E · Start/Select: Enter/Tab · L/R: right/left mouse
button (or Q and R) · sticks: WASD and mouse · front touch: Alt+click · F10 menu, F1 frame rate, F5 bug mark.
A Japanese release usually confirms with **Circle (C)** and cancels with **Cross (Space)**: to be checked in the game.

## The button problem (investigation, 2026-11-18)

- Two controller reads exist in the whole program (generated C, call sites of the import stubs):
  `fn_815920de` (sceCtrlReadBufferPositive2 port 0, every frame, main game loop) keeps only L, R, L3, R3 (the PS TV
  extra buttons games use in place of touch); `fn_81b1c958` (sceCtrlPeekBufferPositive) is the real pad device's read.
- The real read's chain (RECOMP_CTRL_BACKTRACE): Aska worker `fn_81a23802` -> job `fn_81a1f276` -> `fn_81b1cd18` ->
  `fn_81b1c958`. The job loops "while not quit: update the 3 device slots (+0x18, vtable +0x24); sleep 8 ms"; the pad
  update locks (spin, then 1 ms sleeps), peeks, and processes buttons only when the sample's timestamp changed.
- It peeked once (frame 0) and never again, while the loop kept spinning. The trace hooks showed why: from the second
  pass the loop's object pointer (r5, callee-saved) was 0, so it read empty slots at 0/4/8 forever. **Cause:** the
  runtime wrote each `SceCtrlData` as 64 bytes; it is 0x20. The pad update keeps its sample at `sp+0` under its canary
  at `sp+0x24` and the saved r4-r8 from `sp+0x2c`: the extra 32 bytes zeroed them, and the canary check passed because
  `__stack_chk_guard` is left 0. **Fixed** (display.c): the pad update ran 218,000 times in the next run and the
  buttons work.
- Not the cause (checked): the save-slot stubs (that call only counts saves, and 0 is right for a fresh test),
  sound (not started before the title), the app state (all zeros: nothing overlaid), skipped movies.

## Open questions and next steps

1. A hand play test by the user (windowed): the first mission, loading the save, sound by ear. Names are typed by
   SceIme with a fixed answer ("Nova", `RECOMP_IME_TEXT`); a real typing box is the fork's 340a30f (below).
1a. Line primitives (`prim LINES`) are skipped by both renderers; find what the game draws with them (from frame
   15,565, into a U8 target) before deciding whether they matter.
1b. The arena script: the left stick works, but the scripted route (`dev/psn-logs/sticks-37.txt`: left, then forward)
   doesn't reach the arrows; the real player goes round the left side of the crate field (reference 14:32-14:44).
2. Make `sceAppUtilSaveDataMount` answer "not found" for another title's save (no free PSO2 bonus) unless the user
   wants the bonus.
3. The two shaders the translator refused: find which draws use them.
4. Arabic: finish the RMD decode (read the atlas texture format from the renderer when a message is drawn), then draw
   Arabic messages with our own shaping into new RMD files. Keyboard-key prompts: the button icons are in the same
   pre-rendered messages and the UI atlases (to survey).
5. Bring the SceCtrlData fix to the Uncharted copies (their stacks may be quietly damaged the same way); the user decides.
6. Commit the branch when the user asks.
7. Leads from the Uncharted session's comparison with the Luufen Nativ fork (read-only clone at `recent recomps\Nativ
   Luufen fork`; `Uncharted Golden Abyss Recomp RT\docs\fork-benefit-check.md`, Nova section): taken -- dfc075d (NEON
   post-increment). Not yet, test one at a time: 1deb30f GPU views for any U8U8U8U8 order (~5 target downloads a frame,
   ~12 ms of 51 ms; confirm with `RECOMP_GPU_TRACE_SYNC=1`), 340a30f/ad8dd3d IME text card, SOP2 blend ops on the GPU,
   74e8f78/33c4b5b/3854bf2 NGS (start buffer at +81), 756959a hooks-scan (60 fps / widescreen sites), 9d2bdb6 gap
   report. Do NOT take 47e54dc (L1/R1 bits) without tracing Nova's bit tests first.
