import sys, os, ctypes, subprocess

match sys.platform:
    case "win32":
        USER_INSTALL_DIR = os.path.expanduser("~/AppData/Local/Packages/")
        USER_BIN_DIR = os.path.expanduser("~/.bin/")
        USER_LIB_DIR = os.path.expanduser("~/AppData/Local/Packages/lib/")

        SYSTEM_INSTALL_DIR = "C:/Program Files/"
        SYSTEM_BIN_DIR = "C:/bin/"
        SYSTEM_LIB_DIR = "C:/Program Files/Packages/lib/"

        USER_DATA_DIR = os.path.expanduser("~/AppData/Local/packages/")
        SYSTEM_DATA_DIR = "C:/Program Files/packages/"

    case "linux":
        USER_INSTALL_DIR = os.path.expanduser("~/.packages/")
        USER_BIN_DIR = os.path.expanduser("~/.local/bin/")
        USER_LIB_DIR = os.path.expanduser("~/.local/lib/packages/")

        SYSTEM_INSTALL_DIR = "/packages/"
        SYSTEM_BIN_DIR = "/usr/local/bin/"
        SYSTEM_LIB_DIR = "/usr/local/lib/packages/"

        USER_DATA_DIR = "~/.local/share/packages/"
        SYSTEM_DATA_DIR = "/var/lib/packages"
    case "darwin":
        USER_INSTALL_DIR = os.path.expanduser("~/.packages/")
        USER_BIN_DIR = os.path.expanduser("~/.local/bin/")
        USER_LIB_DIR = os.path.expanduser("~/Library/Packages/lib/")

        SYSTEM_INSTALL_DIR = "/packages/"
        SYSTEM_BIN_DIR = "/usr/local/bin/"
        SYSTEM_LIB_DIR = "/usr/local/lib/packages/"

        USER_DATA_DIR = "~/Library/Application Support/packages/"
        SYSTEM_DATA_DIR = "/Library/Application Support/packages/"
    case _:
        raise NotImplementedError(f"Unknown OS '{sys.platform}'")

def is_admin():
    if sys.platform == "win32":
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    return os.geteuid() == 0

def relaunch_as_admin():
    if sys.platform == "win32":
        # Relaunch this script through the Windows UAC prompt.
        params = subprocess.list2cmdline(
            [os.path.abspath(__file__), *sys.argv[1:]]
        )
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        if result <= 32:
            raise RuntimeError("Administrator access was declined or failed.")
        raise SystemExit(0)

    print(f"Run this command with administrator privileges:\n  sudo {sys.executable} {sys.argv[0]}")
    raise SystemExit(1)
