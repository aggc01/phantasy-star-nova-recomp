# Maintainer tool: remove files the player's setup never uses from a freshly assembled release folder.
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File engine\release\prune_release.ps1
# It only deletes inside engine\python and engine\toolchain\llvm-mingw, and prints what it removed.
# Run it before the final clean-folder test: setup must pass with exactly what ships.
$ErrorActionPreference = "Stop"
$engine = Split-Path -Parent $PSScriptRoot
$python = Join-Path $engine "python"
$mingw = Join-Path $engine "toolchain\llvm-mingw"
foreach ($required in @("$python\python.exe", "$mingw\bin\x86_64-w64-mingw32-clang.exe")) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Not a release engine folder, missing: $required" }
}

$targets = @(
    # CPython: documentation, the standard library's own test suite, IDLE, demos, pip and build-only files.
    "$python\Doc", "$python\include", "$python\libs", "$python\Scripts", "$python\NEWS.txt",
    "$python\Lib\test", "$python\Lib\idlelib", "$python\Lib\turtledemo", "$python\Lib\ensurepip",
    "$python\Lib\site-packages\pip", "$python\Lib\site-packages\pyflakes"
)
$targets += Get-ChildItem -LiteralPath "$python\DLLs" -Filter "_test*.pyd" | ForEach-Object FullName
$targets += Get-ChildItem -LiteralPath "$python\DLLs" -Filter "_ctypes_test.pyd" | ForEach-Object FullName
$targets += Get-ChildItem -LiteralPath "$python\Lib\site-packages" -Directory -Filter "pip-*.dist-info" | ForEach-Object FullName
$targets += Get-ChildItem -LiteralPath "$python\Lib\site-packages" -Directory -Filter "pyflakes-*.dist-info" | ForEach-Object FullName
# LLVM-MinGW: setup only builds for x86_64 Windows. Other target sysroots and the debugger's Python are never read.
foreach ($arch in "aarch64-w64-mingw32", "armv7-w64-mingw32", "i686-w64-mingw32", "python") { $targets += "$mingw\$arch" }
# ...and the debugger, language server and linter, none of which the build invokes.
foreach ($pattern in "lldb*.exe", "liblldb.dll", "libpython3*.dll", "clangd.exe", "clang-tidy.exe", "run-clang-tidy", "analyze-build", "intercept-build") {
    $targets += Get-ChildItem -LiteralPath "$mingw\bin" -Filter $pattern -File | ForEach-Object FullName
}
# Bytecode caches are rebuilt on demand and are never needed in the download.
$targets += Get-ChildItem -LiteralPath $engine -Recurse -Directory -Filter "__pycache__" -Force | ForEach-Object FullName

$freed = 0
foreach ($path in $targets | Sort-Object -Unique) {
    if (-not (Test-Path -LiteralPath $path)) { continue }
    $item = Get-Item -LiteralPath $path -Force
    $bytes = if ($item.PSIsContainer) {
        (Get-ChildItem -LiteralPath $path -Recurse -File -Force | Measure-Object Length -Sum).Sum
    } else { $item.Length }
    Remove-Item -LiteralPath $path -Recurse -Force
    $freed += $bytes
    "removed {0,8:N1} MB  {1}" -f ($bytes / 1MB), $path.Substring($engine.Length + 1)
}
"Freed {0:N1} MB" -f ($freed / 1MB)
