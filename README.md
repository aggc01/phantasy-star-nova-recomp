# Phantasy Star Nova Recomp

**A fork of [Project Nativ](https://github.com/TheLostPantheon/nativ), focused on *Phantasy Star Nova*.**

Phantasy Star Nova Recomp runs the Japanese PS Vita release of *Phantasy Star Nova* (tri-Ace / SEGA, 2014) as a
native Windows program. You bring your own copy of the game. The tools recompile it on your PC, with an English
localization, higher resolutions, a 60 FPS target, and keyboard, mouse and controller support.

It builds on Project Nativ, which recompiles PS Vita games into native PC programs. This fork keeps Nativ's
recompiler and runtime, and adds the game pack, fixes, tools and Windows release for *Phantasy Star Nova*.

## Nothing of the game ships

This repository holds no game code, game data or firmware. You supply your own copy of the game and Sony's firmware
update file, and the tools decrypt and recompile them on your machine.

## Supported version

| | |
| --- | --- |
| Game | *Phantasy Star Nova*, Japan, PS Vita. Title ID `PCSG00351` |
| Base game and update | 1.00 with the official 1.05 update |
| System software | PS Vita 3.74 (`PSVUPDAT.PUP`) |
| Platform | 64-bit Windows 10 or 11 with a Vulkan graphics driver |

Other regions, versions and copies that already carry a fan translation are not supported.

## What this fork adds

- **English localization:** menus, dialogue, UI art and movie subtitles, built on your PC from recipes in this
  repository. Some lines and screens are still Japanese. The original Japanese stays available from the F10 menu.
- **Rendering:** up to 4× internal resolution, a 60 FPS target, and graphics fixes in the shared runtime (depth clip,
  deferred draws, GPU lines).
- **Controls:** keyboard and mouse, and Xbox-style controllers with hot-plugging. The input mode follows the device
  you used last.
- **Saves:** a save picker, save backups and deleted-save recovery, with saves kept outside the build.
- **A Windows release** with one setup program that imports your PKG files, builds the game and installs it. It also
  exports redacted support reports, and can install signed in-place updates (off until a feed is configured).

## Status

Beta. The Windows release is at 0.1.0 Beta 1. The game is playable in English, with known gaps listed in
[docs/psnova/README.md](docs/psnova/README.md), the state file for this game.

## Where things are

| Path | What's in it |
| --- | --- |
| `packs/PCSG00351/` | The game pack: versions, hooks, function seeds and shader recipes |
| `dev/psnova/` | Nova tools: text and UI rebuilds, CPK archive tools, movie subtitles, checks |
| `dev/psnova/release/` | The Windows release layer: setup, launchers, update tooling, player and maintainer guides |
| `docs/psnova/` | Nova documentation: the state file, journals, investigations and decisions |
| `Play Phantasy Star Nova.bat` | Starts a development build from `dump\` |
| `recompiler/`, `runtime/`, `pipeline/`, `decrypt/` | The Project Nativ engine |

## Getting started

**Players** use the Windows release: extract it, run `Setup Phantasy Star Nova.exe` and choose your game files. The
player guide is [dev/psnova/release/README.md](dev/psnova/release/README.md). How to build a release folder is in
[MAINTAINER-NOTES.md](dev/psnova/release/MAINTAINER-NOTES.md).

**Developers** build from this checkout on Windows:

```powershell
bash dev/psn_build_all.sh                                       # import, analyze, recompile, build
.\.venv\Scripts\python.exe -s .\pipeline\vitarecomp.py <stage> PCSG00351   # one stage by hand
```

[docs/psnova/README.md](docs/psnova/README.md) explains the setup, and the journal it links covers what was tried
and the traps to avoid.

## Relationship to Project Nativ

- The engine (recompiler, runtime, pipeline and decryption) comes from Project Nativ. Its design and developer docs
  are in [docs/](docs/architecture.md) and upstream at
  [TheLostPantheon/nativ](https://github.com/TheLostPantheon/nativ).
- This fork changes the engine where *Phantasy Star Nova* needs it: graphics fixes, saves outside the build, streamed
  PKG import and the Windows release.
- Nativ's other game packs (Killzone: Mercenary, Unit 13, Shovel Knight) are still in `packs/` but are not
  maintained or tested here. The Uncharted pack and its research are not part of this fork.

## Licence

This fork, like Project Nativ, is free software under the GNU General Public License, version 2 or (at your option)
any later version: see [LICENSE](LICENSE). Third-party code keeps its own licence, and
[THIRD_PARTY.md](THIRD_PARTY.md) lists it with the projects parts of Nativ are ported from.

It contains no Sony or game code. The English localization rebuilds need the Glenth Regular font, which you supply.

## AI disclaimer

Like Project Nativ, this fork is made with the help of AI tools: much of its code and documentation was written with
AI assistance, under its developer's direction, and tested on the game itself.

## Credits

Project Nativ is by its developer at [TheLostPantheon/nativ](https://github.com/TheLostPantheon/nativ). To support
Nativ itself, see its [Ko-fi](https://ko-fi.com/kingtorro).
