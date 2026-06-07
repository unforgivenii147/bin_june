#!/data/data/com.termux/files/usr/bin/python

from pathlib import Path

from fastwalk import walk_files


def is_python_file(path: str) -> bool:
    if Path(path).is_dir():
        return False
    if path.suffix == ".py":
        return True
    try:
        with Path(path).open(encoding="utf-8", errors="ignore") as f:
            first = f.readline().strip()
            if first.startswith("#!") and "python" in first:
                return True
            sample = f.read(200)
            return any((tok in sample for tok in ("def ", "class ", "import ", "from ")))
    except Exception:
        return False


def remove_header(path) -> None:
    original = []
    try:
        with Path(path).open(encoding="utf-8", errors="ignore") as f:
            original = f.readlines()
    except Exception:
        return
    cleaned = [line for line in original if not line.startswith(("# Author ", "# Email ", "# Time "))]
    print(f"{len(original)}=={len(cleaned)}")
    if cleaned != original:
        ans = "y"
        if ans == "y":
            Path(path).write_text("".join(cleaned), encoding="utf-8")


def main() -> None:
    for pth in walk_files("."):
        path = Path(pth)
        if is_python_file(path):
            remove_header(path)


if __name__ == "__main__":
    main()
