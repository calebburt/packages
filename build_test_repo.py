#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path


OUT_DIR = Path("test")
INDEX_PATH = OUT_DIR / "packages.json"

BIN_DIRS = {"bin", "sbin"}
LIB_DIRS = {"lib", "lib64"}
SHARED_LIBRARY_RE = re.compile(r"^(?:.*\.so(?:\..*)?|.*\.dylib|.*\.dll)$", re.IGNORECASE)


def run(*args):
    subprocess.run(args, check=True)


def deb_field(deb_path: Path, field: str) -> str:
    return subprocess.check_output(
        ["dpkg-deb", "-f", str(deb_path), field],
        text=True,
    ).strip()


def dependency_names(value: str) -> list[str]:
    """Reduce Debian Depends syntax to names supported by packages.json."""
    names = []

    for group in value.split(","):
        # Keep the first alternative; this format doesn't represent alternatives
        # or Debian version constraints.
        first_alternative = group.split("|", 1)[0].strip()
        match = re.match(r"([a-z0-9][a-z0-9+.-]*)", first_alternative)
        if match:
            names.append(match.group(1))

    return sorted(set(names))


def is_bin_path(relative_path: Path) -> bool:
    parts = relative_path.parts
    return bool(parts) and (
        parts[0] in BIN_DIRS
        or (len(parts) >= 2 and parts[0] == "usr" and parts[1] in BIN_DIRS)
    )


def is_library_path(relative_path: Path) -> bool:
    parts = relative_path.parts
    return any(part in LIB_DIRS for part in parts)


def resolve_payload_target(path: Path, root: Path) -> str | None:
    """Return a target path relative to root, or None if it is broken/outside root."""
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve())
        if not resolved.is_file():
            return None
        return resolved.relative_to(root.resolve()).as_posix()
    except (OSError, RuntimeError, ValueError):
        return None


def package_links(root: Path) -> dict:
    bin_links = {}
    lib_links = {}

    for path in sorted(root.rglob("*")):
        relative_path = path.relative_to(root)

        if is_bin_path(relative_path):
            try:
                executable = path.is_file() and os.access(path, os.X_OK)
            except OSError:
                executable = False

            if executable:
                target = resolve_payload_target(path, root)
                if target:
                    # _install() places these names directly into bin_dir.
                    bin_links.setdefault(path.name, target)

        if is_library_path(relative_path) and SHARED_LIBRARY_RE.match(path.name):
            target = resolve_payload_target(path, root)
            if target:
                # _install() places these names directly into lib_dir.
                lib_links.setdefault(path.name, target)

    return {
        "bin": [
            {"name": name, "target": target}
            for name, target in sorted(bin_links.items())
        ],
        "lib": [
            {"name": name, "target": target}
            for name, target in sorted(lib_links.items())
        ],
    }


def archive_package(deb_path: Path, output_path: Path) -> dict:
    name = deb_field(deb_path, "Package")
    description_field = deb_field(deb_path, "Description")
    description = description_field.splitlines()[0] if description_field else ""

    depends_field = deb_field(deb_path, "Depends")
    deps = dependency_names(depends_field) if depends_field else []

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir) / "root"
        root.mkdir()

        # Extract payload only; Debian maintainer scripts are not run.
        run("dpkg-deb", "-x", str(deb_path.resolve()), str(root))

        info = package_links(root)
        (root / "info.json").write_text(
            json.dumps(info, indent=2) + "\n",
            encoding="utf-8",
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                # The installer recreates bin/lib links using info.json.
                # Do not store filesystem symlinks in the ZIP.
                if path.is_file() and not path.is_symlink():
                    archive.write(path, path.relative_to(root).as_posix())

    return {
        "name": name,
        "path": f"/{output_path.name}",
        "deps": deps,
        "description": description,
    }


def read_existing_index() -> list[dict]:
    if not INDEX_PATH.exists():
        return []

    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{INDEX_PATH} must contain a JSON list")
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Build .package ZIPs and packages.json from Debian packages."
    )
    parser.add_argument(
        "packages",
        nargs="*",
        help="APT package names, for example: hello tree curl",
    )
    parser.add_argument(
        "--list",
        dest="package_list",
        help="Text file containing one APT package name per line",
    )
    args = parser.parse_args()

    package_names = list(args.packages)
    if args.package_list:
        for line in Path(args.package_list).read_text(encoding="utf-8").splitlines():
            package_name = line.split("#", 1)[0].strip()
            if package_name:
                package_names.append(package_name)

    package_names = list(dict.fromkeys(package_names))
    if not package_names:
        parser.error("Provide package names or use --list FILE.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        deb_dir = Path(temp_dir) / "debs"
        deb_dir.mkdir()

        # APT resolves dependencies and downloads them without installing.
        # --reinstall also downloads explicitly requested packages that are
        # already installed.
        run(
            "sudo",
            "apt-get",
            "--yes",
            "--download-only",
            "--reinstall",
            "--no-install-recommends",
            "-o",
            f"Dir::Cache::archives={deb_dir}",
            "install",
            *package_names,
        )

        deb_files = sorted(deb_dir.glob("*.deb"))
        if not deb_files:
            raise RuntimeError("APT did not download any .deb files.")

        generated_entries = []
        for deb_path in deb_files:
            package_name = deb_field(deb_path, "Package")
            output_path = OUT_DIR / f"{package_name}.package"
            entry = archive_package(deb_path, output_path)
            generated_entries.append(entry)
            print(f"Built {output_path}")

    # Merge with the existing index so separately generated packages remain
    # available. Newly generated entries replace entries with the same name.
    entries_by_name = {
        entry["name"]: entry
        for entry in read_existing_index()
    }
    for entry in generated_entries:
        entries_by_name[entry["name"]] = entry

    entries = list(entries_by_name.values())
    available = {entry["name"] for entry in entries}

    # Keep only dependencies represented in this repo's index.
    for entry in entries:
        entry["deps"] = [
            dep for dep in entry.get("deps", [])
            if dep in available
        ]

    INDEX_PATH.write_text(
        json.dumps(entries, indent=4) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {INDEX_PATH} with {len(entries)} packages.")


if __name__ == "__main__":
    main()
