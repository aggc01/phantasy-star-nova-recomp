# Windows release layer: source copy

This folder holds the files that the Windows release adds on top of the engine. The paths match the release folder (`setup.py` sits at the release root, `engine\release\play_nova.c` under `engine\release`, and so on).

What is here: the setup program (`setup*.py`), the two launcher sources, the release tooling, the localization build scripts, and the player and maintainer guides.

What is not here:
- Binaries: the compiled launchers, `ffmpeg.exe` and its source archive, the bundled Python and toolchain.
- The English text and movie recipes (`localization\text`, `localization\movies`) and the font.
- The engine itself, which comes from this checkout. The release engine edits listed in `MAINTAINER-NOTES.md` are now in the checkout (saves under `RECOMP_SAVE_ROOT`, streamed PKG import, the `vitarecomp.py` licence and layering changes, the two extra function seeds), with one exception: the checkout keeps the Arabic right-alignment hooks in `packs/PCSG00351`, which the English-only release removes. They do nothing unless a message starts with the Arabic marker.

To build a release, follow "How the release folder was built" in `MAINTAINER-NOTES.md`, copying these files into their matching paths.
