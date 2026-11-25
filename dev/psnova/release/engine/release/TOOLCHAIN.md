# Windows toolchain and source notices


The engine carries the files needed to prepare and build Nova from supplied game data. The Nativ code comes from branch psnova, commit 5d30e61, with the current November 24 input/save/name overlay working-tree edits. Project authorship and third-party credits remain in the source files, [license](../LICENSE), and [third-party notes](../THIRD_PARTY.md).

- The Windows-hosted [LLVM-MinGW 20261006](https://github.com/mstorsjo/llvm-mingw/releases/tag/20261006) UCRT x64 package contains Clang 23.1.3 at LLVM commit 0d261d1ca552c95a8f007e061c787ac7132fbcbc. Its component terms are in toolchain/llvm-mingw/LICENSE.TXT. [LLVM source at that commit](https://github.com/llvm/llvm-project/tree/0d261d1ca552c95a8f007e061c787ac7132fbcbc).
- SDL 3.4.16 uses the x86_64 MinGW development package. Its license is in toolchain/SDL3/x86_64-w64-mingw32/share/licenses/SDL3. [SDL 3.4.16 release and source](https://github.com/libsdl-org/SDL/releases/tag/release-3.4.16).
- zlib 1.3.1 includes the headers, static library and license in toolchain/zlib. Its compilation is described in runtime/platform/win/setup-toolchain.sh. [zlib 1.3.1 source](https://github.com/madler/zlib/tree/v1.3.1).
- The in-game H.264 and AAC decoders use FFmpeg 7.1.1's static libavcodec and libavutil. The matching unmodified source archive and LGPL notices are in toolchain/ffmpeg/source and toolchain/ffmpeg/share/licenses. Its SHA-256 is 733984395e0dbbe5c046abda2dc49a5544e7e0e1e2366bba849222ae9e3a03b1. The build script is runtime/platform/win/setup-toolchain.sh. This local library build uses the script's configure options with --disable-x86asm.
- The subtitle stage runs Gyan Doshi's unmodified Windows FFmpeg 6.1.1 essentials executable as a separate process. Its SHA-256 is 04e1307997530f9cf2fe35cba2ca7e8875ca91da02f89d6c7243df819c94ad00. The publisher's original GPLv3 license and README with its exact configuration and third-party library versions are ffmpeg-LICENSE.txt and ffmpeg-UPSTREAM-README.txt. The matching FFmpeg source is ffmpeg-6.1.1.tar.xz. [Publisher's binary distribution](https://github.com/GyanD/codexffmpeg/releases/tag/6.1.1) and [upstream FFmpeg source tag](https://github.com/FFmpeg/FFmpeg/releases/tag/n6.1.1).
- The portable tools use Windows x64 CPython 3.14.5 with Tcl/Tk 8.6.15, Capstone 5.0.9, PyCryptodome 3.24.0, Pillow 12.2.0, NumPy 2.4.6 and OpenCV-Python-Headless 4.13.0.92. Python's license is in python/LICENSE.txt, Tcl/Tk terms are under python/tcl, and package licenses travel with python/Lib/site-packages. [CPython 3.14.5](https://www.python.org/downloads/release/python-3145/) and [OpenCV Python source/package build](https://github.com/opencv/opencv-python).

## Native play executable

The packaged native launcher template is release/Play Nova.exe. Setup copies it to the release folder as Phantasy Star Nova.exe after it builds the game. Its source is release/play_nova.c. From the engine folder, compile it with:

~~~powershell
& toolchain/llvm-mingw/bin/x86_64-w64-mingw32-clang.exe -O2 -Wall -Wextra -Werror -mwindows -municode -static release/play_nova.c -o "release/Play Nova.exe"
~~~

The launcher finds the completed generation from NovaData/current.txt, starts the matching host without opening a console, and uses NovaData/Player for settings, savedata0, save backups, captures and logs. Its arguments and working directory are relative to the release. The engine's portable import lays out the game filesystem in an ordinary directory to allow moving a completed install. Its game pack includes the two extra function seeds from the development library and the English release's input, performance and rendering defaults.
