from install import check_installations
import get
import sys

if not check_installations[0]:
    print("Please install the required directories with install.py.")
    exit()
if not check_installations[1]:
    print("Warning: not installed for system. On posix, run sudo ./install.py, on windows, run install.py and click \"yes\"")

if len(sys.argv) < 2:
    print("Usage: python main.py command ...")
    exit()

match sys.argv[1]:
    case "install":
        if len(sys.argv) < 3:
            print("Usage: python main.py install <package_name>")
            exit()
        package_name = sys.argv[2]
        packages = get.get_package_list()
        package = next((p for p in packages if p.name == package_name), None)
        if not package:
            print(f"Package '{package_name}' not found.")
            exit()
        get.install(package, system=False)
    case "list":
        packages = get.get_package_list()
        for p in packages:
            print(p.name)
    case "install-system":
        if len(sys.argv) < 3:
            print("Usage: python main.py install-system <package_name>")
            exit()
        package_name = sys.argv[2]
        packages = get.get_package_list()
        package = next((p for p in packages if p.name == package_name), None)
        if not package:
            print(f"Package '{package_name}' not found.")
            exit()
        get.install(package, system=True)
    # case "remove":
    #     if len(sys.argv) < 3:
    #         print("Usage: python main.py remove <package_name>")
    #         exit()
    #     package_name = sys.argv[2]
    #     get.remove(package_name, system=False)
    # case "remove-system":
    #     if len(sys.argv) < 3:
    #         print("Usage: python main.py remove-system <package_name>")
    #         exit()
    #     package_name = sys.argv[2]
    #     get.remove(package_name, system=True)
    case _:
        print(f"Unknown command: {sys.argv[1]}")
        exit()
