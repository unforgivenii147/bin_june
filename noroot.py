#!/data/data/com.termux/files/usr/bin/env python
import re
import sys
from collections import deque
from os import scandir as os_scandir
from pathlib import Path


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file():
                if ext is None or item.suffix in ext:
                    files.append(item)
    return files


def is_binary(path: Path | str) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum((1 for b in chunk if b not in text_chars))
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


def get_nobinary(path: str | Path) -> list[Path]:
    return [f for f in get_files(path) if not is_binary(f)]


IF_BLOCK_REGEX = re.compile(
    r"^if\s+\[\s*\$\((\S+)\)\s*\{\-ne\s+0\s*\}\]\s*;\s*then\s*\n((?:.|\n)*?)^\s*exit\s+1\s*$(.*?)^\s*fi",
    re.MULTILINE | re.IGNORECASE,
)


def remove_conditional_exit_blocks(file_path: Path) -> None:
    try:
        original_content = file_path.read_text(encoding="utf-8")
        modified_content = original_content
        while True:
            match = IF_BLOCK_REGEX.search(modified_content)
            if not match:
                break
            modified_content = modified_content[: match.start()] + modified_content[match.end() :]
        if original_content != modified_content:
            file_path.write_text(modified_content, encoding="utf-8")
            print(f"Cleaned: {file_path}")
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)


def main() -> None:
    cwd = Path.cwd()
    files_to_process = get_nobinary(cwd)
    for item_path in files_to_process:
        if item_path.is_file():
            try:
                content = item_path.read_text(encoding="utf-8", errors="ignore")
                is_likely_bash = False
                if content.startswith(("#!/bin/bash", "#!/usr/bin/env bash")) or oct(item_path.stat().st_mode)[
                    -3:
                ] not in (
                    "000",
                    "001",
                    "010",
                    "011",
                    "002",
                    "012",
                    "100",
                    "110",
                    "111",
                    "101",
                ):
                    is_likely_bash = True
                if is_likely_bash:
                    remove_conditional_exit_blocks(item_path)
            except Exception as e:
                print(f"Could not read or process {item_path}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
