#!/bin/bash
# Burn English and Arabic subtitles into the 8 cleaned story movies and build one movie archive per language
# (2026-11-19). Input: dump/psnova-l10n/subs/<movie>.json (transcribed + translated lines), the v3 cleaned movies and their
# line tables; the warning screen Attention_<lang>.mp4. Output: dump/psnova-l10n/movies_sub_<lang>/<movie>.mp4 and
# dump/psnova-l10n/movie_cpk_<lang>/NOVA_FileList_Vita_movie.cpk (Sony's archive with those 9 entries replaced).
# Install: copy each archive into dump/decrypted/PCSG00351/lang/<lang>/ (the runtime's language overlay).
cd "$(dirname "$0")/../.." || exit 1
PY=.venv/Scripts/python.exe
D=dump/psnova-l10n
BASE=dump/decrypted/PCSG00351/app0_patched/NOVA_FileList_Vita_movie.cpk
for lang in ${LANGS:-en ar}; do
  mkdir -p $D/movies_sub_$lang $D/movie_cpk_$lang $D/subs/preview_$lang
  R="--replace Attention.mp4=$D/movies_l10n/Attention_$lang.mp4"
  while read -r name y0 y1; do
    $PY -s dev/psnova/burn_subs.py $D/movies_clean_jp_v3/$name.mp4 $D/subs/$name.json $D/movies_v3_check/lines_$name.npz \
      $D/movies_sub_$lang/$name.mp4 --lang $lang --y0 $y0 --y1 $y1 --preview $D/subs/preview_$lang/$name \
      || echo "FAILED $lang $name" >> $D/subs/burn_failed.txt
    R="$R --replace $name.mp4=$D/movies_sub_$lang/$name.mp4"
  done <<'EOF'
MP00_000_000 470 497
MP00_000_010 472 499
MP00_010_050 470 496
MP06_030_040 470 497
MP06_030_050 470 497
MP06_030_070 470 497
MP09_040_040 464 491
MP09_040_070 470 497
EOF
  # The English archive also includes the opening announcement.
  if [ "$lang" = en ]; then
    opening_source="$D/movie_cpk_en/source"
    $PY -s -B pipeline/cri/cpk.py extract "$BASE" "$opening_source" --match OpeningDemo.mp4 || exit 1
    $PY -s -B dev/psnova/burn_subs.py "$opening_source/OpeningDemo.mp4" dev/psnova/subs/OpeningDemo.json \
      "$D/movies_sub_en/OpeningDemo.mp4" --lang en --y0 488 --y1 504 \
      --preview "$D/subs/preview_en/OpeningDemo" || exit 1
    R="$R --replace OpeningDemo.mp4=$D/movies_sub_en/OpeningDemo.mp4"
  fi
  $PY -s -I dev/psnova/cpk_replace.py "$BASE" "$D/movie_cpk_$lang/NOVA_FileList_Vita_movie.cpk" $R || exit 1
done
echo BURN-DONE
