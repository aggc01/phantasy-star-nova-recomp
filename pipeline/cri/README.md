# CRI CPK tools used by the pipeline

Copies of `dev/psnova/cpk.py` (reader, CRILAYLA) and `dev/psnova/cpk_merge.py` (copy an archive, add entries from
another), taken 2026-11-18 for `vitarecomp import`'s `REPATCH_KEEP` step (pack.toml). The format notes, the merge layout
and its checks are in `dev/psnova/CPK-MERGE.md` and the tools' own docstrings. Change them here and in dev/psnova together.

Why: a fan translation's rePatch replaces a whole archive; Phantasy Star Nova's English rePatch dropped one entry the
official 1.05 update has (`tex_nova_ui_common.aif`), and the game then showed noise on Filldia and its NOW LOADING
screen. `REPATCH_KEEP = "<archive>:<entry> ..."` carries such entries over into a merged copy of the rePatch archive.
