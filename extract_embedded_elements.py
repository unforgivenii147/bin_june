#!/data/data/com.termux/files/usr/bin/env python


import base64
import hashlib
import re
import sys
from collections.abc import Iterable
from os import scandir as os_scandir
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


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
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


def get_nobinary(path: str | Path) -> list[Path]:
    return [f for f in get_files(path) if not is_binary(f)]


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


OUTPUT_DIR = Path("extracted_base64")
DATA_URL_RE = re.compile(r"data:(?P<mime>[-\w.+/]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)", re.IGNORECASE)
MIME_EXTENSION_MAP: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/heif": "heif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "application/pdf": "pdf",
    "application/octet-stream": "bin",
    "font/woff": "woff",
    "font/woff2": "woff2",
    "application/font-woff": "woff",
    "application/font-woff2": "woff2",
    "font/ttf": "ttf",
    "font/otf": "otf",
    "font/eot": "eot",
    "font/svg": "svg",
    "application/javascript": "js",
}


def infer_extension(mime: str) -> str:
    return MIME_EXTENSION_MAP.get(mime.lower(), mime.rsplit("/", maxsplit=1)[-1])


def decode_base64(data: str) -> bytes:
    cleaned = "".join(data.split())
    return base64.b64decode(cleaned, validate=False)


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:15]


def extract_from_html(html: str) -> Iterable[tuple[str, bytes]]:
    for matchz in DATA_URL_RE.finditer(html):
        mime = matchz.group("mime")
        raw_data = matchz.group("data")
        try:
            decoded = decode_base64(raw_data)
        except Exception:
            continue
        yield mime, decoded


def save_asset(mime: str, data: bytes) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ext = infer_extension(mime)
    digest = content_hash(data)
    filename = f"{digest}.{ext}"
    path = OUTPUT_DIR / filename
    if not path.exists():
        path.write_bytes(data)
    return path


def main() -> None:
    cwd = Path.cwd()
    seen_hashes = set()
    extracted_count = 0
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_nobinary(cwd)
    for html_file in files:
        try:
            html = html_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for mime, data in extract_from_html(html):
            digest = content_hash(data)
            if digest in seen_hashes:
                continue
            seen_hashes.add(digest)
            save_asset(mime, data)
            extracted_count += 1
    print(f"{extracted_count} elements extracted.")


if __name__ == "__main__":
    main()
