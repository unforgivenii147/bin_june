#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import sys
from pathlib import Path

from dh import cprint, get_fast, gsz, runcmd

START_DIR = Path.cwd()
NUM_PROCESSES = 4


def process_file(path: str | Path) -> None:
    path = Path(path)
    before = gsz(path)
    try:
        cmd = [
            "pngquant",
            "--force",
            "--skip-if-larger",
            "--quality=60-70",
            "--strip",
            str(path),
            "--output",
            str(path),
        ]
        _ret, txt, _err = runcmd(cmd, show_output=False)
        if "skipping" in txt.lower():
            print(f" Skipped: {path.name}")
            return
        after = gsz(path)
        dz = before - after
        if not dz:
            print(f"✅ : {path.name} : (no change)")
            return
        ratio = (after / before) * 100
        print(f"✅ : {path.name}", end=" | ")
        cprint(f"{ratio:.1f} %")
        return
    except FileNotFoundError:
        print(
            "❌ Error: 'pngquant' command not found. Please ensure the 'pngquant' binary is installed and in your system PATH."
        )
    except Exception as e:
        print(f"❌ Error compressing {path}: {e}")
    return


def main() -> None:
    cwd = Path.cwd()
    for f in get_fast(cwd):
        if f.suffix in {".png", ".PNG"}:
            process_file(f)


if __name__ == "__main__":
    sys.exit(main())
