#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

from dh import get_nobinary, mpf3, runcmd


def has_shell_shebang(path):
    try:
        with Path(path).open("rb") as f:
            first = f.readline(256).decode("utf-8", errors="ignore").strip()
    except Exception:
        return False
    if not first.startswith("#!"):
        return False
    return "bash" in first or "sh" in first


def process_file(path):
    path = Path(path)
    path = Path(path)
    print(f"Formatting:  {path.name}")
    try:
        res, _, _ = runcmd(["shfmt", "-w", str(path)], show_output=True)
        if res != 0:
            print("  shfmt failed:", res.stderr.strip(), file=sys.stderr)
            return (False, path)
    except Exception as e:
        print("  error running shfmt:", e, file=sys.stderr)
        return (False, path)
    return (True, path)


def main():
    cwd = Path.cwd()
    files = [p for p in get_nobinary(cwd) if not p.suffix and has_shell_shebang(p) or p.suffix == ".sh"]
    results = mpf3(process_file, files)
    for res in results:
        ret, k = res
        if not ret:
            print(f"  - {k.relative_to(cwd)}")


if __name__ == "__main__":
    main()
