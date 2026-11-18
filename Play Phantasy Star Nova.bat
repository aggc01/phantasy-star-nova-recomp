@echo off
:: Starts Phantasy Star Nova (PCSG00351, 1.05, with the English rePatch), built from your own copy in dump\.
:: Controls: Enter = Start, C = Circle (confirm), Space = Cross (cancel), arrows = D-pad, WASD + mouse = sticks,
:: F10 = in-game menu, Alt+F4 = quit. Saves: dump\decrypted\PCSG00351\recomp\fs\savedata0. Log: ...\recomp\session.log
cd /d "%~dp0"
:: The pipeline's Python is the Uncharted checkout's (this folder is a git worktree of it); python.exe in a minimized
:: console, not pythonw: the pipeline writes the game's log to its console.
set "PY=%~dp0..\recent recomps\Uncharted Golden Abyss Recomp\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Python not found at "%PY%"
  pause
  exit /b 1
)
start "Phantasy Star Nova" /min "%PY%" "pipeline\vitarecomp.py" run PCSG00351
