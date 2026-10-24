"""Minecraft Server Client Setup.

A small GUI installer that makes sure Fabric for Minecraft 1.21.11 is installed
(with a launcher profile), downloads the chosen mod pack from GitHub, and puts
it in the user's .minecraft\\mods folder, moving any existing mod jars into
old_mods first.
"""

import datetime
import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

APP_TITLE = "Minecraft Server Client Setup"
MC_VERSION = "1.21.11"
PROFILE_KEY = f"fabric-loader-{MC_VERSION}"
PROFILE_NAME = f"Fabric {MC_VERSION}"
FABRIC_META = "https://meta.fabricmc.net/v2/versions/loader"

GITHUB_REPO = "leevigarrison-lgtm/RequiredMods"
GITHUB_BRANCH = "main"
REPO_URL = f"https://github.com/{GITHUB_REPO}"

# Dropdown label -> folder inside Mods/ in the GitHub repo.
PACKS = {
    "Download Full": ".Full",
    "Download Essential": ".Essentials",
}

LAUNCHER_EXES = {"minecraftlauncher.exe", "minecraft.exe"}
JAVA_EXES = {"java.exe", "javaw.exe"}
# Substrings of a Java command line that mean it is the Minecraft client.
GAME_MARKERS = ("net.minecraft.client", "knotclient", "--gamedir")
PROFILE_FILES = ("launcher_profiles.json", "launcher_profiles_microsoft_store.json")

FABRIC_DIR_RE = re.compile(rf"^fabric-loader-(.+)-{re.escape(MC_VERSION)}$")


class SetupError(Exception):
    """A failure whose message is shown to the user as-is."""


# ---------------------------------------------------------------- paths

def minecraft_dir() -> Path:
    # MC_SETUP_MINECRAFT_DIR lets the installer be tested against a scratch folder.
    override = os.environ.get("MC_SETUP_MINECRAFT_DIR")
    if override:
        return Path(override)
    return Path(os.environ["APPDATA"]) / ".minecraft"


# ---------------------------------------------------------------- processes

def _run_hidden(args):
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _list_processes():
    """Return [{"Name": ..., "CommandLine": ...}] for running processes."""
    try:
        result = _run_hidden([
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "Get-CimInstance Win32_Process | Select-Object Name, CommandLine"
            " | ConvertTo-Json -Compress",
        ])
        processes = json.loads(result.stdout or "[]")
        return [processes] if isinstance(processes, dict) else processes
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    # Fallback without command lines: only the launcher can be detected.
    try:
        result = _run_hidden(["tasklist", "/FO", "CSV", "/NH"])
    except (OSError, subprocess.SubprocessError):
        return []
    return [{"Name": line.split('","')[0].strip('"'), "CommandLine": ""}
            for line in result.stdout.splitlines() if line]


def running_minecraft() -> list:
    """Names of Minecraft launcher/game processes that are currently open."""
    found = set()
    for proc in _list_processes():
        name = (proc.get("Name") or "").lower()
        cmd = (proc.get("CommandLine") or "").lower()
        if name in LAUNCHER_EXES:
            found.add("the Minecraft Launcher")
        elif name in JAVA_EXES and any(marker in cmd for marker in GAME_MARKERS):
            found.add("Minecraft")
    return sorted(found)


# ---------------------------------------------------------------- json helpers

def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise SetupError(f"Could not read {path}:\n\n{exc}") from exc


def _write_json(path: Path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _open_url(url: str):
    request = urllib.request.Request(
        url, headers={"User-Agent": "MinecraftServerClientSetup/1.0"})
    return urllib.request.urlopen(request, timeout=30)


def _download_error(what: str, url: str, exc: Exception) -> SetupError:
    if isinstance(exc, urllib.error.HTTPError) and exc.code in (403, 429):
        return SetupError(
            f"Could not download {what}: the server is rate limiting requests.\n\n"
            "Wait a while (up to an hour) and try again.")
    return SetupError(
        f"Could not download {what} from:\n{url}\n\n"
        f"Check your internet connection and try again.\n\n{exc}")


def _http_json(url: str, what: str):
    try:
        with _open_url(url) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise _download_error(what, url, exc) from exc


def _download_file(url: str, target: Path, what: str):
    try:
        with _open_url(url) as response, open(target, "wb") as out:
            shutil.copyfileobj(response, out)
    except OSError as exc:
        raise _download_error(what, url, exc) from exc


def _version_key(version: str):
    return tuple((0, int(part), "") if part.isdigit() else (1, 0, part)
                 for part in re.split(r"[.+-]", version))


# ---------------------------------------------------------------- fabric

def installed_fabric_versions(mc_dir: Path) -> list:
    """Installed Fabric version ids for MC_VERSION, oldest loader first."""
    versions_dir = mc_dir / "versions"
    found = []
    if versions_dir.is_dir():
        for entry in versions_dir.iterdir():
            match = FABRIC_DIR_RE.match(entry.name)
            if match and (entry / f"{entry.name}.json").is_file():
                found.append((match.group(1), entry.name))
    found.sort(key=lambda item: _version_key(item[0]))
    return [version_id for _, version_id in found]


def install_fabric(mc_dir: Path) -> str:
    """Install the newest stable Fabric loader for MC_VERSION; return its version id.

    This mirrors what the official Fabric installer does: it writes the profile
    json from Fabric's meta server into versions\\<id>\\. The launcher downloads
    vanilla Minecraft and Fabric's libraries itself on first launch.
    """
    loaders = _http_json(f"{FABRIC_META}/{MC_VERSION}", "Fabric")
    stable = [entry["loader"]["version"] for entry in loaders
              if entry.get("loader", {}).get("stable")]
    if not stable:
        raise SetupError(f"Fabric has no stable loader for Minecraft {MC_VERSION}.")
    loader = max(stable, key=_version_key)

    profile = _http_json(f"{FABRIC_META}/{MC_VERSION}/{loader}/profile/json", "Fabric")
    version_id = profile.get("id") or f"fabric-loader-{loader}-{MC_VERSION}"
    version_dir = mc_dir / "versions" / version_id
    try:
        version_dir.mkdir(parents=True, exist_ok=True)
        _write_json(version_dir / f"{version_id}.json", profile)
        # The official installer leaves an empty jar beside the json too.
        (version_dir / f"{version_id}.jar").touch()
    except OSError as exc:
        raise SetupError(f"Could not install Fabric into {version_dir}:\n\n{exc}") from exc
    return version_id


def ensure_profile(mc_dir: Path, version_ids: list) -> bool:
    """Make sure a launcher profile uses an installed Fabric version.

    Returns True if a profile had to be created.
    """
    paths = [mc_dir / name for name in PROFILE_FILES if (mc_dir / name).is_file()]
    if not paths:
        paths = [mc_dir / PROFILE_FILES[0]]

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    created = False
    for path in paths:
        data = _read_json(path) if path.exists() else {"profiles": {}, "version": 3}
        profiles = data.setdefault("profiles", {})
        if any(isinstance(p, dict) and p.get("lastVersionId") in version_ids
               for p in profiles.values()):
            continue
        try:
            if path.exists():
                shutil.copy2(path, path.with_name(path.name + ".bak"))
            profiles[PROFILE_KEY] = {
                "name": PROFILE_NAME,
                "type": "custom",
                "created": now,
                "lastUsed": now,
                "icon": "Furnace",
                "lastVersionId": version_ids[-1],
            }
            _write_json(path, data)
        except OSError as exc:
            raise SetupError(f"Could not update {path}:\n\n{exc}") from exc
        created = True
    return created


# ---------------------------------------------------------------- mods

def download_pack(pack_label: str, dest: Path) -> Path:
    """Download every file in Mods/<pack> of the GitHub repo into dest."""
    folder = PACKS[pack_label]
    listing = _http_json(
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/Mods/{folder}"
        f"?ref={GITHUB_BRANCH}",
        "the mod list")
    files = [entry for entry in (listing if isinstance(listing, list) else [])
             if entry.get("type") == "file" and entry.get("download_url")]
    if not files:
        raise SetupError(f"No mods were found on GitHub in Mods/{folder}:\n{REPO_URL}")

    for entry in files:
        target = dest / entry["name"]
        _download_file(entry["download_url"], target, entry["name"])
        if entry.get("size") is not None and target.stat().st_size != entry["size"]:
            raise SetupError(f"{entry['name']} didn't download completely. Please try again.")
    return dest


def install_mods(mc_dir: Path, source: Path):
    """Move existing top-level jars into old_mods, then copy the pack in.

    Returns (number of items copied, backup folder or None).
    """
    mods_dir = mc_dir / "mods"
    try:
        mods_dir.mkdir(parents=True, exist_ok=True)
        old_jars = [p for p in mods_dir.iterdir()
                    if p.is_file() and p.suffix.lower() == ".jar"]
        backup_dir = None
        if old_jars:
            backup_dir = mods_dir / "old_mods"
            if backup_dir.exists():
                stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                backup_dir = mods_dir / f"old_mods_{stamp}"
            backup_dir.mkdir()
            for jar in old_jars:
                shutil.move(str(jar), str(backup_dir / jar.name))

        copied = 0
        for item in source.iterdir():
            target = mods_dir / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
            copied += 1
    except OSError as exc:
        raise SetupError(
            f"Could not copy mods into {mods_dir}:\n\n{exc}\n\n"
            "Make sure Minecraft is closed and try again."
        ) from exc
    return copied, backup_dir


# ---------------------------------------------------------------- orchestration

def run_setup(pack_label: str, report=lambda message: None) -> str:
    """Do the whole install and return a summary for the user."""
    mc_dir = minecraft_dir()
    if not mc_dir.is_dir():
        raise SetupError(
            f"Minecraft doesn't look installed for this user (no folder at {mc_dir}).\n\n"
            "Install the Minecraft Launcher and open it once, then try again."
        )

    # Download everything first so a failed download leaves Minecraft untouched.
    with tempfile.TemporaryDirectory(prefix="mc-setup-") as staging:
        report("Downloading mods from GitHub...")
        source = download_pack(pack_label, Path(staging))

        report("Checking for Fabric...")
        lines = []
        versions = installed_fabric_versions(mc_dir)
        if versions:
            lines.append(f"Fabric for Minecraft {MC_VERSION} is already installed.")
        else:
            report(f"Installing Fabric for Minecraft {MC_VERSION}...")
            version_id = install_fabric(mc_dir)
            versions = installed_fabric_versions(mc_dir)
            lines.append(f"Installed Fabric ({version_id}).")

        report("Updating launcher profile...")
        if ensure_profile(mc_dir, versions):
            lines.append(f'Created the "{PROFILE_NAME}" profile in the Minecraft Launcher.')

        report("Copying mods...")
        copied, backup_dir = install_mods(mc_dir, source)
    lines.append(f"Copied {copied} mods into:\n{mc_dir / 'mods'}")
    if backup_dir:
        lines.append(f"Your previous mods were moved to:\n{backup_dir}")

    lines.append(f'Open the Minecraft Launcher and play using the "{PROFILE_NAME}" profile.')
    return "\n\n".join(lines)


# ---------------------------------------------------------------- gui

class SetupApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.events = queue.Queue()

        root.title(APP_TITLE)
        root.resizable(False, False)

        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=APP_TITLE, font=("Segoe UI", 16, "bold")).pack(pady=(0, 18))

        ttk.Label(frame, text="Choose what to download:").pack(anchor="w")
        self.pack_var = tk.StringVar(value=next(iter(PACKS)))
        self.combo = ttk.Combobox(frame, textvariable=self.pack_var, values=list(PACKS),
                                  state="readonly", width=36)
        self.combo.pack(fill="x", pady=(4, 16))

        self.button = ttk.Button(frame, text="Download", command=self.on_download)
        self.button.pack(fill="x", ipady=4)

        link_row = ttk.Frame(frame)
        link_row.pack(anchor="w", pady=(16, 0))
        ttk.Label(link_row, text="Open Source Code:").pack(side="left")
        link = ttk.Label(link_row, text=REPO_URL.removeprefix("https://"),
                         foreground="#0066cc", cursor="hand2",
                         font=("Segoe UI", 9, "underline"))
        link.pack(side="left", padx=(4, 0))
        link.bind("<Button-1>", lambda _event: webbrowser.open(REPO_URL))

        root.update_idletasks()
        x = (root.winfo_screenwidth() - root.winfo_width()) // 2
        y = (root.winfo_screenheight() - root.winfo_height()) // 3
        root.geometry(f"+{x}+{y}")

    def set_busy(self, busy: bool):
        self.button.configure(state="disabled" if busy else "normal",
                              text="Downloading..." if busy else "Download")
        self.combo.configure(state="disabled" if busy else "readonly")

    def on_download(self):
        pack_label = self.pack_var.get()
        self.set_busy(True)
        self.root.update()
        while True:
            running = running_minecraft()
            if not running:
                break
            if not messagebox.askretrycancel(
                    APP_TITLE,
                    f"Please close {' and '.join(running)} before continuing.\n\n"
                    "Click Retry once it's closed."):
                self.set_busy(False)
                return

        threading.Thread(target=self.worker, args=(pack_label,), daemon=True).start()
        self.root.after(100, self.poll)

    def worker(self, pack_label: str):
        try:
            self.events.put(("done", run_setup(pack_label)))
        except SetupError as exc:
            self.events.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001 - always tell the user something
            self.events.put(("error", f"Unexpected error:\n\n{exc!r}"))

    def poll(self):
        try:
            kind, message = self.events.get_nowait()
        except queue.Empty:
            self.root.after(100, self.poll)
            return
        self.set_busy(False)
        if kind == "done":
            messagebox.showinfo(APP_TITLE, message)
        else:
            messagebox.showerror(APP_TITLE, message)


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    SetupApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
