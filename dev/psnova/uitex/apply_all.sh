#!/usr/bin/env bash
# apply_all.sh [lang...] - redraw every UI texture spec (dump/psnova-l10n/uitex/specs/*.json) for English and Arabic
# into dump/psnova-l10n/uitex/out/<lang>/ (<texture>.aif + preview/), then build one contact sheet per language
# (make_sheets.py -> dump/psnova-l10n/uitex/out/sheet_<lang>.png). Default languages: en ar.
# Specs whose file name starts with "_" (drafts, tests) are skipped unless UITEX_ALL=1. Exit code 1 if any spec failed its check.
# Then: build_l10n.py --extra-dir dump/psnova-l10n/uitex/out/<lang> puts the textures into that language's archive.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
PY="$ROOT/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$ROOT/.venv/bin/python"
SPECS="$ROOT/dump/psnova-l10n/uitex/specs"
OUT="$ROOT/dump/psnova-l10n/uitex/out"
LANGS=("$@"); [ ${#LANGS[@]} -eq 0 ] && LANGS=(en ar)

shopt -s nullglob
specs=()
for s in "$SPECS"/*.json; do
  if [ "${UITEX_ALL:-0}" != 1 ]; then
    case "$(basename "$s")" in _*) echo "skip $(basename "$s") (draft/test; UITEX_ALL=1 includes it)"; continue;; esac
  fi
  specs+=("$s")
done
[ ${#specs[@]} -eq 0 ] && { echo "no specs in $SPECS"; exit 0; }

fail=0
for lang in "${LANGS[@]}"; do
  mkdir -p "$OUT/$lang/preview"
  for s in "${specs[@]}"; do
    if ! "$PY" -s "$HERE/apply_spec.py" "$s" "$lang" "$OUT/$lang"; then
      echo "FAILED: $(basename "$s") [$lang]"; fail=1
    fi
  done
done
"$PY" -s "$HERE/make_sheets.py" "${LANGS[@]}"
[ $fail -eq 0 ] && echo "all specs OK (${#specs[@]} specs x ${#LANGS[@]} languages)" || echo "SOME SPECS FAILED"
exit $fail
