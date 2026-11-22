#!/usr/bin/env python3

import ctypes
import os
import pathlib
import subprocess
import sys

from helpers import (
    USER_BIN_DIR,
    USER_INSTALL_DIR,
    SYSTEM_BIN_DIR,
    SYSTEM_INSTALL_DIR,
    USER_LIB_DIR,
    SYSTEM_LIB_DIR,
    relaunch_as_admin,
    is_admin,
)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def create_user_dir():
    ensure_dir(USER_INSTALL_DIR)
    ensure_dir(USER_BIN_DIR)
    ensure_dir(USER_LIB_DIR)


def add_unix_path(rc_path, variable, new_dir):
    """Add a directory to a shell environment variable in an rc file."""
    new_dir = os.path.abspath(os.path.expanduser(new_dir))
    rc_path = pathlib.Path(rc_path).expanduser()
    rc_path.parent.mkdir(parents=True, exist_ok=True)

    # Add the directory only if it is not already present.
    line = (
        f'case ":${{{variable}:-}}:" in '
        f'*":{new_dir}:"*) ;; '
        f'*) export {variable}="{new_dir}${{{variable}:+:${variable}}}" ;; '
        f'esac'
    )
    marker = f"# Added by Python package manager: {variable} {new_dir}"

    existing = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
    if marker in existing:
        return

    with rc_path.open("a", encoding="utf-8") as file:
        file.write(f"\n{marker}\n{line}\n")


def add_to_path_unix(new_dir, shell_rc=None):
    if shell_rc is None:
        shell = os.environ.get("SHELL", "")
        shell_rc = "~/.zshrc" if shell.endswith("zsh") else "~/.bashrc"

    add_unix_path(shell_rc, "PATH", new_dir)


def add_to_user_library_env(new_dir):
    if sys.platform == "darwin":
        variable = "DYLD_LIBRARY_PATH"
    else:
        variable = "LD_LIBRARY_PATH"

    shell = os.environ.get("SHELL", "")
    rc_path = "~/.zshrc" if shell.endswith("zsh") else "~/.bashrc"
    add_unix_path(rc_path, variable, new_dir)


def add_to_launchctl_env(variable, new_dir):
    """Set a variable for processes launched from the current macOS GUI session."""
    new_dir = os.path.abspath(os.path.expanduser(new_dir))

    try:
        current = subprocess.check_output(
            ["launchctl", "getenv", variable],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        current = ""

    entries = [entry for entry in current.split(":") if entry]
    if new_dir not in entries:
        entries.insert(0, new_dir)

    subprocess.run(
        ["launchctl", "setenv", variable, ":".join(entries)],
        check=True,
    )


def add_to_windows_path(registry_root, subkey, new_dir):
    import winreg

    new_dir = os.path.normcase(os.path.normpath(os.path.expandvars(new_dir)))

    with winreg.OpenKey(
        registry_root,
        subkey,
        0,
        winreg.KEY_READ | winreg.KEY_WRITE,
    ) as key:
        try:
            current_path, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path, value_type = "", winreg.REG_EXPAND_SZ

        paths = [p.strip() for p in current_path.split(";") if p.strip()]
        normalized_paths = {
            os.path.normcase(os.path.normpath(os.path.expandvars(p)))
            for p in paths
        }

        if new_dir not in normalized_paths:
            paths.append(new_dir)
            winreg.SetValueEx(key, "Path", 0, value_type, ";".join(paths))


def notify_windows_environment_changed():
    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF,  # HWND_BROADCAST
        0x1A,    # WM_SETTINGCHANGE
        0,
        "Environment",
        0x0002,  # SMTO_ABORTIFHUNG
        5000,
    )


def add_user_paths_windows():
    import winreg

    add_to_windows_path(winreg.HKEY_CURRENT_USER, "Environment", USER_BIN_DIR)
    add_to_windows_path(winreg.HKEY_CURRENT_USER, "Environment", USER_LIB_DIR)
    notify_windows_environment_changed()


def add_system_paths_windows():
    import winreg

    key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    add_to_windows_path(winreg.HKEY_LOCAL_MACHINE, key_path, SYSTEM_BIN_DIR)
    add_to_windows_path(winreg.HKEY_LOCAL_MACHINE, key_path, SYSTEM_LIB_DIR)
    notify_windows_environment_changed()


def add_system_library_path_linux():
    """Register the system library directory with the Linux dynamic loader."""
    library_dir = os.path.abspath(SYSTEM_LIB_DIR)
    config_dir = pathlib.Path("/etc/ld.so.conf.d")
    config_file = config_dir / "packages-manager.conf"

    config_dir.mkdir(parents=True, exist_ok=True)
    config_file.write_text(library_dir + "\n", encoding="utf-8")
    subprocess.run(["ldconfig"], check=True)


def add_system_library_env_macos():
    """Set dyld library paths for shells launched system-wide."""
    library_dir = os.path.abspath(SYSTEM_LIB_DIR)

    # Login shells read /etc/profile (bash) or /etc/zprofile (zsh).
    for rc_file in ("/etc/profile", "/etc/zprofile"):
        add_unix_path(rc_file, "DYLD_LIBRARY_PATH", library_dir)

    # Set the variable for apps launched by the current launchd session too.
    add_to_launchctl_env("DYLD_LIBRARY_PATH", library_dir)


def add_user_path():
    if sys.platform == "win32":
        add_user_paths_windows()

    elif sys.platform in ("linux", "darwin"):
        add_to_path_unix(USER_BIN_DIR)
        add_to_user_library_env(USER_LIB_DIR)

        if sys.platform == "darwin":
            add_to_launchctl_env("PATH", USER_BIN_DIR)
            add_to_launchctl_env("DYLD_LIBRARY_PATH", USER_LIB_DIR)

    else:
        raise NotImplementedError(f"Unsupported platform: {sys.platform}")


def install():
    create_user_dir()
    add_user_path()


def system_install():
    if not is_admin():
        relaunch_as_admin()

    ensure_dir(SYSTEM_INSTALL_DIR)
    ensure_dir(SYSTEM_BIN_DIR)
    ensure_dir(SYSTEM_LIB_DIR)

    if sys.platform == "win32":
        add_system_paths_windows()

    elif sys.platform == "linux":
        # /usr/local/bin is normally already on PATH.
        add_system_library_path_linux()

    elif sys.platform == "darwin":
        # /usr/local/bin is normally already on PATH.
        add_system_library_env_macos()

    else:
        raise NotImplementedError(f"Unsupported platform: {sys.platform}")


def normalize_path(path):
    path = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))
    path = os.path.normpath(os.path.abspath(path))
    return os.path.normcase(path) if sys.platform == "win32" else path


def configured_paths_windows():
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


def check_installations():
    if sys.platform == "win32":
        paths = configured_paths_windows()
    else:
        paths = os.environ.get("PATH", "").split(os.pathsep)

    normalized_paths = {
        normalize_path(path)
        for path in paths
        if path.strip()
    }

    def done(install_dir, bin_dir):
        return (
            os.path.isdir(install_dir)
            and os.path.isdir(bin_dir)
            and normalize_path(bin_dir) in normalized_paths
        )

    return (
        done(USER_INSTALL_DIR, USER_BIN_DIR),
        done(SYSTEM_INSTALL_DIR, SYSTEM_BIN_DIR),
    )


if __name__ == "__main__":
    print("Installing user directories and paths...")
    install()

    if len(sys.argv) > 1 and sys.argv[1] in ("--system", "-s"):
        print("Installing system directories and paths...")
        system_install()

    print("Checking Python dependencies...")
    try:
        import requests  # noqa: F401
    except ImportError:
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            "requirements.txt",
        ])
