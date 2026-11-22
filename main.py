from install import check_installations

if not check_installations[0]:
    print("Please install the required directories with install.py.")
    exit()
if not check_installations[1]:
    print("Warning: not installed for system. On posix, run sudo ./install.py, on windows, run install.py and click \"yes\"")
