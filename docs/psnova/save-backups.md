# Save backups in the F10 menu (2026-11-19)

The user asked for save states in the menu, "so that we move to a place easier".

## Why not save states

An emulator can freeze the whole machine because it owns all of it. A recompiled game runs as the PC's own code: each
guest function is a C function (`fn_8187886a(c);`) called on the host's own stack, and the game's threads are real
Windows threads. A thread's position therefore lives in host stack frames, which can't be written to a file and resumed.
True save states would need a different runtime design.

## What was added instead

A **Saves** page in the F10 menu (between Game and Controls) that keeps copies of the game's own save folder:

- **The game's save now:** the current save's own description, read from its slot marker (for Phantasy Star Nova:
  "Nova/ハンターLv1/0:02" and the chapter "惑星の洗礼"), and when it was saved.
- **Back up:** copies `<RECOMP_FS>/savedata0` to `<RECOMP_FS>/../save_backups/<date> <name>/`. For the player's copy
  that is `dump/decrypted/PCSG00351/recomp/save_backups/`. The name is optional (letters, digits, spaces; ASCII only, because
  the Windows C library opens paths in the ANSI code page; no dots, so a name can't make "..").
- **Restore** (asks first): backs up the current save as "<date> before restore", then puts the backup in its place.
  The game reads its save only when it loads one, so the player then loads it: the title screen's Continue (restart the
  game first if in play).
- **Delete** (asks first).

It only reaches points where the game itself saved. The menu pauses the game, so the game isn't writing its save during
a copy.

## Files

- `runtime/ui/save_backups.c` / `.h`: the file work (copy, list, restore, delete; slot marker parsing as in
  `runtime/core/apputil.c`). Added to the host source list in `runtime/build.py`.
- `runtime/ui/overlay.cpp`: `page_saves()` and the tab wiring (`TAB_SAVES`).
- `runtime/ui/ui_theme.h`: `load_system_font` merges a Japanese face (Yu Gothic, Meiryo or MS Gothic on Windows) into
  the menu font, so a Japanese game's words show instead of boxes (the Saves page and the in-game save dialog).

## Tests

- `dev/psnova/tests/save_backups_test.c` (`build/save_backups_test.exe <fs folder>`): back up, list, change the save,
  restore, compare bytes, the "before restore" copy, bad names, delete. 17/17 passed on a copy of the player's save.
  Build line: as for `usse_dis` in `docs/psnova/cutscene-colours.md`, plus `-D_POSIX_THREAD_SAFE_FUNCTIONS` and
  `runtime/ui/save_backups.c`.
- `dev/psn-logs/saves-page.png`: the page rendered headless (`RECOMP_OVERLAY_DUMP=<ppm>
  RECOMP_OVERLAY_DUMP_UI=menu:Saves`), with a backup listed and the Japanese slot text drawn.

## Review (2026-11-19, 3 lenses, each finding checked by a skeptic)

Confirmed and fixed:
- **The list kept the 64 oldest backups.** It stopped reading the folder at 64 entries, in listing order (NTFS lists by
  name, and the names start with the date), then sorted. Past 64, new backups and the "before restore" copy vanished
  from the page. Now every name is read, sorted newest first, then cut. Test added (71 backups, room for 64).
- **L1/R1 onto the Saves page started text editing** in the name field (the page's first control gets the keyboard
  focus), which then held the next L1/R1. Saves no longer takes that focus.
- **L1/R1 could change the page under the confirmation**, leaving the modal in ImGui's popup stack. Stepping is off while
  a confirmation is open.
- **The Japanese font's cost:** ImGui reads the whole file at start, so the comment saying "costs nothing" was wrong. MS
  Gothic (9 MB) is now first instead of Yu Gothic (14 MB).
- **macOS:** the fallback named a Chinese face (Hiragino Sans GB); now Hiragino Kaku Gothic (Japanese).

Refuted by the skeptics (left as they are): a name-collision overwrite, Windows names ending in a dot, the game writing
its save during a copy, the confirmation surviving a menu close, overlay.o rebuild dependencies, a failed font load
aborting, read-only save files.

game_host.exe rebuilt 08:46:30 with the page and these fixes; windowed check (test91) clean.
