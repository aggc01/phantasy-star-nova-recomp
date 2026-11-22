@echo off
:: Starts Phantasy Star Nova (PCSG00351, Japanese 1.05 with this project's English/Arabic overlays), built from your own
:: copy in dump\. Language: F10 menu (or "language" in dump\decrypted\PCSG00351\recomp\settings.ini).
:: Controls: Enter = Start, C = Circle (confirm), Space = Cross (cancel), arrows = D-pad, WASD + mouse = sticks,
:: F10 = in-game menu, Alt+F4 = quit. Saves: dump\decrypted\PCSG00351\recomp\fs\savedata0. Log: ...\recomp\session.log
cd /d "%~dp0"
:: This folder's own Python (2026-11-19: separated from the Uncharted checkout, docs\psnova\separation-from-uncharted.md):
:: .venv first; tools\python itself if the .venv is missing or was made at another path (a venv records its base by
:: absolute path, so moving the folder breaks it). python.exe in a minimized console, not pythonw: the pipeline writes the
:: game's log to its console.
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY="
if defined PY "%PY%" -s -c "" 2>nul || set "PY="
if not defined PY set "PY=%~dp0tools\python\python.exe"
if not exist "%PY%" (
  echo Python not found: neither "%~dp0.venv\Scripts\python.exe" nor "%~dp0tools\python\python.exe" runs.
  pause
  exit /b 1
)
start "Phantasy Star Nova" /min "%PY%" -s "pipeline\vitarecomp.py" run PCSG00351
