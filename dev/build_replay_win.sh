#!/bin/bash
# gfxreplay on Windows (runtime/debug/build_replay.sh is zsh and POSIX-only): the same sources, built with the
# toolchain runtime/build.py uses for Windows (<root>/toolchain: llvm-mingw, SDL3, zlib), with its flags.
#   bash dev/build_replay_win.sh [out]   (default build/gfxreplay.exe, SDL3.dll copied beside it)
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd); RT=$ROOT/runtime; G=$RT/gfx; D=$RT/debug; C=$RT/core
WT=${ATIV_WIN_TOOLCHAIN:-$ROOT/toolchain}; SDLW=$WT/SDL3/x86_64-w64-mingw32
OUT=${1:-$ROOT/build/gfxreplay.exe}; mkdir -p "$(dirname "$OUT")"
SRCS=("$D/gfxreplay.c" "$RT/platform/platform_win32.c" "$RT/platform/win32_compat.c" "$G/gfx_dispatch.c" "$G/gfx_soft.c"
  "$G/gfx_gpu.c" "$G/gpulock.c" "$D/gfx_coverage.c" "$D/gfx_capture.c" "$D/waitstats.c" "$G/guestwatch.c" "$C/metrics.c"
  "$C/settings.c" "$G/usse.c" "$G/usse_spirv.c" "$C/psarc.c" "$G/gxp_index.c" "$G/ssao.c" "$G/fsr/fsr.c")
INC=(); for d in core gfx audio media input net ui platform debug; do INC+=(-I "$RT/$d"); done; INC+=(-I "$ROOT/recompiler" -I "$ROOT")
"$WT/llvm-mingw/bin/x86_64-w64-mingw32-clang.exe" -O2 -ffp-contract=off -Wall -D_FILE_OFFSET_BITS=64 -D_POSIX_THREAD_SAFE_FUNCTIONS \
  -include "$RT/platform/win32_compat.h" -include "$ROOT/dev/replay_win_shim.h" -I "$WT/zlib/include" -I "$SDLW/include" "${INC[@]}" "${SRCS[@]}" \
  -L "$SDLW/lib" -lSDL3 -L "$WT/zlib/lib" -lz -lpthread -lwinmm -lws2_32 -o "$OUT"
cp -f "$SDLW/bin/SDL3.dll" "$(dirname "$OUT")/"
echo "built $OUT"
