#!/data/data/com.termux/files/usr/bin/env python
import argparse
import contextlib
import io
import os
import re
import sys
import tarfile
import tempfile
import zipfile
from functools import wraps
from inspect import getfullargspec
from itertools import chain
from pathlib import Path
from tarfile import TarFile
from typing import Any, Callable, Dict
from urllib.parse import urlparse
from zipfile import ZipFile

import zstd

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


class ValidationFailure(Exception):
    def __init__(self, function: Callable[..., Any], arg_dict: Dict[str, Any]):
        self.func = function
        self.__dict__.update(arg_dict)

    def __repr__(self):
        return (
            f"ValidationFailure(func={self.func.__name__}, "
            + f"args={ ({k: v for (k, v) in self.__dict__.items() if k != 'func'}) })"
        )

    def __str__(self):
        return repr(self)

    def __bool__(self):
        return False


def _func_args_as_dict(func: Callable[..., Any], *args: Any, **kwargs: Any):
    return dict(list(zip(dict.fromkeys(chain(getfullargspec(func)[0], kwargs.keys())), args)) + list(kwargs.items()))


def validator(func: Callable[..., Any]):
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        return True if func(*args, **kwargs) else ValidationFailure(func, _func_args_as_dict(func, *args, **kwargs))

    return wrapper


ip_middle_octet = r"(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5]))"

ip_last_octet = r"(?:\.(?:0|[1-9]\d?|1\d\d|2[0-4]\d|25[0-5]))"

url_regex = re.compile(
    r"^"
    r"(?:(?:https?|ftp)://)"
    r"(?:[-a-z\u00a1-\uffff0-9._~%!$&'()*+,;=:]+"
    r"(?::[-a-z0-9._~%!$&'()*+,;=:]*)?@)?"
    r"(?:"
    r"(?P<private_ip>"
    r"(?:(?:10|127)" + ip_middle_octet + r"{2}" + ip_last_octet + r")|"
    r"(?:(?:169\.254|192\.168)" + ip_middle_octet + ip_last_octet + r")|"
    r"(?:172\.(?:1[6-9]|2\d|3[0-1])" + ip_middle_octet + ip_last_octet + r"))"
    r"|"
    r"(?P<private_host>"
    r"(?:localhost))"
    r"|"
    r"(?P<public_ip>"
    r"(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])"
    r"" + ip_middle_octet + r"{2}"
    r"" + ip_last_octet + r")"
    r"|"
    r"\[("
    r"([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|"
    r"([0-9a-fA-F]{1,4}:){1,7}:|"
    r"([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|"
    r"([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|"
    r"([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|"
    r"([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|"
    r"([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|"
    r"[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|"
    r":((:[0-9a-fA-F]{1,4}){1,7}|:)|"
    r"fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|"
    r"::(ffff(:0{1,4}){0,1}:){0,1}"
    r"((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}"
    r"(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|"
    r"([0-9a-fA-F]{1,4}:){1,4}:"
    r"((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}"
    r"(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])"
    r")\]|"
    r"(?:(?:(?:xn--[-]{0,2})|[a-z\u00a1-\uffff\U00010000-\U0010ffff0-9]-?)*"
    r"[a-z\u00a1-\uffff\U00010000-\U0010ffff0-9]+)"
    r"(?:\.(?:(?:xn--[-]{0,2})|[a-z\u00a1-\uffff\U00010000-\U0010ffff0-9]-?)*"
    r"[a-z\u00a1-\uffff\U00010000-\U0010ffff0-9]+)*"
    r"(?:\.(?:(?:xn--[-]{0,2}[a-z\u00a1-\uffff\U00010000-\U0010ffff0-9]{2,})|"
    r"[a-z\u00a1-\uffff\U00010000-\U0010ffff]{2,}))"
    r")"
    r"(?::\d{2,5})?"
    r"(?:/[-a-z\u00a1-\uffff\U00010000-\U0010ffff0-9._~%!$&'()*+,;=:@/]*)?"
    r"(?:\?\S*)?"
    r"(?:#\S*)?"
    r"$",
    re.UNICODE | re.IGNORECASE,
)

URL_RE = re.compile(url_regex)


def is_valid_url(value, public=False):
    result = URL_RE.match(value)
    if not public:
        return result
    return result and not any((result.groupdict().get(key) for key in ("private_ip", "private_host")))


def append_text(path: (str | Path), content: str, encoding: str = "utf-8") -> bool:
    path = Path(path)
    if path.is_symlink() or path.is_dir():
        return False
    if not path.exists():
        path.write_text(content, encoding=encoding)
        return True
    with path.open("a", encoding=encoding) as f:
        f.write("\n")
        f.write(content)
    return True


DEFAULT_MAX_MB = 15
EXCLUDE_DIRS = {".git", "__pycache__"}
URL_RE = re.compile(r"(https?://[^\s\'\"<>\\)\\(]+)", flags=re.IGNORECASE)

GIT_FILE = Path("gitlinks.txt")
REPO_FILE = Path("repos.txt")

ARCHIVE_SUFFIXES = (
    ".tar.gz",
    ".tgz",
    ".tar.xz",
    ".txz",
    ".tar.bz2",
    ".tbz2",
    ".tar.zst",
    ".tar",
    ".zip",
    ".whl",
    ".zst",
    ".br",
    ".xz",
    ".gz",
    ".7z",
    ".tar.7z",
    ".tar.br",
    ".tar.7z",
    ".t7z",
    ".tbz",
    "tzz",
)


def should_skip_dir(dirname: str) -> bool:
    return any(part in EXCLUDE_DIRS for part in dirname.split(os.sep))


def find_urls_in_text(text):
    found = set()
    for m in URL_RE.findall(text):
        url = m.rstrip(".,;:)]}>\"'")
        if url:
            found.add(url)
    return found


def decode_bytes_to_text(b):
    for enc in ("utf-8", "latin-1", "utf-16"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", errors="ignore")


def scan_bytes_for_urls(b: bytes, max_bytes, exts, name_hint=None):
    if exts is not None and name_hint:
        _, ext = os.path.splitext(name_hint)
        if ext and ext.lower() not in exts:
            return set()
    if len(b) > max_bytes:
        return set()
    text = decode_bytes_to_text(b)
    return find_urls_in_text(text)


def is_archive_name(name) -> bool:
    nl = name.lower()
    return any(nl.endswith(suf) for suf in ARCHIVE_SUFFIXES)


def open_tar_from_zst_path(path):
    temp = tempfile.TemporaryFile()
    with Path(path).open("rb") as fh:
        dctx = zstd.ZstdDecompressor()
        reader = dctx.stream_reader(fh)
        try:
            while True:
                chunk = reader.read(16384)
                if not chunk:
                    break
                temp.write(chunk)
        finally:
            with contextlib.suppress(Exception):
                reader.close()
    temp.seek(0)
    try:
        tf = tarfile.open(fileobj=temp, mode="r:*")
        return tf, temp
    except Exception:
        with contextlib.suppress(Exception):
            temp.close()
        return None, None


def process_zipfile_zipped(zipf: ZipFile, max_bytes, exts, found, recursion_depth, max_recursion) -> None:
    for zi in zipf.infolist():
        if zi.is_dir():
            continue
        name = zi.filename
        if zi.file_size > max_bytes:
            continue
        try:
            with zipf.open(zi) as member_f:
                b = member_f.read()
        except Exception:
            continue
        if recursion_depth < max_recursion and is_archive_name(name):
            process_bytes_as_archive(b, name, max_bytes, exts, found, recursion_depth + 1, max_recursion)
        else:
            found.update(scan_bytes_for_urls(b, max_bytes, exts, name_hint=name))


def process_tarfile_obj(tarf: TarFile, max_bytes, exts, found, recursion_depth, max_recursion) -> None:
    for member in tarf.getmembers():
        if not member.isfile():
            continue
        name = member.name
        if member.size > max_bytes:
            continue
        try:
            f = tarf.extractfile(member)
            if f is None:
                continue
            b = f.read()
        except Exception:
            continue
        if recursion_depth < max_recursion and is_archive_name(name):
            process_bytes_as_archive(b, name, max_bytes, exts, found, recursion_depth + 1, max_recursion)
        else:
            found.update(scan_bytes_for_urls(b, max_bytes, exts, name_hint=name))


def process_bytes_as_archive(b, name, max_bytes, exts, found, recursion_depth: int = 0, max_recursion: int = 3) -> None:
    lname = name.lower()
    bio = io.BytesIO(b)
    try:
        if lname.endswith((".zip", ".whl")):
            try:
                with zipfile.ZipFile(bio) as zf:
                    process_zipfile_zipped(zf, max_bytes, exts, found, recursion_depth, max_recursion)
            except zipfile.BadZipFile:
                found.update(scan_bytes_for_urls(b, max_bytes, exts, name_hint=name))
            return

        if any(lname.endswith(suf) for suf in (".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2")):
            try:
                bio.seek(0)
                with tarfile.open(fileobj=bio, mode="r:*") as tf:
                    process_tarfile_obj(tf, max_bytes, exts, found, recursion_depth, max_recursion)
            except tarfile.ReadError:
                found.update(scan_bytes_for_urls(b, max_bytes, exts, name_hint=name))
            return

        if lname.endswith(".tar.zst"):
            if zstd is None:
                found.update(scan_bytes_for_urls(b, max_bytes, exts, name_hint=name))
                return
            try:
                dctx = zstd.ZstdDecompressor()
                with dctx.stream_reader(io.BytesIO(b)) as reader, tempfile.TemporaryFile() as tmpf:
                    while True:
                        chunk = reader.read(16384)
                        if not chunk:
                            break
                        tmpf.write(chunk)
                    tmpf.seek(0)
                    try:
                        with tarfile.open(fileobj=tmpf, mode="r:*") as tf:
                            process_tarfile_obj(tf, max_bytes, exts, found, recursion_depth, max_recursion)
                    except tarfile.ReadError:
                        found.update(scan_bytes_for_urls(b, max_bytes, exts, name_hint=name))
                return
            except Exception:
                found.update(scan_bytes_for_urls(b, max_bytes, exts, name_hint=name))
                return

        found.update(scan_bytes_for_urls(b, max_bytes, exts, name_hint=name))
    except Exception:
        found.update(scan_bytes_for_urls(b, max_bytes, exts, name_hint=name))


def process_path(path: str, max_bytes: int, exts, found, recursion_limit=999) -> None:
    p = Path(path)
    try:
        size = p.stat().st_size
    except Exception:
        return
    if size > max_bytes and not is_archive_name(path):
        return

    lname = path.lower()
    try:
        if any(lname.endswith(suf) for suf in (".zip", ".whl")):
            try:
                with ZipFile(p) as zf:
                    process_zipfile_zipped(zf, max_bytes, exts, found, 0, recursion_limit)
                return
            except zipfile.BadZipFile:
                pass

        if any(lname.endswith(suf) for suf in (".tar", ".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2")):
            try:
                with tarfile.open(p, mode="r:*") as tf:
                    process_tarfile_obj(tf, max_bytes, exts, found, 0, recursion_limit)
                return
            except (tarfile.ReadError, EOFError):
                pass

        if lname.endswith(".tar.zst"):
            if zstd is None:
                try:
                    b = p.read_bytes()[: max_bytes + 1]
                    found.update(scan_bytes_for_urls(b, max_bytes, exts, name_hint=path))
                except Exception:
                    pass
                return

            tf, tmpf = open_tar_from_zst_path(path)
            if tf is None:
                return
            try:
                process_tarfile_obj(tf, max_bytes, exts, found, 0, recursion_limit)
            finally:
                with contextlib.suppress(Exception):
                    tf.close()
                with contextlib.suppress(Exception):
                    tmpf.close()
            return

        b = p.read_bytes()[: max_bytes + 1]
        found.update(scan_bytes_for_urls(b, max_bytes, exts, found=found, name_hint=path))
    except TypeError:
        try:
            b = p.read_bytes()[: max_bytes + 1]
            found.update(scan_bytes_for_urls(b, max_bytes, exts, name_hint=path))
        except Exception:
            return
    except Exception:
        return


def is_github_url(url):
    try:
        result = urlparse(url)
        return "github.com" in result.netloc
    except:
        return False


def extract_git_repos(urls):
    repo_urls = []
    github_regex = re.compile(r"https?://github\.com/([^/]+)/([^/]+?)(?:/|$|\.git|\?|#)")
    for url in urls:
        matchz = github_regex.search(url)
        if matchz:
            user = matchz.group(1)
            repo = matchz.group(2)
            if "/" not in repo and "." not in repo.split("/")[0]:
                repo_urls.append(f"{user}/{repo}")
    return repo_urls


def extract_and_save_gitlinks(urllist) -> None:
    glinks = []
    for url in urllist:
        if is_github_url(url):
            glinks.append(url)
            print(url)
    repoz = extract_git_repos(glinks)
    if repoz:
        repos = "\n".join(repoz)
        append_text(REPO_FILE, repos)
        git_links = "\n".join(glinks)
        append_text(GIT_FILE, git_links)
        print(f"{len(glinks)} links found.")
    else:
        print("no git link")


def iter_files(root: Path):
    root = root.resolve()
    for current_dir, dirnames, filenames in os.walk(str(root), topdown=True, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        if should_skip_dir(current_dir):
            continue
        cd = Path(current_dir)
        for fname in filenames:
            yield cd / fname


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find URLs in files and supported archives recursively and save them to a file."
    )
    parser.add_argument("-o", "--output", default="urls.txt", help="Output file (one URL per line).")
    parser.add_argument(
        "-m",
        "--max-mb",
        type=float,
        default=DEFAULT_MAX_MB,
        help=f"Max file/member size to scan in MB (default {DEFAULT_MAX_MB}).",
    )
    parser.add_argument(
        "-e",
        "--extensions",
        default="",
        help="Comma-separated list of file extensions to scan (e.g. .py,.md). If empty, all files are scanned. Applies to archive members too.",
    )
    parser.add_argument(
        "--max-recursion", type=int, default=999, help="Max nested-archive recursion depth (default 999)."
    )
    args = parser.parse_args()

    max_bytes = int(args.max_mb * 1024 * 1024)
    exts = {e.strip().lower() for e in args.extensions.split(",") if e.strip()} if args.extensions else None
    found = set()

    for p in iter_files(Path(".")):
        print(f"processing {p.name}")
        process_path(str(p), max_bytes, exts, found, recursion_limit=args.max_recursion)

    if not found:
        print("no url found")
        sys.exit(0)

    sorted_urls = sorted(found)
    extract_and_save_gitlinks(sorted_urls)

    out_path = Path(args.output)
    try:
        if out_path.exists():
            print("urls.txt exists. appending new urls")
            with out_path.open("a", encoding="utf-8") as out:
                out.write("\n\n")
                for u in sorted_urls:
                    if is_valid_url(u):
                        out.write(u + "\n")
        else:
            with out_path.open("w", encoding="utf-8") as out:
                for u in sorted_urls:
                    if is_valid_url(u):
                        out.write(u + "\n")

        print(f"Wrote {len(sorted_urls)} unique URLs to {args.output}")
        any(p.endswith(".tar.zst") for p in sorted_urls)
    except OSError as e:
        print(f"Error writing output file: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
