#!/data/data/com.termux/files/usr/bin/env python


import stat
from pathlib import Path
from dh import is_binary, should_skip


def has_shebang(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            first_three = f.read(3)
            return first_three == b"#!/"
    except (OSError, PermissionError):
        return False


def make_exec(filename: Path) -> None:
    original_mode = filename.stat().st_mode
    levels = [stat.S_IXUSR, stat.S_IXGRP, stat.S_IXOTH]
    for at in range(len(levels), 0, -1):
        try:
            mode = original_mode
            for level in levels[:at]:
                mode |= level
            filename.chmod(mode)
            break
        except OSError:
            continue


def is_exec(path: Path) -> bool:
    return bool(path.stat().st_mode & stat.S_IXUSR)


def process_directory(cwd: Path) -> None:
    for path in cwd.rglob("*"):
        if should_skip(path):
            continue
        pardir = path.parent.name
        if pardir in {"sbin", "bin"} and not is_exec(path):
            make_exec(path)
            print(f"[+] Made executable: {path.relative_to(cwd)}")
            continue
        if not path.suffix or is_binary(path):
            if path.name == "control" or "share" in path.parts:
                continue
            if not is_exec(path):
                make_exec(path)
                print(f"[+] Made executable: {path.relative_to(cwd)}")
                continue
        if has_shebang(path):
            if not is_exec(path):
                make_exec(path)
                print(f"[+] Made executable: {path.relative_to(cwd)}")
            else:
                print(f"[=] Already executable: {path}")


if __name__ == "__main__":
    process_directory(Path.cwd())
