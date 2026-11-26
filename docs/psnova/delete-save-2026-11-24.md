# Deleting a Nova save slot

24 November 2026.

In the PC picker, click **Delete...** on the slot, or highlight it and press **Delete** on the keyboard or **X / Square** on a controller. The confirmation identifies the slot and starts on **Cancel**. Move to **Delete** and confirm, or use **Esc / B / Circle** to return to the list. Open the picker from **Continue** on the title screen. Nova's fixed-slot in-game Save command uses its own confirmation.

The host checks that the same picker step and character slot are still active. It moves only the selected slot's `savedataN.bin` and `.slotN` into a unique directory under `<RECOMP_FS>/deleted_saves/`. The normal install uses `recomp/fs/deleted_saves/`. It preserves `system.bin`, Nova's `.slot255` system marker, and the other character slots. The load list drops the deleted row. A save list shows the slot as **New Saved Data**. Both updates keep the guest dialog open and use the original guest slot IDs for later selections.

If a save file move fails, the picker keeps the slot. If the metadata move fails after the payload move, the runtime moves the payload back. A legacy marker with a missing payload can still be moved out of the list. To recover a deleted slot, close Nova and copy its archived pair back to `savedata0` while that slot is empty.

## Verification

An isolated Windows run exercised the actual picker with virtual SDL keyboard and gamepad input. Cancel preserved all files, a blocked recovery destination preserved the slot, and controller confirmation moved only slot 1 to recovery. Both archived files matched their originals byte for byte. The refreshed list selected and loaded neighboring slot 0. Every live save file matched its pre-test SHA-256 hash.

The file and list regression check also covered a stale request, the protected system marker, a failed metadata move with rollback, converting a deleted save-list row to an empty slot, and removing the last load row when its payload was already missing. Scripts and logs are under `dump/codex-delete-save-20261124/`. The on-screen mouse button and physical controller were outside the automated input trial.

## Installed build

The normal launcher uses `recomp/game_host.exe` with SHA-256 `285acd4e359cb70d884ab593befa0d52206e30527c9e439824327d11a9564927`. The previous controller build is backed up at `dump/codex-delete-save-20261124/game_host.before-delete-save.exe`.
