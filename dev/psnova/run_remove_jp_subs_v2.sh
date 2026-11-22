#!/bin/bash
# Clean the Japanese burned-in subtitles from the 8 ORIGINAL story movies (v2). Written 2026-11-18 evening.
# Inputs: dump/psnova-l10n/movies_jp (extracted from the game's NOVA_FileList_Vita_movie.cpk), movies (fan-patched copies, timing support).
# Outputs: dump/psnova-l10n/movies_clean_jp/*.mp4, per-movie logs run2_<name>.log, counts c2_<name>.npz.  4 at a time.
cd "$(dirname "$0")/../.." || exit 1
D=dump/psnova-l10n
mkdir -p $D/movies_clean_jp
run() {  # name y0 y1 thr
  python dev/psnova/remove_jp_subs_v2.py $D/movies_jp/$1.mp4 $D/movies_clean_jp/$1.mp4 --y0 $2 --y1 $3 --thr $4 \
    --ref $D/movies/$1.mp4 --counts $D/c2_$1.npz > $D/run2_$1.log 2>&1
}
export -f run; export D
printf '%s\n' "MP09_040_040 464 491 700" "MP00_000_000 470 497 350" "MP00_010_050 470 496 350" "MP09_040_070 470 497 350" \
  "MP06_030_070 470 497 350" "MP00_000_010 472 499 350" "MP06_030_050 470 497 350" "MP06_030_040 470 497 350" \
  | xargs -P 4 -L 1 bash -c 'run $0 $1 $2 $3'
echo ALL-DONE > $D/run2_done.txt
