from __future__ import annotations
from collections import deque
from collections.abc import Callable
from pathlib import Path
from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

CHUNK_SIZE = 1024 * 1024
from dh import get_files, get_nobinary


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)((delayed(process_function)(file_str, **kwargs) for file_str in file_strings))


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
        return nontext / len(chunk) > 0.3
    except Exception:
        return True


DetectorFactory.seed = 0
MAX_CHARS = 5000


def process_file(path) -> bool | None:
    path = Path(path)
    try:
        with Path(path).open(encoding="utf-8", errors="ignore") as f:
            text = f.read(MAX_CHARS).strip()
            if len(text) < 20:
                return False
            if detect(text) != "en":
                print(path)
                return True
    except (LangDetectException, OSError):
        return False


def main() -> None:
    cwd = Path.cwd()
    files = get_nobinary(cwd)
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
