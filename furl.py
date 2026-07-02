#!/data/data/com.termux/files/usr/bin/env python
"""
Extract URLs from files in current directory recursively.
Separates git links into a separate file and shows progress.
Uses pathlib and parallel processing for efficiency.
"""

import re
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict
from tqdm import tqdm
from typing import Tuple, Set

URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]*', re.IGNORECASE)
GIT_DOMAINS = {
    "github.com",
    "gitlab.com",
    "gitea.io",
    "bitbucket.org",
    "git.sr.ht",
    "codeberg.org",
    "gitbucket.org",
    "gogs.io",
}


def is_git_url(url: str) -> bool:
    return any(domain in url.lower() for domain in GIT_DOMAINS)


def extract_urls_from_file(file_path: Path) -> Tuple[Set[str], Set[str]]:
    regular_urls = set()
    git_urls = set()
    try:
        if file_path.stat().st_size > 10 * 1024 * 1024:
            return regular_urls, git_urls
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return regular_urls, git_urls
        urls = URL_PATTERN.findall(content)
        for url in urls:
            url = url.rstrip(".,;:!?)'\"`")
            if url:
                if is_git_url(url):
                    git_urls.add(url)
                else:
                    regular_urls.add(url)
    except Exception:
        pass
    return regular_urls, git_urls


def main():
    current_dir = Path.cwd()
    exclude_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", ".env", "dist", "build"}
    all_files = [f for f in current_dir.rglob("*") if f.is_file() and not any(part in exclude_dirs for part in f.parts)]
    if not all_files:
        print("No files found to process.")
        return
    print(f"Found {len(all_files)} files to process...")
    all_regular_urls = set()
    all_git_urls = set()
    max_workers = 4
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(extract_urls_from_file, file_path): file_path for file_path in all_files}
        with tqdm(total=len(all_files), desc="Processing files", unit="file") as pbar:
            for future in as_completed(future_to_file):
                regular_urls, git_urls = future.result()
                all_regular_urls.update(regular_urls)
                all_git_urls.update(git_urls)
                pbar.update(1)
    all_regular_urls = sorted(all_regular_urls)
    all_git_urls = sorted(all_git_urls)
    urls_file = current_dir / "urls.txt"
    with open(urls_file, "w", encoding="utf-8") as f:
        for url in all_regular_urls:
            f.write(url + "\n")
    gitlinks_file = current_dir / "gitlinks.txt"
    with open(gitlinks_file, "w", encoding="utf-8") as f:
        for url in all_git_urls:
            f.write(url + "\n")
    print(f"\n✓ Extraction complete!")
    print(f"  Regular URLs: {len(all_regular_urls)} → {urls_file.name}")
    print(f"  Git URLs: {len(all_git_urls)} → {gitlinks_file.name}")


if __name__ == "__main__":
    main()
