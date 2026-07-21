#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

from pathlib import Path

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

TARGET_SHEBANG = "#!/data/data/com.termux/files/usr/bin/bash"
cwd = Path.cwd()


def process_file(path: Path) -> None:
    path = Path(path)
    print(f"processing {path.name}")
    with path.open("r+", encoding="utf-8") as f:
        lines = f.readlines()
        if not lines:
            return
        if lines and lines[0].startswith("#!"):
            lines[0] = TARGET_SHEBANG + "\n"
            if len(lines) > 1 and lines[1].strip() != "":
                lines.insert(1, "\n")
        f.seek(0)
        f.writelines(lines)
        f.truncate()
        print(f"{path.relativeto(cwd)}")
    if "bin" in path.parts:
        path.chmod(0o755)


if __name__ == "__main__":
    for path in cwd.rglob("*.sh"):
        process_file(path)
