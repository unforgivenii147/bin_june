#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

from urllib.parse import urlparse

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

seen = set()
gl = []
with open("urls.txt") as f:
    lines = f.readlines()
    for line in lines:
        try:
            orig = urlparse(line.strip()).netloc
            if orig == "github.com":
                gl.append(line)
            if orig not in seen:
                seen.add(orig)
            else:
                continue
        except:
            print(line)
with open("cleaned_urls", "w") as fo:
    for k in seen:
        fo.write(f"{k}\n")
with open("git_urls", "a") as fg:
    fg.write("".join(gl))
