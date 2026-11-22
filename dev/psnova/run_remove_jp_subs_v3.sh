#!/bin/bash
# Clean the Japanese burned-in subtitles from the 8 ORIGINAL story movies with v3 (per-line masks). Written 2026-11-19.
# ONE movie at a time; remove_jp_subs_v3.py and check_sub_residue.py put themselves at IDLE priority (ffmpeg inherits it).
# Inputs: dump/psnova-l10n/movies_jp (originals), movies (fan-patched copies, English-line timing).
# Outputs: dump/psnova-l10n/movies_clean_jp_v3/*.mp4, logs run3_<name>.log, line tables movies_v3_check/lines_<name>.npz,
#          residue reports movies_v3_check/residue_<name>.json/.log and picture strips movies_v3_check/*.png
#          (v2 = movies_clean_jp vs v3).  Same bands and thresholds as run_remove_jp_subs_v2.sh.
cd "$(dirname "$0")/../.." || exit 1
D=dump/psnova-l10n
mkdir -p $D/movies_clean_jp_v3 $D/movies_v3_check
while read -r name y0 y1 thr; do
  python dev/psnova/remove_jp_subs_v3.py $D/movies_jp/$name.mp4 $D/movies_clean_jp_v3/$name.mp4 --y0 $y0 --y1 $y1 \
    --thr $thr --ref $D/movies/$name.mp4 --lines $D/movies_v3_check/lines_$name.npz > $D/run3_$name.log 2>&1 \
    || echo "FAILED $name" >> $D/run3_failed.txt
  python dev/psnova/check_sub_residue.py $name --clean $D/movies_clean_jp --clean $D/movies_clean_jp_v3 \
    --strips $D/movies_v3_check --json $D/movies_v3_check/residue_$name.json > $D/movies_v3_check/residue_$name.log 2>&1
done <<'EOF'
MP09_040_040 464 491 700
MP00_000_000 470 497 350
MP00_010_050 470 496 350
MP09_040_070 470 497 350
MP06_030_070 470 497 350
MP00_000_010 472 499 350
MP06_030_050 470 497 350
MP06_030_040 470 497 350
EOF
echo ALL-DONE > $D/run3_done.txt
