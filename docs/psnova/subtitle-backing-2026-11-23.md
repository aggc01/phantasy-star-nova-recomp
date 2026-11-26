# The Enigmatic Girl I subtitle backing, 2026-11-23

The Theater Scope scene uses `MP00_000_010.mp4`. The English “And then...” cue is line 8. The original subtitle detector found a band from x=422 to x=653, while the English text was centered on the 960-pixel frame. The renderer used the mask's position as well as its width, so it centered the backing around x=538.

The movie subtitle renderer now takes its backing width from the translated text and the detected mask width and centers the backing on the caption. On movie frame 1221 the measured backing center moved from x=538 to x=480. The source and new versions have the same 960 × 544 format and 1,551 frames. All ten cues were retained with their original timing. The AAC packet payload hash matches the original. [Matched frame comparison](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-subtitle-backing/subtitle-comparison.png>)

The replacement CPK was built against the installed English movie archive. Its 21 entries all passed the read-back check. The only changed entry is `MP00_000_010.mp4`. The original movie archive is preserved in the [isolated fixture](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/baseline/fs/lang/en/NOVA_FileList_Vita_movie.cpk>), SHA-256 `7d2e72bcb9af3bcb64372407fbb5276913ef83b41d1715443afc889694ffc84b`.

To reproduce from the repository root, use the existing subtitle burn command for `MP00_000_010` with `--lang en --y0 472 --y1 499 --normal`. Use `cpk_replace.py` with the active English movie archive as the base and `--replace MP00_000_010.mp4=<the rebuilt video>`.

The isolated game smoke test opened the staged archive and reached character creation. The scripted route stopped there. The cue position was verified directly on matched decoded movie frames. [Game log](<C:/Users/<user>/.codex/visualizations/2026/11/18/01a1ef68-356c-71b2-8aaf-9ee9791a4f22/nova-text-pilot/subtitle-backing-verified/session.log>)

With the game closed, I installed the verified CPK into the English language overlay and checked the SHA-256 through the launcher’s filesystem path. The installed archive is 430,514,816 bytes with SHA-256 `eced2b023ef94af964e1e6f6dba5ce15ff884c190f5a1f35375e6f7f20671e64`.
