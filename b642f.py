#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import base64
import binascii
import sys
from pathlib import Path

from dh import cprint

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

cleanup = True
cwd = Path.cwd()
out_dir = Path("output")
if not out_dir.exists():
    out_dir.mkdir(exist_ok=True)


def content_hash(data: bytes) -> str:
    from hashlib import sha256

    if not isinstance(data, bytes):
        data = data.encode("utf8")
    return sha256(data).hexdigest()


def clean_line(txt: str) -> str:
    indx = txt.index("base64,") + 7
    cleaned = txt[indx:]
    if '"' in cleaned:
        end_indx = cleaned.index('"')
        cleaned = cleaned[:end_indx]
    elif " " in cleaned:
        end_indx = cleaned.index(" ")
        cleaned = cleaned[:end_indx]
    elif ")" in cleaned:
        end_indx = cleaned.index(")")
        cleaned = cleaned[:end_indx]
    return cleaned


def try_all_base64_methods(line: str) -> bytes | None:
    """Attempt to decode a base64 string using various methods."""
    text = line.strip()

    # 1. Standard base64 with strict validation
    try:
        return base64.b64decode(text, validate=True)
    except Exception:
        pass

    # 2. Standard base64 ignoring invalid characters (lenient)
    try:
        return base64.b64decode(text, validate=False)
    except Exception:
        pass

    # 3. URL-safe base64 decoder
    try:
        return base64.urlsafe_b64decode(text)
    except Exception:
        pass

    # 4. Fix padding and try again
    try:
        missing_padding = len(text) % 4
        if missing_padding:
            text += "=" * (4 - missing_padding)
        return base64.b64decode(text)
    except Exception:
        pass

    # 5. Binascii fallback (handles some string quirks differently)
    try:
        return binascii.a2b_base64(text)
    except Exception:
        pass

    return None


def decode_base64_lines(path: Path) -> None:
    success_count = 0
    error_count = 0
    failed = []
    remained = []

    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            output_path = out_dir / f"{content_hash(line)}.bin"

            if "base64," in line:
                line = clean_line(line)

            # Try multiple base64 decoding methods
            decoded_bytes = try_all_base64_methods(line)

            if decoded_bytes is not None:
                output_path.write_bytes(decoded_bytes)
                success_count += 1
            else:
                print(f"✗ Line {i:4d} failed: Could not decode with any known base64 method")
                error_count += 1
                failed.append(i)
                remained.append(line)

    print(f"Failed lines: {failed}")
    cprint(f"✓ {success_count}\n✘ {error_count}", "cyan")

    if cleanup:
        new_content = "\n".join(remained)
        path.write_text(new_content)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input_file>")
        sys.exit(1)

    INPUT_FILE = Path(sys.argv[1])
    decode_base64_lines(INPUT_FILE)
