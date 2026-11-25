# Phantasy Star Nova Recomp: start here

This repository turns the PS Vita game **Phantasy Star Nova** (PCSG00351, Japan, update 1.05) into a native Windows
program. It is a fork of [Project Nativ](https://github.com/TheLostPantheon/nativ).

- **Set up, build and play:** [README.md](README.md).
- **The state of the recomp:** [docs/psnova/README.md](docs/psnova/README.md): what works, what is open, how to build,
  run and test, and how strongly each claim is proven (proven / single run / untested). Update it in place rather than
  starting new status files.
- **Play:** `Play Phantasy Star Nova.bat`. **Rebuild:** `bash dev/psn_build_all.sh`.
- **How the recompiler and runtime work:** [docs/architecture.md](docs/architecture.md),
  [docs/developers.md](docs/developers.md), [docs/debugging.md](docs/debugging.md).

Working rules:

- Everything a build needs stays inside this folder: the game library (`dump/`), builds, Python (`.venv`) and
  toolchain (`toolchain/`). All four are git-ignored.
- Treat your own game files as read only. The pipeline copies what it needs into `dump/`.
- Saves live in `dump/decrypted/PCSG00351/recomp/fs/`. Back them up before any test run that could write them; the
  F10 menu's Saves page keeps copies ([save-backups.md](docs/psnova/save-backups.md)).
- The repository stores LF line endings (`core.autocrlf false`); write files with `newline='\n'`. The `.bat` files
  are CRLF.
- Never commit personal paths (`C:\Users\<name>\…`) or personal email addresses.
