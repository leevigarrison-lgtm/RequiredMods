"""Build MinecraftServerClientSetup.exe with PyInstaller.

Usage:  python build.py

Output: dist\\MinecraftServerClientSetup.exe. The exe downloads its mod packs
from the GitHub repo at runtime, so it can be shared on its own.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "MinecraftServerClientSetup"


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found, installing it...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    dist = ROOT / "dist"
    build = ROOT / "build"
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", NAME,
        "--distpath", str(dist),
        "--workpath", str(build),
        "--specpath", str(build),
        str(ROOT / "minecraft_setup.py"),
    ])

    print(f"\nBuilt {dist / (NAME + '.exe')}")


if __name__ == "__main__":
    main()
