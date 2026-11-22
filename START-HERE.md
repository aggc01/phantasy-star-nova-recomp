# Phantasy Star Nova recomp: start here

This folder is its own git repository (branch `psnova`; since 2026-11-19, before that a worktree of the Project Nativ
checkout in `..\recent recomps\Uncharted Golden Abyss Recomp`: [separation-from-uncharted.md](docs/psnova/separation-from-uncharted.md)).
It turns the PS Vita game **Phantasy Star Nova** (PCSG00351, Japan, update 1.05) into a native Windows program, with this
project's own English and Arabic overlays on the Japanese game.

- **The one state file:** [docs/psnova/README.md](docs/psnova/README.md): what works, what is open, how to build, run
  and test, and every claim's strength (proven / single run / untested). Update it in place; don't start new status files.
- **Play:** `Play Phantasy Star Nova.bat`. **Build:** `bash dev/psn_build_all.sh`.
- **Project Nativ's own guides** (how the recompiler and runtime work): [README.md](README.md),
  [docs/developers.md](docs/developers.md), [docs/debugging.md](docs/debugging.md).
- **Lessons from the earlier recomps**, applied here from day one: `..\recomp_study\RETROSPECTIVE.md` and
  `..\recomp_study\RECOMP_PLAYBOOK.md`.

Rules for this copy:

- Everything it needs is inside this folder: its own library (`dump/`), branch, builds, Python (`tools\python` +
  `.venv`) and toolchain (`toolchain\`). Nothing is read from or written to the Uncharted copies.
- The player's game files in `F:\RECOMP GAMES\Phantasy Star Nova (v1.05)` are read only.
- Saves live in `dump/decrypted/PCSG00351/recomp/fs/`; back them up fresh before any test run that could write them
  (the F10 menu's Saves page keeps copies: [save-backups.md](docs/psnova/save-backups.md)).
- The repository stores LF line endings (`core.autocrlf false`); write files with `newline='\n'`. The `.bat` files are CRLF.
