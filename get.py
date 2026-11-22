from api import Package, download_package, get_package_list
import os, stat
import json
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from helpers import USER_INSTALL_DIR, SYSTEM_INSTALL_DIR, USER_BIN_DIR, SYSTEM_BIN_DIR, USER_LIB_DIR, SYSTEM_LIB_DIR

# Resolve dependencies for a given package
def _resolve_dependencies(
    package: Package,
    packages: list[Package],
    resolved=None,
    unresolved=None,
):
    print(f"Resolving dependencies for package {package.name}...")
    if resolved is None:
        resolved = []
    if unresolved is None:
        unresolved = []

    by_name = {}
    for pkg in packages:
        if pkg.name in by_name:
            raise ValueError(f"Duplicate package name: {pkg.name}")
        by_name[pkg.name] = pkg

    done = {pkg.name for pkg in resolved}
    visiting = {pkg.name for pkg in unresolved}

    def visit(current: Package):
        if current.name in done:
            return

        # A back-edge means this dependency is part of a cycle.
        # Stop this branch; the package will be added when its visit completes.
        if current.name in visiting:
            return

        visiting.add(current.name)
        unresolved.append(current)

        for dep_name in current.deps:
            dep_package = by_name.get(dep_name)
            if dep_package is None:
                raise ValueError(
                    f"Dependency {dep_name} not found for package {current.name}"
                )
            visit(dep_package)

        unresolved.remove(current)
        visiting.remove(current.name)

        if current.name not in done:
            resolved.append(current)
            done.add(current.name)

    visit(package)
    for dep_name in package.deps:
        print("Found dependency: {}".format(dep_name))
    return resolved

# Install a single package, without dependencies
def _install(package: Package, system: bool = False):
    print(f"Installing package {package.name}...")
    install_dir = SYSTEM_INSTALL_DIR if system else USER_INSTALL_DIR
    bin_dir = SYSTEM_BIN_DIR if system else USER_BIN_DIR
    lib_dir = SYSTEM_LIB_DIR if system else USER_LIB_DIR
    package_path = os.path.join(install_dir, package.name)
    os.makedirs(package_path, exist_ok=True)
    with TemporaryDirectory() as temp_dir:
        download_package(package, os.path.join(temp_dir, f"{package.name}.package"))
        with ZipFile(os.path.join(temp_dir, f"{package.name}.package"), 'r') as zip_ref:
            zip_ref.extractall(package_path)

    if os.path.exists(os.path.join(package_path, "info.json")):
        with open(os.path.join(package_path, "info.json"), 'r') as f:
            info = json.load(f)
            for symlink in info.get("bin", []):
                target = os.path.join(package_path, symlink["target"])
                name = os.path.join(bin_dir, symlink["name"])
                if os.path.exists(os.path.join(bin_dir, name)):
                    os.remove(os.path.join(bin_dir, name))
                os.symlink(os.path.join(package_path, target), os.path.join(bin_dir, name))
                mode = os.stat(os.path.join(bin_dir, name)).st_mode
                os.chmod(os.path.join(bin_dir, name), mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            for symlink in info.get("lib", []):
                target = os.path.join(package_path, symlink["target"])
                name = os.path.join(lib_dir, symlink["name"])
                if os.path.exists(os.path.join(lib_dir, name)):
                    os.remove(os.path.join(lib_dir, name))
                os.symlink(os.path.join(package_path, target), os.path.join(lib_dir, name))
                mode = os.stat(os.path.join(lib_dir, name)).st_mode
                os.chmod(os.path.join(lib_dir, name), mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    else:
        raise Exception(f"info.json not found in package {package.name}")

# Install a package along with its dependencies
def install(package: Package, system: bool = False):
    packages = get_package_list()
    resolved_packages = _resolve_dependencies(package, packages)
    for pkg in resolved_packages:
        _install(pkg, system)

# packs = get_package_list()
# pack = None
# for p in packs:
#     if p.name == "vlc":
#         pack = p
#         break
# install(p, system=False)
