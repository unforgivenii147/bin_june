#!/data/data/com.termux/files/usr/bin/python

import os
import subprocess
import zipfile
from pathlib import Path

from dh import get_installed_packages


def get_wheel_package_info(wheel_file: str) -> tuple[str, str] | tuple[None, None]:
    try:
        with zipfile.ZipFile(wheel_file, "r") as zip_ref:
            for file in zip_ref.namelist():
                if file.endswith("METADATA"):
                    with zip_ref.open(file) as f:
                        metadata = f.read().decode("utf-8")
                        for line in metadata.splitlines():
                            if line.startswith("Name:"):
                                pkg_name = line.split(":")[1].strip()
                            if line.startswith("Version:"):
                                pkg_version = line.split(":")[1].strip()
                        return (pkg_name, pkg_version)
    except Exception as e:
        print(f"Error reading {wheel_file}: {e}")
    return (None, None)


def remove_wheel_file(wheel_file: str) -> None:
    try:
        Path(wheel_file).unlink()
        print(f"Removed: {wheel_file}")
    except Exception as e:
        print(f"Error removing {wheel_file}: {e}")


def main() -> None:
    whl_dir = "/sdcard/whl"
    if not Path(whl_dir).exists():
        print(f"Directory {whl_dir} does not exist.")
        return
    installed = get_installed_packages()
    for file in os.listdir(whl_dir):
        if file.endswith(".whl"):
            wheel_file = os.path.join(whl_dir, file)
            pkg_name, pkg_version = get_wheel_package_info(wheel_file)
            if pkg_name and pkg_version:
                installed_version = installed.get(pkg_name)
                if installed_version:
                    if installed_version == pkg_version:
                        print(f"{pkg_name} {pkg_version} is already installed in the venv, removing {wheel_file}")
                        remove_wheel_file(wheel_file)
                    elif installed_version > pkg_version:
                        print(f"{pkg_name} {installed_version} is newer than {pkg_version} , removing {wheel_file}")
                        remove_wheel_file(wheel_file)


if __name__ == "__main__":
    main()
