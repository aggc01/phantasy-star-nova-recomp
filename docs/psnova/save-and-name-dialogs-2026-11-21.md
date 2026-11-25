# Nova save picker and character-name input


## Save picker

Nova still opens and advances the Vita save-data service. The recomp presents its steps in an original Project Nativ panel with Nova's existing save icon, a selection accent, the stored date and input hints. The original slot IDs, focus logic and save callbacks continue to drive selection, confirmation and progress.

In English mode, the picker and the backup list translate the class in the slot's subtitle and the chapter in its detail. The class parser works from the right of `name/classLvN/time`, so the player name can contain slashes or Japanese class words. The helper uses the active session language. It recognizes four classes and fourteen chapters from sheet v7 and passes through unknown metadata. Displaying this information never rewrites a save.

On an isolated copy of the three reported slots, the picker displayed Hunter / Planet’s Baptism, Force / Steel Giants, and Hunter / Planet’s Baptism. It showed each slot's original level, playtime and timestamp. Selecting Force and confirming caused the guest to open `savedata1.bin`, and the level 6 character appeared in gameplay. All six copied slot metadata and progress files matched their originals byte for byte after the load. The metadata fixture also checked a name containing a slash and Japanese text, all four classes, and passthrough in the original language.

A separate runtime callback test used the three copied slot records and exercised list focus, stale input rejection, selection of slot ID 1, overwrite cancellation and overwrite confirmation. It checked the results passed back to the guest dialog.

## Character creation

Nova’s `sceImeOpen` request now opens an editor in the window. Controller mode shows a navigable grid with letters, case, symbols, numbers, space, erase and Done. Cross selects a key, Start confirms and Circle cancels. Keyboard & mouse mode focuses a text field for SDL text input, including normal selection, backspace, Enter and Escape. Automatic mode takes the currently active device on open. The selected editor stays in use for that request.

The UI sends UTF-8 to the guest bridge. The bridge converts it to UTF-16 without splitting a surrogate pair, checks the request sequence, and sends the final text update before Enter or Close. The window neutralizes guest gameplay input while a prompt owns it. Headless runs retain their existing scripted name behavior.

An isolated live character-creation run opened an empty keyboard field with the game-provided 10-unit limit. Typing `DiscardMe` displayed it in the editor, and Escape returned to the creation menu. The guest log recorded the close callback. A separate test of the actual editor code sent synthetic keyboard and gamepad input through ImGui. It covered entering exactly 10 units, rejecting overflow, Escape, D-pad navigation, case switching, erasing a character and submitting with Start. A C smoke test checked delayed callbacks, cancellation and surrogate-pair boundaries.

A second live run opened Controller mode. Clicking the on-screen grid entered `qa`, and Done handed that name to Nova's registration screen without dismissing the game's own confirmation. The test advanced to the Start the Game step. Physical gamepad hardware and saving and reloading a newly named character were outside the completed smoke tests. The controller navigation was exercised with synthetic gamepad events.

Screenshots of the picker, the on-screen keyboard and the game's registration prompt are in `dump/codex-dialogs-20261121/evidence/`.

## Build

The normal Nova launcher uses the installed `game_host.exe`. Before it was replaced, the previous executable was kept as `game_host.before-codex-dialogs.exe` beside it. The installed executable's SHA-256 is `0f27c260f49a8767af14f7131e3e866a29507ca445d0b44ec513b26c57acbfbd`. The Windows build now detects an identical SDL DLL before copying so an already-mapped copy can be reused.
