# Minecraft Server Client Setup

A one-click Windows installer that gets a friend's Minecraft client ready to join
our modded server. Choose a mod pack and click **Download**. It installs Fabric
for Minecraft 1.21.11, adds a launcher profile, and downloads the mods from this
repository.

![Python](https://img.shields.io/badge/python-3.10+-blue) ![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## Quick start

1. Download [`dist/MinecraftServerClientSetup.exe`](dist/MinecraftServerClientSetup.exe).
2. Close Minecraft and the Minecraft Launcher.
3. Run the exe, pick **Download Full** (recommended) or **Download Essential**,
   and click **Download**.
4. Open the Minecraft Launcher and play using the **Fabric 1.21.11** profile.

> **"Windows protected your PC"?** The exe isn't code-signed, because signing
> certificates cost money and this is a hobby project. Click **More info → Run
> anyway**, or build the exe from source yourself (see below).

## What it does, exactly

When you click **Download**, the installer runs these steps in order and stops
at the first error:

1. **Checks that Minecraft is closed.** It reads the list of running processes
   (names and command lines) to find the Minecraft Launcher or the game, and
   asks you to close them. It never closes anything itself.
2. **Downloads the chosen pack** from [`Mods/.Full`](Mods/.Full) or
   [`Mods/.Essentials`](Mods/.Essentials) on this repo's `main` branch into a
   temporary folder. If a download fails, nothing on your PC has changed yet.
3. **Installs Fabric if needed.** If no Fabric 1.21.11 version is in
   `%APPDATA%\.minecraft\versions`, it downloads the newest stable Fabric loader
   profile from Fabric's official servers and saves it there. That is the same
   thing the official Fabric installer does.
4. **Adds a launcher profile** named *Fabric 1.21.11*, if one doesn't already
   exist. Before editing `launcher_profiles.json` (or the Microsoft Store
   launcher's version of it), it saves a `.bak` copy.
5. **Backs up your existing mods.** Any `.jar` files in `.minecraft\mods` are
   **moved** to `mods\old_mods` (or `old_mods_<date-time>` if that folder
   already exists). Other files and folders in `mods` are left alone.
6. **Copies in the new mods** and tells you where your old ones went.

**What it doesn't do:** it doesn't ask for admin rights, collect analytics or
telemetry, run in the background, or delete any of your files.

### Network access

| Server | Why |
| --- | --- |
| `api.github.com` | List the files in the chosen mod pack folder |
| `raw.githubusercontent.com` | Download the mod jars |
| `meta.fabricmc.net` | Download the Fabric loader profile (only if Fabric isn't installed) |

GitHub allows about 60 mod-list requests per hour per internet connection
without signing in. Each click of **Download** uses one.

### Updates

The installer always downloads whatever is currently on this repo's `main`
branch. When the pack changes here, everyone gets the new version the next time
they click **Download**. They don't need a new exe.

## Mod packs

| Pack | Contents |
| --- | --- |
| **Essential** | The minimum needed to join the server: Fabric API, Fabric Language Kotlin, Cloth Config, Silk and Enchant Overhaul |
| **Full** (recommended) | Everything in Essential, plus performance, map, quality-of-life and visual mods (Sodium, Iris, Xaero's maps, JEI, AppleSkin, and more) |

Every mod belongs to its own author and keeps its own license. See
[`links.txt`](links.txt) for each mod's official page, where you can check its
author and license or download it yourself. *Enchant Overhaul* is my own mod.

## Building from source

You need Python 3.10 or newer on Windows.

```bash
python build.py
```

This installs [PyInstaller](https://pyinstaller.org) if it's missing and writes
`dist\MinecraftServerClientSetup.exe`. To run the installer without building
it, use `python minecraft_setup.py`.

**Testing safely:** set `MC_SETUP_MINECRAFT_DIR` to a scratch folder, and the
installer works on that folder instead of your real `.minecraft`.

## Project layout

```
minecraft_setup.py   The installer: GUI (tkinter) plus all install logic
build.py             Packages the installer into a single exe with PyInstaller
Mods/.Essentials/    Essential mod pack, downloaded by the installer
Mods/.Full/          Full mod pack, downloaded by the installer
links.txt            Official source page for every mod
dist/                The prebuilt exe
```
