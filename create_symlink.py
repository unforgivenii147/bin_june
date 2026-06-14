#!/data/data/com.termux/files/usr/bin/python

from pathlib import Path

BASHBIN: Path = Path.home() / "bashbin"
BIN: Path = Path.home() / "bin"


def process_dir(cwd: Path, ext: str) -> None:
    for path in cwd.glob(f"*.{ext}"):
        symlink_path = path.with_name(path.stem)
        if not symlink_path.exists():
            symlink_path.symlink_to(path)
            print(f"Created: {symlink_path.name} -> {path.name}")
        else:
            continue


if __name__ == "__main__":
    process_dir(BASHBIN, "sh")
    process_dir(BIN, "py")
