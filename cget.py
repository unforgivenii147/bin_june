#!/data/data/com.termux/files/usr/bin/env python
from __future__ import annotations

import contextlib
from io import BytesIO
from pathlib import Path

import pycurl

# SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def download_urls_from_file(filepath: str = "urls.txt", output_dir_str: str = "downloads") -> None:
    output_dir = Path(output_dir_str)
    output_dir.mkdir(exist_ok=True, parents=True)
    urls = []
    try:
        with Path(filepath).open("r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        print(f"❌ Error: {filepath} not found.")
        return
    print(f"📦 Downloading {len(urls)} URLs using pycurl...\n")
    for i, url in enumerate(urls, 1):
        print(f"🌐 [{i}/{len(urls)}] Downloading: {url}")
        buffer = BytesIO()
        c = pycurl.Curl()
        try:
            c.setopt(c.URL, url)
            c.setopt(c.WRITEDATA, buffer)
            c.setopt(c.FOLLOWLOCATION, 1)
            c.setopt(c.TIMEOUT, 30)
            c.setopt(c.USERAGENT, "pycurl/7.83.0")
            c.perform()
            status_code = c.getinfo(pycurl.RESPONSE_CODE)
            if status_code == 200:
                filename = url.split("/")[-1] or "index.html"
                with contextlib.suppress(BaseException):
                    _ = buffer.getvalue()
                safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ")[:200].strip()
                if not safe_filename:
                    safe_filename = "index.html"
                outpath = output_dir / safe_filename
                outpath.write_bytes(buffer.getvalue())
                print(f"✅ Saved to: {outpath.name}\n")
            else:
                print(f"⚠️  Failed (HTTP {status_code})\n")
        except pycurl.error as e:
            print(f"❌ pycurl error: {e}\n")
        finally:
            c.close()


if __name__ == "__main__":
    download_urls_from_file()
