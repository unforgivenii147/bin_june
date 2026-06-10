#!/data/data/com.termux/files/usr/bin/python

import os
from pathlib import Path

from dh import BIN_EXT, TXT_EXT, get_nobinary, mpf3
from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

DetectorFactory.seed = 0
MAX_CHARS = 5000


def process_file(path):
    path = Path(path)
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


def main():
    cwd = Path.cwd()
    files = get_nobinary(cwd)
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
