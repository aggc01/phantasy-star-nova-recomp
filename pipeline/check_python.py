"""Check that this Python can run the recomp's setup: Python 3.12 or newer, 64-bit (x64).

README step 1 runs it with the project's .venv Python before installing the packages. A 32-bit or ARM64 Python
cannot install them: some come ready-made only for x64, and pip then tries to compile them, which fails with errors
such as "Building wheel for capstone did not run successfully".
"""
import sys
import sysconfig

FIX = ('Install Python from https://www.python.org/downloads/ using the "Windows installer (64-bit)", '
       'delete the .venv folder in the project, and run step 1 again.')


def main():
    version = '.'.join(map(str, sys.version_info[:3]))
    platform = sysconfig.get_platform()
    if sys.version_info < (3, 12):
        print(f'Python {version} is too old: setup needs Python 3.12 or newer. {FIX}')
        return 1
    if platform.startswith('win') and platform != 'win-amd64':
        kind = {'win32': '32-bit', 'win-arm64': 'ARM64'}.get(platform, platform)
        print(f'This Python ({version}, {kind}) cannot install the packages setup needs: it needs the 64-bit (x64) '
              f'Python. {FIX}')
        if platform == 'win-arm64':
            print('On a Windows on ARM PC, choose the 64-bit (x64) installer, not the ARM64 one.')
        return 1
    print(f'Python {version}, {"64-bit" if sys.maxsize > 2**32 else "32-bit"}: ready.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
