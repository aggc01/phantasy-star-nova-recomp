# Phantasy Star Nova recomp: start here

This folder is a git worktree of the Project Nativ checkout in
`..\recent recomps\Uncharted Golden Abyss Recomp` (branch `psnova`, made from `main` 2245178 on 2026-11-18).
It turns the PS Vita game **Phantasy Star Nova** (PCSG00351, Japan, update 1.05) into a native Windows program.

- **The one state file:** [docs/psnova/README.md](docs/psnova/README.md): what works, what is open, how to build, run
  and test, and every claim's strength (proven / single run / untested). Update it in place; don't start new status files.
- **Project Nativ's own guides** (how the recompiler and runtime work): [README.md](README.md),
  [docs/developers.md](docs/developers.md), [docs/debugging.md](docs/debugging.md).
- **Lessons from the earlier recomps**, applied here from day one: `..\recomp_study\RETROSPECTIVE.md` and
  `..\recomp_study\RECOMP_PLAYBOOK.md`.

Rules for this copy:

- It has its own library (`dump/`), its own branch and its own builds. Nothing here is linked into the Uncharted
  copies, and nothing of theirs is written from here. The toolchain and Python are *read* from the main Uncharted
  checkout by path (see `dev/psn_build_all.sh`), never through a junction.
- The player's game files in `F:\RECOMP GAMES\Phantasy Star Nova (v1.05)` are read only.
- Saves live in `dump/decrypted/PCSG00351/recomp/fs/`; back them up fresh before any test run that could write them.
