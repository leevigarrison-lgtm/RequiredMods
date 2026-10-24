"""Build MinecraftServerClientSetup.exe with PyInstaller.

Usage:  python build.py

Output: dist\\MinecraftServerClientSetup.exe with a copy of the Mods folder
beside it. The exe reads its mod packs from that Mods folder at runtime, so
ship the two together.
"""

import shutil
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

    mods_out = dist / "Mods"
    if mods_out.exists():
        shutil.rmtree(mods_out)
    shutil.copytree(ROOT / "Mods", mods_out)

    print(f"\nBuilt {dist / (NAME + '.exe')}")
    print(f"Copied mod packs to {mods_out}")


if __name__ == "__main__":
    main()
