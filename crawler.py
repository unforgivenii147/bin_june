#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import json
import os
import re
from typing import List, Optional, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dh import cprint

BASE_URL = "https://dls2.aparatchi-dlcenter.top/DonyayeSerial/"
OUTPUT_FILE = "movies.txt"
STATE_FILE = "crawler_state.json"
MAX_SIZE_MB = 300
visited: Set[str] = set()
found_movies: List[str] = []


def size_to_mb(size_str: str) -> Optional[float]:
    """Convert size string to MB, handling various formats."""
    if not size_str or size_str.strip() == "-":
        return None

    # Handle common formats: 226.8M, 191.0M, 1.2G, etc.
    match = re.search(r"([\d.]+)\s*([KMG]?)i?B?", size_str.strip())
    if match:
        value = float(match.group(1))
        unit = match.group(2).upper()
        if unit == "G":
            return value * 1024
        elif unit == "M":
            return value
        elif unit == "K":
            return value / 1024
        else:
            return value / 1024 / 1024  # Assume bytes if no unit
    return None


def is_valid_movie(filename: str, size_mb: Optional[float]) -> bool:
    """Check if the file is a valid movie based on criteria."""
    if not filename:
        return False

    # Check file extension
    if not (filename.lower().endswith(".mkv") or filename.lower().endswith(".mp4")):
        return False

    # Check resolution
    if not ("480p" in filename.lower() or "720p" in filename.lower()):
        return False

    # Check size (skip if None or >= MAX_SIZE_MB)
    if size_mb is None or size_mb >= MAX_SIZE_MB:
        return False

    cprint(f"{filename} {size_mb:.2f} MB")
    return True


def save_state():
    """Save current crawler state to file."""
    state = {"visited": list(visited), "found_movies": found_movies}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_state():
    """Load previous crawler state from file."""
    global visited, found_movies
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                visited = set(state.get("visited", []))
                found_movies = state.get("found_movies", [])
                print(f"📂 Loaded previous state: {len(visited)} visited, {len(found_movies)} movies found")
                return True
        except Exception as e:
            print(f"⚠️ Error loading state: {e}")
    return False


def save_movie(url: str):
    """Save a single movie URL to file immediately."""
    if url not in found_movies:
        found_movies.append(url)
        # Append to file immediately
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            f.write(url + "\n")


def crawl(url: str, depth: int = 0) -> None:
    """Recursively crawl directories and find movie files."""
    # Skip if already visited
    if url in visited:
        return

    # Skip movie pages (direct file links handled differently)
    if "movie" in url.lower():
        return

    print(f"{'  ' * depth}Crawling: {url}")
    visited.add(url)

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to access {url}: {e}")
        return

    # Parse HTML
    soup = BeautifulSoup(response.text, "html.parser")

    # Handle both standard and XML/HTML formats
    rows = soup.find_all("tr")
    if not rows:
        # Try alternative selector for the XML format
        rows = soup.select("table tbody tr")

    for row in rows:
        # Find all cells
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        # Get the link cell (usually first column)
        link_cell = cols[0]
        link_tag = link_cell.find("a")
        if not link_tag:
            continue

        # Extract link info
        name = link_tag.text.strip()
        href = link_tag.get("href")
        if not href:
            continue

        # Get size from the third column (index 2)
        size_text = cols[2].text.strip() if len(cols) > 2 else ""
        size_mb = size_to_mb(size_text)

        # Build full URL
        full_url = urljoin(url, href)

        # Skip parent directory
        if "Parent directory" in name or "Parent Directory" in name:
            continue

        # If it's a directory, crawl it
        if href.endswith("/"):
            crawl(full_url, depth + 1)
        else:
            # It's a file - check if it's a valid movie
            if is_valid_movie(name, size_mb):
                print(f"✅ Found: {full_url} ({size_mb:.2f} MB)")
                save_movie(full_url)
                save_state()  # Save state after each movie found


def main():
    """Main entry point with resume support."""
    global found_movies

    print("🎬 Movie Crawler with Resume Support")
    print("=" * 40)

    # Load previous state if exists
    loaded = load_state()

    # If no previous state, start fresh
    if not loaded:
        if os.path.exists(OUTPUT_FILE):
            # Load existing movies file if it exists
            try:
                with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                    existing_movies = [line.strip() for line in f if line.strip()]
                    found_movies = existing_movies
                    print(f"📂 Loaded {len(found_movies)} movies from {OUTPUT_FILE}")
            except Exception as e:
                print(f"⚠️ Could not load existing movie file: {e}")

    # Start crawling
    print("\n🔍 Starting crawl...")
    try:
        crawl(BASE_URL)
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user. Saving state...")
        save_state()
        print("💾 State saved. Run again to resume.")
        return

    # Final save
    save_state()
    print(f"\n✅ Done. {len(found_movies)} movies saved to {OUTPUT_FILE}")

    # Show summary
    if found_movies:
        print("\n📋 First 5 movies found:")
        for url in found_movies[:5]:
            print(f"  • {url}")
        if len(found_movies) > 5:
            print(f"  ... and {len(found_movies) - 5} more")


if __name__ == "__main__":
    main()
