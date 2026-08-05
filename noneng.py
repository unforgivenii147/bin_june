#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from pathlib import Path

from dh import get_files, get_nobinary, is_binary
from dh.jobutils import mpf3
from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

CHUNK_SIZE = 1024 * 1024


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
