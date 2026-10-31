#!/usr/bin/env python3
"""Install a per-user desktop launcher and app copy. No sudo or pip needed."""
import argparse
import os
from pathlib import Path
import shutil
import sys

APP_ID = "asiahorse-umbra"
APP_FILES = ("asiahorse.py", "asiahorse_gui.py", "effects.py", "sensors.py", "LICENSE")


def desktop_quote(value):
    """Escape an Exec argument for the desktop-entry format (not a shell)."""
    if any(c in value for c in "\n\r\x00"):
        raise ValueError("Desktop launcher paths cannot contain line breaks or NUL")
    value = value.replace("%", "%%")
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\' + char)
    # Backslashes themselves need escaping in desktop-entry string values.
    return '"' + value.replace('\\', '\\\\') + '"'


def install(source, data_home, python):
    app = data_home / APP_ID
    applications = data_home / "applications"
    icons = data_home / "icons/hicolor/scalable/apps"
    # Check the complete source before changing an existing install.
    for name in (*APP_FILES, "assets/asiahorse-umbra.svg"):
        if not (source / name).is_file():
            raise FileNotFoundError(f"Missing source file: {name}. Extract the complete download first.")
    command = f"{desktop_quote(str(python))} {desktop_quote(str(app / 'asiahorse_gui.py'))}"
    for directory in (app, applications, icons):
        directory.mkdir(parents=True, exist_ok=True)
    for name in APP_FILES:
        if (source / name).resolve() != (app / name).resolve():
            shutil.copy2(source / name, app / name)
    shutil.copy2(source / "assets/asiahorse-umbra.svg", icons / f"{APP_ID}.svg")
    launcher = applications / f"{APP_ID}.desktop"
    launcher.write_text(
        "[Desktop Entry]\nType=Application\nVersion=1.0\n"
        "Name=AsiaHorse Umbra\nComment=RGB lighting effects and system sensors\n"
        f"Exec={command}\nIcon={APP_ID}\nTerminal=false\n"
        "Categories=Utility;\nKeywords=RGB;LED;Umbra;AsiaHorse;\n",
        encoding="utf-8",
    )
    return launcher


def uninstall(data_home):
    # Remove only files this installer owns; keep any unrelated files.
    for path in (data_home / "applications" / f"{APP_ID}.desktop",
                 data_home / "icons/hicolor/scalable/apps" / f"{APP_ID}.svg"):
        path.unlink(missing_ok=True)
    app = data_home / APP_ID
    for name in APP_FILES:
        (app / name).unlink(missing_ok=True)
    try:
        app.rmdir()
    except (FileNotFoundError, OSError):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true", help="Remove the per-user installation")
    parser.add_argument("--data-home", type=Path,
                        default=Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share"),
                        help="Desktop data directory (default: XDG_DATA_HOME or ~/.local/share)")
    args = parser.parse_args()
    data_home = args.data_home.expanduser()
    if not data_home.is_absolute():
        parser.error("--data-home must be an absolute path")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        parser.error("Run as your regular desktop user, without sudo")
    try:
        if args.uninstall:
            uninstall(data_home)
            print("Removed the AsiaHorse Umbra menu launcher and installed app files.")
        else:
            launcher = install(Path(__file__).resolve().parent, data_home, Path(sys.executable).resolve())
            print(f"Installed: {launcher}\nOpen your application menu and search for AsiaHorse Umbra.\n"
                  "If it does not appear immediately, sign out and back in.\n"
                  "The app runs without a terminal. Close the app to stop animations.")
    except (OSError, ValueError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
