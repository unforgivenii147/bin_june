#!/data/data/com.termux/files/usr/bin/env python

from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

BASHBIN: Path = Path.home() / "bashbin"
BIN: Path = Path.home() / "bin"


def process_dir(cwd: Path, ext: str) -> None:
    for path in cwd.glob(f"*.{ext}"):
        symlink_path = path.with_name(path.stem)

        # Remove if it exists (whether symlink, file, or directory)
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()
            print(f"Removed existing: {symlink_path.name}")

        # Create fresh symlink
        symlink_path.symlink_to(path)
        print(f"Created: {symlink_path.name} -> {path.name}")


if __name__ == "__main__":
    process_dir(BASHBIN, "sh")
    process_dir(BIN, "py")
