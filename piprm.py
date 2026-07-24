#!/data/data/com.termux/files/home/.local/bin/python


from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rapidfuzz import fuzz

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def get_file_age(path: str | Path, str_mode: bool = False) -> float | str:
    from os import stat as os_stat
    from time import time as time_time

    path = Path(path)
    current_time = time_time()
    file_stat = os_stat(path)
    file_creation_time = file_stat.st_ctime
    age = current_time - file_creation_time
    int_age = int(age)
    if not str_mode:
        if not path.exists():
            return 0.0
        if not path.is_file():
            return -1.0
        return age
    if int_age < 0:
        return "0 sec"
    units = [
        ("y", 365 * 24 * 60 * 60),
        ("m", 30 * 24 * 60 * 60),
        ("d", 24 * 60 * 60),
        ("h", 60 * 60),
        ("min", 60),
        ("sec", 1),
    ]
    parts = []
    for name, seconds_per_unit in units:
        value, int_age = divmod(int_age, seconds_per_unit)
        if value:
            parts.append(f"{value} {name}")
    return ", ".join(parts) if parts else "0 sec"


def get_installed_pkgs():
    packages = []
    pip_freeze_path = Path("/sdcard/data/pip.freeze")
    file_age = get_file_age(pip_freeze_path)
    if file_age < 60 * 60 * 24:
        lines = pip_freeze_path.read_text(encoding="utf8").splitlines(keepends=False)
        for line in lines:
            if not line.startswith("#") and "==" in line:
                name, _ = line.split("==", 1)
                packages.append(name)
        return packages
    from importlib.metadata import distributions

    for dist in distributions():
        meta = dist.metadata
        name = meta.get("Name") or meta.get("name")
        if not name:
            continue
        name = name.strip()
        packages.append(name)
    return packages


get_ipkgs = get_installed_pkgs

PIP_LIST_FILE = "/sdcard/data/pip.list"


def create_pip_list_again() -> list[str]:
    installed = get_ipkgs()
    content = "\n".join(installed)
    Path(PIP_LIST_FILE).write_text(content, encoding="utf-8")
    return installed


def load_installed_packages() -> list[str]:
    path = Path(PIP_LIST_FILE)
    if get_file_age(path) > 1.0 or not path.exists():
        return create_pip_list_again()
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def find_dist_info(prefix):
    import site

    matches = []
    for sp in site.getsitepackages():
        sp_path = Path(sp)
        for d in sp_path.glob(f"{prefix}*.dist-info"):
            matches.append(d)
    for sp in (site.getusersitepackages(),):
        sp_path = Path(sp)
        for d in sp_path.glob(f"{prefix}*.dist-info"):
            matches.append(d)
    return matches


def uninstall_packages(pkg_name: str) -> None:
    try:
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", pkg_name], check=True)
        print(f"Uninstalled {pkg_name}")
    except subprocess.CalledProcessError:
        print(f"Skipped {pkg_name} (not installed or error)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <package_prefix>")
        sys.exit(1)
    prefix = sys.argv[1].lower()
    installed = load_installed_packages()
    to_uninstall = [
        pkg.lower() for pkg in installed if prefix in pkg.lower() or fuzz.partial_ratio(prefix, pkg.lower()) > 95
    ]
    if not to_uninstall:
        print("no match found")
        sys.exit(0)
    for k in to_uninstall:
        ans = input(f"remove {k} --> ? (y/n)")
        if ans in {"y", "Y", "Yes", "yes", "YES", "OK", "ok"}:
            uninstall_packages(k)
