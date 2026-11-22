#!/bin/bash
# import -> analyze -> recompile -> build for PCSG00351, each stage logged (dev/psn-logs/<stage>.log)
cd "$(dirname "$0")/.."
# the project's own Python and toolchain, inside this folder (2026-11-19: separated from the Uncharted checkout; tools/python +
# .venv made from it, toolchain/ = a copy; docs/psnova/separation-from-uncharted.md)
PY="${PY:-$PWD/.venv/Scripts/python.exe}"
export ATIV_WIN_TOOLCHAIN="${ATIV_WIN_TOOLCHAIN:-$PWD/toolchain}"
for s in ${STAGES:-import analyze recompile build}; do
  t0=$(date +%s)
  "$PY" pipeline/vitarecomp.py $s PCSG00351 > dev/psn-logs/$s.log 2>&1; rc=$?
  echo "$s rc=$rc $(( $(date +%s) - t0 ))s"
  if [ $rc -ne 0 ]; then tail -20 dev/psn-logs/$s.log; exit $rc; fi
  # before a 25-minute build, the generated C's gotos all have their labels (dev/psnova/check_labels.py)
  if [ "$s" = recompile ]; then
    "$PY" -I dev/psnova/check_labels.py dump/decrypted/PCSG00351/recomp game > dev/psn-logs/check_labels.log 2>&1 || { tail -20 dev/psn-logs/check_labels.log; exit 3; }
    tail -1 dev/psn-logs/check_labels.log
  fi
done
exit 0
