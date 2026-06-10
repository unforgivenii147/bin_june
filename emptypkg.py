#!/data/data/com.termux/files/usr/bin/python

import csv
import os
import sysconfig
import tempfile
import zipfile
from pathlib import Path


def is_empty_package(dist_info_path) -> bool:
    record_file = os.path.join(dist_info_path, "RECORD")
    if not Path(record_file).is_file():
        return False
    with Path(record_file).open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            rel_path = row[0]
            abs_path = Path(os.path.join(Path(dist_info_path).parent, rel_path)).resolve()
            if not str(abs_path).startswith(str(Path(dist_info_path).resolve()) + os.sep):
                return False
    return True


def is_empty_whl(whl_path: Path) -> bool:
    """Check if a wheel file contains any files outside its .dist-info directory"""
    try:
        with zipfile.ZipFile(whl_path, "r") as zf:
            dist_info_dirs = [name for name in zf.namelist() if ".dist-info/" in name]
            if not dist_info_dirs:
                return False

            dist_info_dir = dist_info_dirs[0].split("/")[0] + "/"

            for file_name in zf.namelist():
                if file_name.endswith("/"):
                    continue

                if not file_name.startswith(dist_info_dir):
                    return False
            return True
    except zipfile.BadZipFile:
        print(f"Warning: {whl_path} is not a valid zip file")
        return False


def find_empty_packages(site_packages):
    empty = []
    for entry in os.listdir(site_packages):
        if entry.endswith(".dist-info"):
            dist_info_path = os.path.join(site_packages, entry)
            if is_empty_package(dist_info_path):
                empty.append(dist_info_path)
    return empty


def find_empty_wheels(current_dir: Path) -> list:
    """Find empty wheel files in the current directory"""
    empty_wheels = []
    for file in current_dir.glob("*.whl"):
        if is_empty_whl(file):
            empty_wheels.append(str(file))
    return empty_wheels


def main() -> None:
    site_packages = sysconfig.get_paths()["purelib"]

    empty_installed = find_empty_packages(site_packages)

    current_dir = Path.cwd()
    empty_wheels = find_empty_wheels(current_dir)

    if empty_installed:
        print("\n=== Empty installed packages (site-packages) ===")
        for pkg in empty_installed:
            print(f"  {pkg}")
    else:
        print("\nNo empty installed packages found.")

    if empty_wheels:
        print("\n=== Empty wheel files in current directory ===")
        for whl in empty_wheels:
            print(f"  {whl}")
    else:
        print("\nNo empty wheel files found in current directory.")

    if not empty_installed and not empty_wheels:
        print("\nNo empty packages or wheels found.")


if __name__ == "__main__":
    main()
