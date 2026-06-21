#!/data/data/com.termux/files/usr/bin/python

import re
import tarfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import py7zr
from dh import BIN_EXT, TXT_EXT, get_files

url_pattern = re.compile("https?://[^\\s\\\"\\']+")
EXT = BIN_EXT
EXT.update(TXT_EXT)


def extract_urls_from_text(content: str):
    return set(url_pattern.findall(content))


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
    if path.suffix in EXT:
        return extract_urls_from_file(filepath)
    if path.suffix in {".zip", ".whl"}:
        return extract_urls_from_zip(filepath)
    if path.suffix.startswith(".tar") or path.suffix in {".tar.gz", ".tar.xz", ".tar.zst", ".tar.7z"}:
        return extract_urls_from_tar(filepath)
    if path.suffix == ".7z":
        return extract_urls_from_7z(filepath)
    return set()


if __name__ == "__main__":
    cwd = Path.cwd()
    file_paths = get_files(cwd)
    all_urls = set()
    with ThreadPoolExecutor(8) as executor:
        futures = [executor.submit(extract_urls, path) for path in file_paths]
        for future in as_completed(futures):
            all_urls.update(future.result())
    with Path("urls.txt").open("w", encoding="utf-8") as f:
        f.writelines((url + "\n" for url in sorted(all_urls)))
    print(f"Extracted {len(all_urls)} unique URLs to urls.txt")
