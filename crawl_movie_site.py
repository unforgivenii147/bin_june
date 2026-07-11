#!/data/data/com.termux/files/usr/bin/env python


import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://sr.moviesho.com/Series/"
OUTPUT_FILE = "movies.txt"
MAX_SIZE_MB = 400
visited = set()
found_movies = []


def size_to_mb(size_str: str) -> float | None:
    match = re.search("([\\d.]+)\\s*Mi?B", size_str)
    if match:
        return float(match.group(1))
    return None


def is_valid_movie(filename: str, size_mb: float | None) -> bool:
    if not filename.lower().endswith(".mkv"):
        return False
    if not ("480p" in filename.lower() or "720p" in filename.lower()):
        return False
    return not (size_mb is None or size_mb >= MAX_SIZE_MB)


def crawl(url: str) -> None:
    if url in visited:
        return
    print(f"Crawling: {url}")
    visited.add(url)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to access {url}: {e}")
        return
    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 3:
            continue
        link_tag = cols[0].find("a")
        if not link_tag:
            continue
        name = link_tag.text.strip()
        href = link_tag.get("href")
        size_text = cols[1].text.strip()
        full_url = urljoin(url, href)
        if "Parent directory" in name:
            continue
        if href.endswith("/"):
            crawl(full_url)
        else:
            size_mb = size_to_mb(size_text)
            if is_valid_movie(name, size_mb):
                print(f"Found: {full_url} ({size_mb} MB)")
                found_movies.append(full_url)


if __name__ == "__main__":
    crawl(BASE_URL)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(movie + "\n" for movie in found_movies)
    print(f"\n✅ Done. {len(found_movies)} movies saved to {OUTPUT_FILE}")
