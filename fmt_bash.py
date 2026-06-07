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


def process_file(fp):
    print(f"Formatting:  {fp.name}")
    try:
        res, _, _ = runcmd(["shfmt", "-w", str(fp)], show_output=True)
        if res != 0:
            print("  shfmt failed:", res.stderr.strip(), file=sys.stderr)
            return (False, fp)
    except Exception as e:
        print("  error running shfmt:", e, file=sys.stderr)
        return (False, fp)
    return (True, fp)


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
