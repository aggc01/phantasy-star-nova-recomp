# Vita firmware dialog bring-up

Done by Codex, 21 November 2026.

The probe uses the original modules from the local Vita 3.74 firmware. The launcher's installed executable is still the verified PC dialog build. Its SHA-256 is `0f27c260f49a8767af14f7131e3e866a29507ca445d0b44ec513b26c57acbfbd`. Test runs use independent save directories and compare hashes with the live save directory.

## Save picker

- Nova's boot-time save dialog reached the firmware's `sceSaveDataDialogInit` and returned 0. The runtime then ran the original startup callbacks for the common-dialog main module, PAF, and Common GUI. Nova polled the original firmware status functions. The game reached the title with **Continue** selected.
- The first PAF run also exposed Nova's trophy setup dialog. The probe uses the existing host handlers for trophy setup, message, and network-check dialogs. PAF loaded the original save plug-in, called its start routine, and opened `savedata_dialog_plugin.rco`. The log for that stage is under `dump/codex-firmware-dialogs/runs/save-pvf/`.
- PAF looked for `sa0:data/font/pvf/jpn0.pvf`. The main firmware package omits that partition. I retrieved the separate Sony font package, verified SHA-256 `c3c03fc7363dd573d90e5157629bf11551f434b283cc898d9ffc71dd716b791c`, and extracted `sa0` into the test filesystem. [Vita3K firmware installation notes](https://vita3k.org/quickstart#installing-the-firmware) · [Published package hash](https://abdess.github.io/retrobios/systems/sony-playstation-vita/)
- The probe uses deferred module entry points so the guest receives the firmware's startup arguments. The `vs0` and `sa0` mounts are read-only. The deferred images activate the runtime bridge.
- With the fonts mounted, the firmware opened both `jpn0.pvf` and `ltn0.pvf`. Selecting **Continue** reached the second firmware dialog. The native PAF thread advanced through the default graphics surface pool, then the dialog stayed in Running status and the frame stayed black. `continue-black.log` and `continue-02700.png` preserve that run. The second run uses the full firmware lifecycle from boot through Continue.
- The `save-list` profile handles the boot dialog through the established host path to test a first firmware slot-list session. The first test closed the firmware dialog before its rows appeared. The plug-in rejected the stubbed zero SDK version and advanced after the probe returned the staged firmware's encoded version, `0x03740000`.
- After the SDK correction, the original resource reader reached unsupported ARM NEON instructions. Codex added widening and variable shifts, logical immediates, and widening accumulation used by the firmware's resource path. Compiled smoke checks exercised the exact instructions with overlapping input registers, shifts outside the lane width, and positive and negative accumulation.
- The stage includes an AppMgr metadata reader that reuses the project's slot files and English translations. It copies display fields into the guest's size-tagged `0x418`-byte request using the existing `0x34c`-byte metadata structure. The existing translation fixture passed. The firmware still needs its slot-file API before the list can exercise that metadata adapter.
- The final `save-list` run reached frame 2700 without an instruction fault. It opened the original dialog resources and then called the missing `sceAppMgrSaveDataSlotFileOpen` and `sceAppMgrSaveDataSlotFileClose` services. The renderer also reported unsupported `0x95840000`, a P8 paletted texture. `after-resource-02700.png` shows a magenta strip and an empty slot area. The picker requires slot-file support and rendering for this texture format before a copied slot can be selected. [VitaSDK GXM texture formats](https://github.com/vitasdk/vita-headers/blob/master/include/psp2/gxm.h)
- Firmware module IDs and the option layout were checked against [VitaSDK's SceSysmodule header](https://github.com/vitasdk/vita-headers/blob/master/include/psp2/sysmodule.h). Local module inspection established the calls and data flow. No firmware files are part of the patch.

## Controller keyboard

The original `libime` starts inside Nova's isolated test build. The console client depends on `libshellsvc` and the shell's `SceImeService`. The local shell binary references the service, its client list and event queue, and the `ime_plugin` resource. At startup, `libshellsvc` tried to open a named message pipe and reported `IPC Server is not available (0x80020583)`. Later, selecting **Enter Character Name** called the original `sceImeOpen`, which returned `0x80100705` after calling the original IPMI client imports. The log is under `dump/codex-firmware-dialogs/runs/ime-service/session.log`. The named shell IPC server and IME plug-in lifecycle are prerequisites for the native keyboard.

## Running the probes

Use `dev/psnova/probe_firmware_dialogs.py` from the repo with `save-pvf` for the full save-dialog path, `save-list` to exercise the native slot list on its first open, or `ime-service` for the shell-service probe. The executable and module images are staged under `dump/codex-firmware-dialogs`. Each run writes its own log under `runs/<profile>`. The save profiles need the copied slots under `fs/savedata0`. The name probes use `fs-ime/savedata0`. Both mounts use the local game assets and English overlay. The tests stop on a frame count or after a three-minute timeout.

The normal launcher was left on the previous build because a usable firmware picker, controller keyboard, and named-character save/load round trip still require verification.
