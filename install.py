#! /usr/bin/env python3
import sys, os, ctypes, subprocess
from helpers import USER_BIN_DIR, USER_INSTALL_DIR, SYSTEM_BIN_DIR, SYSTEM_INSTALL_DIR, relaunch_as_admin, is_admin

if sys.platform in ["linux", "darwin"]:
    import pathlib

    def add_to_path_unix(new_dir, shell_rc=None):
        new_dir = os.path.abspath(new_dir)

        # Pick a default shell RC file
        if shell_rc is None:
            shell = os.environ.get("SHELL", "")
            if shell.endswith("zsh"):
                shell_rc = "~/.zshrc"
            else:
                shell_rc = "~/.bashrc"

        rc_path = pathlib.Path(shell_rc).expanduser()

        export_line = f"""
# Added by Python script
export PATH="$PATH:{new_dir}"
"""

        # Avoid duplicate entries
        if rc_path.exists() and new_dir in rc_path.read_text():
            return

        with rc_path.open("a") as f:
            f.write(export_line)

match sys.platform:
    case "win32":
        import winreg
        def add_to_user_path(new_dir):
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Environment",
                0,
                winreg.KEY_READ | winreg.KEY_WRITE
            )

            try:
                current_path, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current_path = ""

            paths = current_path.split(";") if current_path else []

            if new_dir not in paths:
                paths.append(new_dir)
                updated = ";".join(paths)
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, updated)

                # Notify Windows that environment variables changed
                ctypes.windll.user32.SendMessageTimeoutW(
                    0xFFFF,  # HWND_BROADCAST
                    0x1A,    # WM_SETTINGCHANGE
                    0,
                    "Environment",
                    0x0002,
                    5000
                )

            winreg.CloseKey(key)
        def add_user_path():
            add_to_user_path(USER_BIN_DIR)
        def add_to_system_path(new_dir):
            """Add a directory to the Windows machine PATH. Must run as administrator."""
            new_dir = os.path.normcase(os.path.normpath(new_dir))

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                0,
                winreg.KEY_READ | winreg.KEY_WRITE,
            ) as key:
                try:
                    current_path, value_type = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    current_path, value_type = "", winreg.REG_EXPAND_SZ

                paths = current_path.split(";") if current_path else []
                normalized = {
                    os.path.normcase(os.path.normpath(p.strip()))
                    for p in paths if p.strip()
                }

                if new_dir not in normalized:
                    paths.append(new_dir)
                    winreg.SetValueEx(key, "Path", 0, value_type, ";".join(paths))

            # Notify Windows that environment variables changed.
            ctypes.windll.user32.SendMessageTimeoutW(
                0xFFFF, 0x1A, 0, "Environment", 0x0002, 5000
            )
    case "linux":
        def add_user_path():
            add_to_path_unix(USER_BIN_DIR)
    case "darwin":
        def add_to_path_macos_launchctl(new_dir):
            new_dir = os.path.abspath(new_dir)
            current = subprocess.check_output(["launchctl", "getenv", "PATH"], text=True).strip()
            if new_dir not in current.split(":"):
                new_path = f"{current}:{new_dir}"
                subprocess.run(["launchctl", "setenv", "PATH", new_path])

        def add_user_path():
            add_to_path_unix(USER_BIN_DIR)
            add_to_path_macos_launchctl(USER_BIN_DIR)
        
    case _:
        raise NotImplementedError(f"Unknown OS '{sys.platform}'")

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def create_user_dir():
    ensure_dir(USER_INSTALL_DIR)
    ensure_dir(USER_BIN_DIR)

def system_install():
    if not is_admin():
        relaunch_as_admin()

    ensure_dir(SYSTEM_INSTALL_DIR)
    ensure_dir(SYSTEM_BIN_DIR)

    if sys.platform == "win32":
        add_to_system_path(SYSTEM_BIN_DIR)
    # /usr/local/bin is normally already on PATH on Linux and macOS.

def install():
    create_user_dir()
    add_user_path()

def check_installations():
    import os
    import sys

    def normalize(path):
        path = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))
        path = os.path.normpath(os.path.abspath(path))
        return os.path.normcase(path) if sys.platform == "win32" else path

    def configured_paths():
        if sys.platform == "win32":
            import winreg

            paths = []
            locations = [
                (winreg.HKEY_CURRENT_USER, r"Environment"),
                (
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                ),
            ]
            for root, subkey in locations:
                try:
                    with winreg.OpenKey(root, subkey) as key:
                        value, _ = winreg.QueryValueEx(key, "Path")
                        paths.extend(value.split(";"))
                except FileNotFoundError:
                    pass
            return paths

        return os.environ.get("PATH", "").split(os.pathsep)

    paths = {normalize(p) for p in configured_paths() if p.strip()}

    def done(install_dir, bin_dir):
        return (
            os.path.isdir(install_dir)
            and os.path.isdir(bin_dir)
            and normalize(bin_dir) in paths
        )

    return (
        done(USER_INSTALL_DIR, USER_BIN_DIR),
        done(SYSTEM_INSTALL_DIR, SYSTEM_BIN_DIR),
    )

if __name__ == "__main__":
    print("installing user directories...")
    install()
    if len(sys.argv) > 1 and sys.argv[1] in ["--system", "-s"]:
        print("installing system directories...")
        system_install()
    print("installing dependencies...")
    try:
        import requests
    except ImportError:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
