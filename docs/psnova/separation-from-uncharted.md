# Phantasy Star Nova: separated from the Uncharted folder (2026-11-19)

User's instruction: "only work in your folder (only work in Drive F) and separate your work from Uncharted cleanly",
done by the localization session together with the PS Nova recomp session (it agreed to every step and paused git work);
the Uncharted RT session was told and confirmed nothing of Uncharted depends on PS Nova.

## What PS Nova used to take from "recent recomps\Uncharted Golden Abyss Recomp"

| What | Before | Now (all inside `Phantasy Star Nova Recomp`, all git-ignored) |
|---|---|---|
| git | this folder was a **worktree** of the Uncharted repository (branch `psnova`; `.git` was a file pointing to `Uncharted\.git\worktrees\Phantasy-Star-Nova-Recomp`) | **its own repository** (`.git` folder): branches `main` and `psnova` fetched from the Uncharted repo, HEAD `psnova` (3e5328a), `core.autocrlf false` as before |
| Python | `Uncharted\.venv` (base `C:\Python314`; numpy, OpenCV, Pillow from `C:\Users\...\AppData\Roaming\Python`) | `tools\python` = a copy of Python 3.14.5 with numpy 2.4.6, opencv-python-headless 4.13, Pillow 12.2, pycryptodome, capstone 5.0.9, pyflakes copied in (no downloads); `.venv` made from it (`--system-site-packages`); nothing on C: is used |
| Toolchain | `Uncharted\toolchain` (llvm-mingw, SDL3, ffmpeg, zlib; 968 MB) | `toolchain\` = a byte-identical copy (`diff -rq` clean); runtime/build.py's default `<root>\toolchain` |
| ffmpeg for movie work | `F:\Antigravity Proj\animation\node_modules\ffmpeg-static\ffmpeg.exe` | `tools\ffmpeg.exe` (same file); the movie scripts (remove_jp_subs*.py, redraw_attention.py, survey_other_movies.py) find it relative to themselves |
| Scratch files | the session's scratchpad on C: | `dump\psnova-l10n\scratch\` (old scratch copied there) |

`dev/psn_build_all.sh` defaults: `PY=$PWD/.venv/Scripts/python.exe`, `ATIV_WIN_TOOLCHAIN=$PWD/toolchain`. By hand:
`.venv/Scripts/python.exe -s pipeline/vitarecomp.py <stage> PCSG00351` (ATIV_WIN_TOOLCHAIN not needed).
Proof: `RECOMP_BIN=l10n` build at 06:47 with only these tools (log: no path into the Uncharted folder); the recomp
session ran its own check build with the new defaults.

## How the git split was done (and how to undo it)

1. Backups in `dump\psnova-l10n\separation\`: `nativ-main-psnova-20261119.bundle` (main + psnova, verified),
   `dotgit-file-backup` (the old `.git` link file), `worktree-registration-backup\` (Uncharted's registration folder),
   `status_before.txt`, `log_before.txt`, `diff_before.patch`.
2. Here: removed the `.git` file, `git init`, `git fetch "<Uncharted repo>" main:main psnova:psnova`,
   `git symbolic-ref HEAD refs/heads/psnova`, `git reset` (index only: every uncommitted change stays as it was),
   `git config core.autocrlf false`.
3. Checked: `git log psnova` identical; `git status --porcelain=v1 -uall` byte-identical to before (`status_after2.txt`).
4. In the Uncharted repo: removed **only** `.git\worktrees\Phantasy-Star-Nova-Recomp` by hand (no `git worktree prune` /
   `remove`: the RT, Native and add-game-fix worktrees, the last with uncommitted work, are registered there too).
   `git worktree list` there now shows main, add-game-fix, native-renderer, raytracing.
5. **Kept on purpose:** the `psnova` branch in the Uncharted repository, as an archive (deleting it is the user's call).
   Uncharted's `.venv`, `toolchain\` and `tools\` were not touched (the RT copy's tools\ and toolchain\ are junctions into
   them).

Undo: delete this `.git` folder, copy `dotgit-file-backup` back as `.git`, copy `worktree-registration-backup` back to
`Uncharted\.git\worktrees\Phantasy-Star-Nova-Recomp`.

## Line endings (found during the split)

The repository stores LF. Python's text mode on Windows had rewritten 7 tracked files as CRLF in this session (the
localization session's edits: vitarecomp.py, io.c, fios.c, overlay.cpp, pack.toml, psn_build_all.sh,
localization-notes.md); converted back to LF with `dump\psnova-l10n\scratch\to_lf.py` (also the new localization
scripts). The recomp session was told that three of its files (gfx_gpu.c, display.c, docs/psnova/README.md) are CRLF
in the working copy too. Lesson: write files with `open(p, 'w', newline='\n')` or in binary.

## Still outside F: or outside this folder

- The game itself was decrypted from `F:\RECOMP GAMES\Phantasy Star Nova (v1.05)` (F:, read only).
- The user's reference frames from a real Vita playthrough at `C:\New PATH\screenshots` (1.4 GB, read by the recomp
  session): the user's files; not moved (asked the user).
- The development tools' own memory notes and session transcripts live in `C:\Users\<user>\.claude` (the app's place, not ours).
- Cross-session coordination and the in-app task list: no files.
