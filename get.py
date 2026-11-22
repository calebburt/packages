from api import Package, download_package, get_package_list
import os
import json
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from helpers import USER_INSTALL_DIR, SYSTEM_INSTALL_DIR, USER_BIN_DIR, SYSTEM_BIN_DIR

# Resolve dependencies for a given package
def _resolve_dependencies(package: Package, packages: list[Package], resolved=None, unresolved=None):
    if resolved is None:
        resolved = []
    if unresolved is None:
        unresolved = []
    unresolved.append(package)
    for dep_name in package.deps:
        dep_package = next((p for p in packages if p.name == dep_name), None)
        if dep_package is None:
            raise Exception(f"Dependency {dep_name} not found for package {package.name}")
        if dep_package not in resolved:
            if dep_package in unresolved:
                raise Exception(f"Circular dependency detected: {dep_package.name} <-> {package.name}")
            _resolve_dependencies(dep_package, packages, resolved, unresolved)
    resolved.append(package)
    unresolved.remove(package)
    return resolved

# Install a single package, without dependencies
def _install(package: Package, system: bool = False):
    install_dir = SYSTEM_INSTALL_DIR if system else USER_INSTALL_DIR
    bin_dir = SYSTEM_BIN_DIR if system else USER_BIN_DIR
    package_path = os.path.join(install_dir, package.name)
    os.makedirs(package_path, exist_ok=True)
    with TemporaryDirectory() as temp_dir:
        download_package(package, os.path.join(temp_dir, f"{package.name}.package"))
        with ZipFile(os.path.join(temp_dir, f"{package.name}.package"), 'r') as zip_ref:
            zip_ref.extractall(package_path)

    if os.path.exists(os.path.join(package_path, "info.json")):
        with open(os.path.join(package_path, "info.json"), 'r') as f:
            info = json.load(f)
            for symlink in info.get("symlinks", []):
                target = os.path.join(package_path, symlink["target"])
                name = os.path.join(bin_dir, symlink["name"])
                os.symlink(os.path.join(package_path, target), os.path.join(bin_dir, name))
    else:
        raise Exception(f"info.json not found in package {package.name}")

# Install a package along with its dependencies
def install(package: Package, system: bool = False):
    packages = get_package_list()
    resolved_packages = _resolve_dependencies(package, packages)
    for pkg in resolved_packages:
        _install(pkg, system)

packs = get_package_list()
install(packs[0], system=False)
