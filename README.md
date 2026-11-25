# Phantasy Star Nova Recomp

**A fork of [Project Nativ](https://github.com/TheLostPantheon/nativ), focused on *Phantasy Star Nova*.**

Phantasy Star Nova Recomp turns the Japanese PS Vita release of *Phantasy Star Nova* (tri-Ace / SEGA, 2014) into a
native Windows program. It is not an emulator. The game's ARM code is translated to C once, ahead of time, and compiled
into a normal Windows executable. A runtime stands in for the Vita's system software and hardware: it runs the game's
threads, draws its graphics on your GPU through Vulkan, plays its sound and movies, and reads your keyboard, mouse or
controller.

You bring your own copy of the game. Nothing of the game ships in this repository.

## What you get

- **The full game running natively**, from the title screen through gameplay, movies and saves.
- **Higher resolution and frame rate:** up to 6× the Vita's 960 × 544 internal resolution, and an optional 60 FPS
  mode where the Vita ran at 30.
- **PC controls:** keyboard and mouse, or an Xbox-style controller you can plug in at any time. The game follows
  whichever device you used last.
- **Saves you can manage:** a PC save picker, and save backups from the in-game menu.
- **An in-game menu (F10)** for resolution, frame rate, controls, language and saves.
- **Graphics fixes** for depth, deferred draws and lines that the Vita's GPU handled differently.

## Status

**Beta.** In testing on Windows 11, the game runs through character creation, gameplay, movies, saving and loading.
An English localization exists, but its
text and subtitle data are not in this repository yet, so a build from this repository plays the **Japanese** game
(see [English](#english)). Known issues are tracked in [docs/psnova/README.md](docs/psnova/README.md).

## What you need

| | |
| --- | --- |
| PC | 64-bit Windows 10 or 11, a GPU with a current Vulkan driver, about 20 GB of free disk space |
| Software | [Git for Windows](https://git-scm.com/download/win) (for Git Bash) and [Python](https://www.python.org/downloads/) 3.12 or newer |
| The game | *Phantasy Star Nova*, Japan, title ID `PCSG00351`: the **1.00** base game and the official **1.05** update, as PKG files or as folders copied from a Vita (`ux0:app/PCSG00351`, `ux0:patch/PCSG00351`) |
| The game's licence | `work.bin` or a `.rif` file for your copy |
| Vita system software | `PSVUPDAT.PUP` 3.74, from [PlayStation's download page](https://www.playstation.com/en-us/support/hardware/psvita/system-software/) |

Other regions and versions are not supported. Use an unmodified copy.

## Setup

Run these from PowerShell in the folder where you want the project, unless a step says Git Bash. The first build takes
about an hour; later runs start in seconds.

**1. Get the code and its Python packages.**

```powershell
git clone https://github.com/aggc01/phantasy-star-nova-recomp.git
cd phantasy-star-nova-recomp
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**2. Install the compiler toolchain** (Clang for Windows, SDL3, zlib and FFmpeg's decoders, at pinned versions). Open
**Git Bash** in the project folder:

```bash
ATIV_WIN_TOOLCHAIN="$PWD/toolchain" bash runtime/platform/win/setup-toolchain.sh
```

This downloads and builds into `toolchain\`, where the build looks for it.

**3. Prepare the Vita system software.** The game needs some of Sony's system modules, which are taken from the
firmware file you downloaded:

```powershell
.\.venv\Scripts\python.exe pipeline\vitarecomp.py firmware "C:\path\to\PSVUPDAT.PUP"
```

**4. Add the game, then its update.** The first command decrypts and keeps the base game. The second adds the 1.05
update and then builds everything: import, analysis, recompilation and compilation.

```powershell
.\.venv\Scripts\python.exe pipeline\vitarecomp.py add "C:\path\to\base-game.pkg" --license "C:\path\to\work.bin" --no-build
.\.venv\Scripts\python.exe pipeline\vitarecomp.py add "C:\path\to\update-1.05.pkg"
```

Folders copied from a Vita work in place of the PKG files. Your files are only read. Everything the build makes goes
under `dump\` in the project folder.

**5. Play.** Double-click **`Play Phantasy Star Nova.bat`**.

To rebuild after changing the code, run `bash dev/psn_build_all.sh` from Git Bash. It runs the import, analyze,
recompile and build stages again and writes a log for each to `dev/psn-logs/`.

## Playing

The game starts at the Vita's own resolution and 30 FPS. Press **F10** at any time for the in-game menu, and raise
the resolution (up to 6×) and the frame rate (60 FPS) there. Both are saved for next time. 4× and above need a
strong GPU.

| Action | Keyboard and mouse | Controller |
| --- | --- | --- |
| Move | W A S D | Left stick |
| Camera | Mouse | Right stick |
| Confirm (Circle) / Cancel (Cross) | C / Space | B / A |
| Square / Triangle | F / E | X / Y |
| L / R | Q / R, or the mouse buttons | LB / RB |
| D-pad | Arrow keys | D-pad |
| Start / Select | Enter / Tab | Menu / View |
| In-game menu | F10 | |
| Quit | Alt+F4 | |

Controls can be changed in **F10 → Controls**.

| What | Where |
| --- | --- |
| Saves | `dump\decrypted\PCSG00351\recomp\fs\savedata0` |
| Settings | `dump\decrypted\PCSG00351\recomp\settings.ini` |
| Log | `dump\decrypted\PCSG00351\recomp\session.log` |

Back up your saves from **F10 → Saves** before trying anything risky.

## English

The English localization covers menus, dialogue, UI art and movie subtitles, with some lines still in Japanese. It is
built as an overlay on the Japanese game: the original archives stay untouched, and **F10 → Game → Language** switches
between English and the original Japanese.

The tools that build it are in this repository (`dev/psnova/rmdtext/`, `dev/psnova/uitex/` and the movie subtitle
scripts in `dev/psnova/`). The translated text and subtitle data they read are not published here yet. Until they
are, a build from this repository plays in Japanese.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| `no Windows toolchain at …` | Run step 2 again, and check that `toolchain\llvm-mingw` exists. |
| `Python not found` when starting the game | Create `.venv` as in step 1. |
| The update is refused or asks for a licence | Add the base game first (step 4), with its `work.bin` or `.rif`. |
| A stage fails during the build | Read its log in `dev/psn-logs/`, or the command's output. Most failures name the file or setting at fault. |
| Black screen or crash at start | Update your GPU driver. Check `session.log` for the last lines before the problem. |

## How it works

1. **Import:** the game's executable and Sony's system modules are decrypted from your files and checked against the
   versions this project supports.
2. **Analyze:** every function in the game's 28 MB executable is found, about 40,000 in all.
3. **Recompile:** each function's ARM instructions are translated to C. The output is about 1 GB of C in 100 files.
4. **Build:** Clang compiles that C together with the runtime into one Windows program.
5. **Run:** the runtime provides what the game expects from a Vita: memory, threads, files, the GPU, sound, input and
   the system dialogs for saves and names.

Game-specific fixes, such as the 60 FPS frame pacing and the input hooks, live in
[`packs/PCSG00351/`](packs/PCSG00351/pack.toml). Project Nativ's [architecture guide](docs/architecture.md) explains the
recompiler and runtime in depth.

## Repository layout

| Path | What's in it |
| --- | --- |
| `packs/PCSG00351/` | The game pack: supported versions, code hooks, function seeds and shader recipes |
| `recompiler/` | The static recompiler (ARM to C) |
| `runtime/` | What the recompiled game runs on: kernel and libraries, graphics, audio, input, UI |
| `pipeline/` | `vitarecomp.py`, the driver for every stage |
| `decrypt/` | Decryption of firmware and game packages |
| `dev/psnova/` | Nova tools: localization builders, archive tools, subtitles, checks |
| `dev/psnova/release/` | The standalone Windows release: setup program, launchers and guides |
| `docs/psnova/` | Nova documentation: current state, investigations and design notes |

## Relationship to Project Nativ

The recompiler, runtime, pipeline and decryption come from Project Nativ
([TheLostPantheon/nativ](https://github.com/TheLostPantheon/nativ)). This fork changes them where *Phantasy Star Nova*
needs it, and adds the game pack, the localization tools and the Windows release. Nativ's other game packs (Killzone:
Mercenary, Unit 13, Shovel Knight) are still in `packs/` but are not maintained or tested here.

## Licence

Free software under the GNU General Public License, version 2 or (at your option) any later version, like Project
Nativ: see [LICENSE](LICENSE). Third-party code keeps its own licence, listed in [THIRD_PARTY.md](THIRD_PARTY.md).

This repository contains no Sony or game code. The game is recompiled on your machine from your own copy and never
leaves it.

## Credits

Built on [Project Nativ](https://github.com/TheLostPantheon/nativ). To support Nativ itself, see its
[Ko-fi](https://ko-fi.com/kingtorro).
