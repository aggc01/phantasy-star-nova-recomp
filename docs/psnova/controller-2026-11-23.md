# Nova controller input

23 November 2026.

The reported session detected an Xbox 360 controller after startup. The native PC save picker still showed keyboard hints. The shared setting `input_mode = kbm` selected keyboard-and-mouse input, which rewrote both gameplay sticks with WASD and mouse values. That explains how controller buttons could work with movement and camera control missing.

The window owns one SDL gamepad handle and shares it with the ImGui overlay. It opens a controller at startup or on connection and transfers control to a remaining device when the active controller disconnects. Device handling and Auto input switching run before the modal input gate, including while a save or load prompt is open. The window reads the four controller axes when the controller takes over, including axes already held during the switch.

The PC picker uses the D-pad or left stick to navigate, A / Cross to select, and B / Circle to go back. Nova's in-game prompts retain the Japanese control layout, where B / Circle confirms and A / Cross cancels. The default trigger mapping sends LT and RT as the Vita's L and R. LB and RB activate the front and rear touch cursors. The F10 Controls page offers a Bumpers setting for L and R.

## Verification and installation

An isolated Windows build exercised the production event and dialog paths with in-process SDL virtual controllers. It connected a controller while Nova's load list was open, canceled with B, switched to a second connected controller when the first was removed, selected the Level 8 Force slot and confirmed with A. Nova opened `savedata1.bin` from the isolated fixture. The guest input recording showed both controller sticks together after using the keyboard, plus D-pad Up and Down, Circle, and the left trigger. A frame replay also showed the in-game System menu after opening and navigating it with the controller. The copied and live save files matched their original SHA-256 hashes after the load and gameplay test. The test scripts, input recording, and logs are under `dump/codex-controller-20261123/`. Physical gamepad hardware was outside the completed tests.

The normal launcher now runs the controller build as `dump/decrypted/PCSG00351/recomp/game_host.exe`. Its SHA-256 is `70e42086f022dcb4305507c6ced8dbcd864d4bdc48b5fd8e0ed3e228012d68a8`. Nova's local `settings.ini` selects Auto, allowing either input device to take over. The executable and settings from before this change are backed up under `dump/codex-controller-20261123/`.

In the loaded base scene, D-pad Up opened the weapon palette. Start opened Nova's main menu. System → Save opened Nova's own Yes/No prompt with Yes selected. B / Circle confirmed it and Nova wrote 569,108 bytes to the copied slot 1. This was a fixed-slot save, which logs the write directly. The initial test looked for a completion message, so I checked the actual write, file size, and hashes separately and corrected the test's completion check. The copied progress and slot metadata changed as expected. The live save hashes matched the pre-test snapshot.
