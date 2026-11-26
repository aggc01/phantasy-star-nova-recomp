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
Setup builds an **English localization** from your copy: menus, dialogue, UI art and movie subtitles, with the
Japanese subtitles burned into the movies removed (see [English](#english)). Known issues are tracked in
[docs/psnova/README.md](docs/psnova/README.md).

## What you need

| | |
| --- | --- |
| PC | 64-bit Windows 10 or 11, a GPU with a current Vulkan driver, about 12 GB of free disk space (plus room to unpack the game if it is in a ZIP) |
| Software | [Git for Windows](https://git-scm.com/download/win) (for Git Bash) and [Python](https://www.python.org/downloads/) 3.12 or newer |
| The game | *Phantasy Star Nova*, Japan, title ID `PCSG00351`: the **1.00** base game and the official **1.05** update, as PKG files or as folders copied from a Vita (`ux0:app/PCSG00351`, `ux0:patch/PCSG00351`) |
| The game's licence | `work.bin` or a `.rif` file for your copy. In a game folder copied from a Vita it is `sce_sys\package\work.bin` |
| Vita system software | `PSVUPDAT.PUP` 3.74, from [PlayStation's download page](https://www.playstation.com/en-us/support/hardware/psvita/system-software/) |
| For English | The font [Glenth Regular](https://elements.envato.com/glenth-classic-display-serif-font-9ZK6SWW) by OWPictures (`glenthregular.ttf`). It is not free to share, so it is not included: you need your own copy |

Other regions and versions are not supported. Use an unmodified copy. A copy that already carries a fan translation
works too: setup removes the fan translation and applies this one, with a few limits (see [English](#english)).

## Setup

Run these from PowerShell in the folder where you want the project, unless a step says Git Bash. Setup takes about
40 minutes in all, most of it the first build and the English; after that the game starts in seconds.

**1. Get the code, its Python packages and a folder for your game library.**

```powershell
git clone https://github.com/aggc01/phantasy-star-nova-recomp.git
cd phantasy-star-nova-recomp
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory dump
```

The `dump` folder is where the decrypted game, the build and your saves go. Create it before step 3: without it,
everything goes to a shared folder in `%LOCALAPPDATA%\ProjectNativ` on your C: drive instead.

**2. Install the compiler toolchain** (Clang for Windows, SDL3, zlib, FFmpeg's decoders, and an FFmpeg program
that re-encodes the movies for English, all at pinned versions). Open **Git Bash** in the project folder:

```bash
ATIV_WIN_TOOLCHAIN="$PWD/toolchain" bash runtime/platform/win/setup-toolchain.sh
```

This downloads about 280 MB and builds into `toolchain\` (about 1.1 GB), where the build looks for it. It takes about
5 minutes.

**3. Prepare the Vita system software.** The game needs some of Sony's system modules, which are taken from the
firmware file you downloaded:

```powershell
.\.venv\Scripts\python.exe pipeline\vitarecomp.py firmware "C:\path\to\PSVUPDAT.PUP"
```

**4. Add the English font.** Copy your `glenthregular.ttf` into `packs\PCSG00351\english\fonts\`. Git ignores
fonts there, so it is never committed. Without it the game still builds, in Japanese, and the next step tells you what
is missing.

**5. Add the game, then its update.** The first command decrypts and keeps the base game. The second adds the 1.05
update and then builds everything: import, analysis, recompilation and compilation (about 15 minutes), then the
English localization (about 15 minutes).

```powershell
.\.venv\Scripts\python.exe pipeline\vitarecomp.py add "C:\path\to\base-game.pkg" --license "C:\path\to\work.bin" --no-build
.\.venv\Scripts\python.exe pipeline\vitarecomp.py add "C:\path\to\update-1.05.pkg"
```

Instead of PKG files you can give the game folders copied from a Vita: `...\app\PCSG00351` for the base game and
`...\patch\PCSG00351` for the update. If your game is in a ZIP, unpack it first. Your files are only read. The build
prints a line starting `built` and the path of `game_host.exe`, and the English ends with
`English localization ready`.

PowerShell shows some of the tools' notes in red, for example one about `sce_sys\about\right.suprx` being skipped.
That note is expected: the file is not part of the game's code. A step has worked if it ends without an error message.

If you add the font later, or the English stopped for another reason, build only the English with:

```powershell
.\.venv\Scripts\python.exe pipeline\vitarecomp.py localize PCSG00351
```

**6. Play.** Double-click **`Play Phantasy Star Nova.bat`**.

To rebuild after changing the code, run `bash dev/psn_build_all.sh` from Git Bash. It runs the import, analyze,
recompile and build stages again and writes a log for each to `dev/psn-logs/`.

## Playing

The game opens in a 960 × 544 window, the Vita's own resolution, with the frame rate shown in the top-left corner
(**F1** cycles or hides it). Press **F10** at any time for the in-game menu, where you can raise the resolution (up to
6×) and turn on 60 FPS. Both are saved for next time. 4× and above need a strong GPU.

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

The English localization covers menus, dialogue, names, UI art and movie subtitles, with some lines still in
Japanese. It lives in [`packs/PCSG00351/english/`](packs/PCSG00351/english/localize.py) as recipes: the English text,
instructions for redrawing each UI image, and subtitle timings, each tied to the SHA-256 of the original file it
applies to. No game file is in the repository. On your PC, step 5 (or `vitarecomp localize PCSG00351`):

1. checks that your game and update archives are the unmodified Japanese originals;
2. writes the English messages and redrawn UI images into a copy of the update's archive;
3. removes the Japanese subtitles burned into the story movies, frame by frame, and draws English subtitles in their
   place;
4. puts both archives in `dump\decrypted\PCSG00351\lang\en` and makes English the starting language.

Your original archives stay untouched. **F10 → Game → Language** switches between English and the original Japanese
at any time. A later run only rebuilds what changed.

If your copy already carries a fan translation (such as Arks-Layer's English patch, often found merged into a
"v1.05 English" copy), step 5 removes it and builds this English in its place:

- the update's archive is rebuilt from the untouched base game, so none of the fan's text is left;
- the story movies, which the fan translation re-encoded with its English under the Japanese line, have both lines
  erased before the English subtitles are drawn;
- the opening warning screen, which the fan translation turns into its credits, is drawn again in English.

A fan copy no longer holds everything the original had. One UI texture is gone, so some screens can show noise.
Eight lines that this English leaves untranslated show the base game's older Japanese wording. The story movies
start from the fan's lower-quality re-encode. Step 5 says so when it runs. For the full result, use an unmodified
Japanese copy.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| `no Windows toolchain at …` | Run step 2 again, and check that `toolchain\llvm-mingw` exists. |
| The firmware or the game went to `%LOCALAPPDATA%\ProjectNativ` | The `dump` folder was missing. Create it (step 1) and run steps 3 and 5 again. |
| `Python not found` when starting the game | Create `.venv` as in step 1. |
| The update is refused or asks for a licence | Add the base game first (step 5), with its `work.bin` or `.rif`. |
| `English localization: … needs the Glenth Regular font` | Copy `glenthregular.ttf` into `packs\PCSG00351\english\fonts\` (step 4), then run `vitarecomp localize PCSG00351`. |
| `English localization: this copy carries a fan translation` | Expected with a fan-translated copy: the fan translation is removed and this English applied, with the limits the message lists. For the full result, add an unmodified copy (step 5). |
| `… is not the original Japanese base game archive` | The base game itself is modified. Add an unmodified copy (step 5). |
| The game is in Japanese after setup | Check the end of step 5's output for a line starting `English localization`, which says what stopped it. |
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
| `packs/PCSG00351/english/` | The English localization: text, UI and subtitle recipes, and the scripts that build them |
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

The English text started from Arks-Layer's fan translation of *Phantasy Star Nova* and was revised and extended for
this project. Glenth Regular is by OWPictures. The movie subtitles are encoded with
[FFmpeg](https://ffmpeg.org/), using Gyan Doshi's Windows build.
