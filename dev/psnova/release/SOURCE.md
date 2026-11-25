# Windows release layer: source copy

This folder holds the files that the Windows release adds on top of the engine. The paths match the release folder (`setup.py` sits at the release root, `engine\release\play_nova.c` under `engine\release`, and so on).

What is here: the setup program (`setup*.py`), the two launcher sources, the release tooling, the localization build scripts, and the player and maintainer guides.

What is not here:
- Binaries: the compiled launchers, `ffmpeg.exe` and its source archive, the bundled Python and toolchain.
- The English text and movie recipes (`localization\text`, `localization\movies`) and the font.
- The engine itself, which comes from this checkout. `MAINTAINER-NOTES.md` lists the release-only engine edits; they are not applied here.

To build a release, follow "How the release folder was built" in `MAINTAINER-NOTES.md`, copying these files into their matching paths.
