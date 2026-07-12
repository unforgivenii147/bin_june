#!/data/data/com.termux/files/usr/bin/env python


import sys
from pathlib import Path


from pathlib import Path


def get_file_age(path: (str | Path), str_mode: bool = False) -> float | str:
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


def read_requirements(filename) -> list[str]:
    req_file = Path(filename)
    with req_file.open(encoding="utf-8") as f:
        return [line.strip().replace("-", "_").lower() for line in f if line.strip() and not line.startswith("#")]


def strip_installed_from_requirements(fname: str) -> None:
    installed = get_ipkgs()
    installed = [p.lower().replace("-", "_") for p in installed if p]
    lines = read_requirements(fname)
    new_lines = [line for line in lines if line not in installed]
    new_lines = [line for line in new_lines if line not in STDLIB]
    new_lines = sorted(list(set(new_lines)))
    Path(fname).write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    removed = len(lines) - len(new_lines)
    print(f"Removed {removed} packages")


if __name__ == "__main__":
    fn = "requirements.txt"
    if len(sys.argv) > 1:
        fn = sys.argv[1]
    strip_installed_from_requirements(fn)
