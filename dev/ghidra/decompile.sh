#!/bin/bash
# Decompile functions of an already-analysed game into docs/lighting-c (or $OUT): decompile.sh <hex addr>...
# Uses the project's own Java and Ghidra (tools/jdk21, tools/ghidra_*), the Ghidra project in tools/ghidra-project.
R=$(cd "$(dirname "$0")/../.." && pwd)
export JAVA_HOME="$R/tools/jdk21" PATH="$R/tools/jdk21/bin:$PATH"
G=$(ls -d "$R"/tools/ghidra_*_PUBLIC | head -1)
"$G/support/analyzeHeadless" "$R/tools/ghidra-project" Uncharted -process uncharted.elf -noanalysis -readOnly \
  -scriptPath "$R/dev/ghidra" -postScript NativDecompile.java "${OUT:-$R/docs/lighting-c}" "$@" 2>&1 | grep -E "decompiled|no function|ERROR"
