# Nova 2× English text pilot, 2026-11-22

Done by Codex.

`build_l10n.py` accepts `--english-atlas-scale 2` for English. It rasterizes complete font runs at double the selected FreeType size and fits them into the original logical geometry. The RMD writer scales the texture payload and its GXM size fields. The RMD header's dimensions at `0x70/0x74` remain at 1× because Nova uses them in its glyph layout. Text codes, glyph advances, texture IDs, box coordinates, and normalized glyph UVs are preserved. The decoder uses the GXM dimensions for the physical bitmap and exposes them separately from the logical size. Captions retain 21-pixel logical cells with 42-pixel physical bitmaps. Original bitmap glyphs in an English atlas retain their source shapes. The default build remains 1×.

For an incremental pilot, use `--layout-base` with an existing English archive and `--only` with the JSON list of message IDs. The pilot requires the default encode to match the base entry before replacement. That catches a stale sheet, font configuration, or previously modified entry.

```powershell
$stage = 'C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot'
$base = 'dump/decrypted/PCSG00351/lang/en/NOVA_FileList_Vita_patch.cpk'
$sheet = 'dump/psnova-l10n/sheet/psnova_text_v7.tsv'
& ./.venv/Scripts/python.exe -s -B dev/psnova/rmdtext/build_l10n.py $sheet en "$stage/test-build" --layout-base $base --only "$stage/ids.json" --english-atlas-scale 2
& ./.venv/Scripts/python.exe -s -B "$stage/verify.py"
```

| ID | Where it appears | Original | Pilot |
| --- | --- | --- | --- |
| 21402 | New Game | 128 × 32 | 256 × 64 |
| 240197 | Storage facility label | 128 × 32 | 256 × 64 |
| 261211 | Kisara's Kuklonahda transmission | 256 × 128 | 512 × 256 |
| 500005 | Enter Character Name | 128 × 64 | 256 × 128 |
| 101010010011001 | Opening Lutina caption | 128 × 128 | 256 × 256 |
| 101010020140051 | Advanced Personnel survey team dialogue | 256 × 128 | 512 × 256 |

Title and Storage were added to the selection so the pilot can check the loader early and sample a visible message during outdoor base gameplay. The verifier compared all 27,819 CPK entries and observed exactly these six replacements. Each selected message matched the installed copy byte for byte at the default scale. The selected replacements preserve tokens and glyph records and double both atlas dimensions. The staged archive is 805,265,896 bytes, 294,912 bytes larger than the installed baseline. [Verification script](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/verify.py>)

The production-generated Kisara atlas was substituted into the same 3840 × 2176 GPU replay as the initial prototype. The changed pixels were confined to the two lines of text. [Kisara comparison](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/kisara-builder-comparison.png>)

A size estimate using the active archive's existing atlas dimensions gives approximately 613 MB of additional BC2 data for classified dialogue, radio and captions, or 1.30 GB for all eligible translated files with local glyphs. The estimate excludes build staging and does not guarantee a complete rebuild will have the exact same sizes. Stage large builds on a separate volume.

## Live test status

The test filesystem is a private copy on `C:`. The first boot attempt skipped the app0 copies of the movie and patch archives and stayed black. Copying both files restored the baseline boot. The live test harness uses the existing installed executable and switches archives only in its private filesystem. [Live test harness](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/run.py>)

The first atlas variant doubled the RMD layout dimensions and the GXM dimensions. In-game this compressed and garbled `Enter Character Name`, even though the replay and the static RMD validation passed. Restoring the original values at `0x70/0x74` fixed the label. The final builder produces the same corrected archive as the live probe. At frame 12000, the guest capture contained the exact corrected BC2 payload and a 256 × 128 draw binding at `0x1d976040`. The corrected PC label retained its on-screen width and appeared sharper in the 3840 × 2176 render. [Failed live variant](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/character-name-1x.png>) · [Corrected live comparison](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/character-name-live.png>)

## Live frame-time comparison

Both builds loaded English slot 1 at the outdoor Delta Valiant Exploration Base. The test used the same scripted controller camera rotation, 4× render scale, 60 FPS target and real game clock. Three 60-second windows per archive began at frame 3600. The first run of each archive captured frame 3500 during warm-up. Screenshot capture was inactive in every timed window. After fixing the logical dimensions, Codex ran three new pilot samples and compared them with the original baseline.

| Measure | Baseline | Pilot |
| --- | --- | --- |
| Game frame-time p95 by run | 18.9, 18.9, 18.7 ms | 17.5, 17.5, 17.4 ms |
| Median p95 | 18.9 ms | 17.5 ms |
| Lowest reported FPS while the game clock was running | 58.5 | 59.9 |
| Active windows below 10 FPS | 0 | 0 |
| Median of per-run GPU busy medians | 4.9 ms/frame | 4.8 ms/frame |
| Peak reported presents in flight | 0 | 0 |
| Median of per-run render callback blocked time medians | 13.97 ms/frame | 14.45 ms/frame |

Baseline run 1 included five one-second windows with a stopped game clock and zero game FPS. These remain in the logs and are counted separately from active-game FPS. The frame-time threshold passed for the sampled outdoor base route. The warm-up Storage label was pixel-identical with either archive. The benchmark covers outdoor base gameplay and leaves the cost of scenes actively displaying upgraded radio and caption text unmeasured. [Benchmark harness](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/timing.py>) · [Baseline and initial pilot summaries](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/timings.json>) · [Corrected pilot summaries](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/timings-corrected.json>)

## Coverage and deployment

The fresh-save route verified character registration and reached the first corridor dialogue with the corrected archive. The selected Lutina caption is in `MP01_010_010` after the initial tutorial quests. That caption and the Advanced Personnel scene passed the archive and layout checks. Their exact screen output still needs a live route. Kisara's message passed the matched GPU replay check. [Opening route log](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/opening-corrected-confirm/session.log>)

The existing English layout verifier passed all 9,577 classified messages. The corrected pilot SHA-256 is `718e38fc64f9fc692c6803d7252919db5d41da46185fafe1c03b3dd11823c79b`.

The optional archive remains staged on `C:`. The active launcher, English archive, installed executable, and player saves retain their original contents. The default 1× build remains supported. [Corrected pilot archive](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/test-build/overlay/NOVA_FileList_Vita_patch.cpk>)
