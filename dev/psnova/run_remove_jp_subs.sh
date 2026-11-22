#!/bin/bash
# Clean the Japanese subtitle line out of the 8 patched story movies (2026-11-18). 4 at a time.
# subtitle presence = the English line is there (persistent white-on-black pixels >= 20) and the Japanese band has strokes (see remove_jp_subs.py)
# in: dump/psnova-l10n/movies/*.mp4 (extracted from the repatched movie archive)  out: dump/psnova-l10n/movies_clean/
cd "$(dirname "$0")/../.." || exit 1
mkdir -p dump/psnova-l10n/movies_clean
cat <<'L' | xargs -P 4 -L 1 bash -c 'python dev/psnova/remove_jp_subs.py dump/psnova-l10n/movies/$0.mp4 dump/psnova-l10n/movies_clean/$0.mp4 --y0 $1 --y1 $2 --enthr 20 > dump/psnova-l10n/run_clean_$0.log 2>&1'
MP09_040_040 464 491
MP00_000_000 470 497
MP00_010_050 470 496
MP09_040_070 470 497
MP06_030_070 470 497
MP00_000_010 472 499
MP06_030_050 470 497
MP06_030_040 470 497
L
cat dump/psnova-l10n/run_clean_*.log > dump/psnova-l10n/run_clean.log; echo ALL-DONE >> dump/psnova-l10n/run_clean.log
