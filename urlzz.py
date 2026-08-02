#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import os
import re
import sys
import tarfile
import zipfile
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from inspect import getfullargspec
from itertools import chain
from pathlib import Path
from typing import Any

import py7zr
from dh import cprint

CHUNK_SIZE = 1024 * 1024


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
            elif item.is_file() and (ext is None or item.suffix in ext):
                files.append(item)
    return files


ip_middle_octet = "(?:\\.(?:1?\\d{1,2}|2[0-4]\\d|25[0-5]))"
ip_last_octet = "(?:\\.(?:0|[1-9]\\d?|1\\d\\d|2[0-4]\\d|25[0-5]))"
url_regex = re.compile(
    "^(?:(?:https?|ftp)://)(?:[-a-z\\u00a1-\\uffff0-9._~%!$&'()*+,;=:]+(?::[-a-z0-9._~%!$&'()*+,;=:]*)?@)?(?:(?P<private_ip>(?:(?:10|127)"
    + ip_middle_octet
    + "{2}"
    + ip_last_octet
    + ")|(?:(?:169\\.254|192\\.168)"
    + ip_middle_octet
    + ip_last_octet
    + ")|(?:172\\.(?:1[6-9]|2\\d|3[0-1])"
    + ip_middle_octet
    + ip_last_octet
    + "))|(?P<private_host>(?:localhost))|(?P<public_ip>(?:[1-9]\\d?|1\\d\\d|2[01]\\d|22[0-3])"
    + ip_middle_octet
    + "{2}"
    + ip_last_octet
    + ")|\\[(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))\\]|(?:(?:(?:xn--[-]{0,2})|[a-z\\u00a1-\\uffff\\U00010000-\\U0010ffff0-9]-?)*[a-z\\u00a1-\\uffff\\U00010000-\\U0010ffff0-9]+)(?:\\.(?:(?:xn--[-]{0,2})|[a-z\\u00a1-\\uffff\\U00010000-\\U0010ffff0-9]-?)*[a-z\\u00a1-\\uffff\\U00010000-\\U0010ffff0-9]+)*(?:\\.(?:(?:xn--[-]{0,2}[a-z\\u00a1-\\uffff\\U00010000-\\U0010ffff0-9]{2,})|[a-z\\u00a1-\\uffff\\U00010000-\\U0010ffff]{2,})))(?::\\d{2,5})?(?:/[-a-z\\u00a1-\\uffff\\U00010000-\\U0010ffff0-9._~%!$&'()*+,;=:@/]*)?(?:\\?\\S*)?(?:#\\S*)?$",
    re.UNICODE | re.IGNORECASE,
)
URL_RE = re.compile(url_regex)


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
        return nontext / len(chunk) > 0.3
    except Exception:
        return True


def get_nobinary(path: str | Path) -> list[Path]:
    return [f for f in get_files(path) if not is_binary(f)]


def _func_args_as_dict(func: Callable[..., Any], *args: Any, **kwargs: Any):
    return dict(
        list(zip(dict.fromkeys(chain(getfullargspec(func)[0], kwargs.keys())), args, strict=False))
        + list(kwargs.items())
    )


def validator(func: Callable[..., Any]):

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        return True if func(*args, **kwargs) else ValidationFailure(func, _func_args_as_dict(func, *args, **kwargs))

    return wrapper


def is_valid_url(value, public=False):
    result = URL_RE.match(value)
    if not public:
        return result
    return result and (not any(result.groupdict().get(key) for key in ("private_ip", "private_host")))


url_pattern = re.compile("https?://[^\\s\\\"\\']+")


def extract_urls_from_text(content: str):
    result = set(url_pattern.findall(content))
    cprint(result)
    return result


def extract_urls_from_file(filepath):
    urls = set()
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        urls.update(extract_urls_from_text(content))
    except Exception as e:
        print(f"Failed to read {filepath}: {e}")
    return urls


def extract_urls_from_tar(filepath):
    urls = set()
    try:
        mode = "r:*"
        with tarfile.open(filepath, mode) as tar:
            for member in tar.getmembers():
                if member.isfile():
                    f = tar.extractfile(member)
                    if f:
                        content = f.read().decode("utf-8", errors="ignore")
                        urls.update(extract_urls_from_text(content))
    except Exception as e:
        print(f"Failed to read tar {filepath}: {e}")
    return urls


def extract_urls_from_zip(filepath):
    urls = set()
    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            for name in zf.namelist():
                try:
                    with zf.open(name) as f:
                        content = f.read().decode("utf-8", errors="ignore")
                        urls.update(extract_urls_from_text(content))
                except:
                    pass
    except Exception as e:
        print(f"Failed to read zip {filepath}: {e}")
    return urls


def extract_urls_from_7z(filepath):
    urls = set()
    try:
        with py7zr.SevenZipFile(filepath, mode="r") as archive:
            all_files = archive.readall()
            for bio in all_files.values():
                try:
                    content = bio.read().decode("utf-8", errors="ignore")
                    urls.update(extract_urls_from_text(content))
                except:
                    pass
    except Exception as e:
        print(f"Failed to read 7z {filepath}: {e}")
    return urls


def extract_urls(filepath):
    path = Path(filepath)
    if path.suffix in {".zip", ".whl"}:
        return extract_urls_from_zip(filepath)
    if path.suffix.startswith(".tar") or path.suffix in {
        ".tar.gz",
        ".tar.xz",
        ".tar.zst",
        ".tar.7z",
    }:
        return extract_urls_from_tar(filepath)
    if path.suffix == ".7z":
        return extract_urls_from_7z(filepath)
    else:
        return extract_urls_from_file(filepath)
    return set()


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    file_paths = [Path(p) for p in args] if args else get_nobinary(cwd)
    all_urls = set()
    with ThreadPoolExecutor(8) as executor:
        futures = [executor.submit(extract_urls, path) for path in file_paths]
        for future in as_completed(futures):
            all_urls.update(future.result())
    with Path("/sdcard/data/urlzz.txt").open("a", encoding="utf-8") as f:
        f.write("\n")
        f.writelines(url + "\n" for url in sorted(all_urls))
    print(f"Extracted {len(all_urls)} unique URLs to urls.txt")
