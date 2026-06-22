#!/data/data/com.termux/files/usr/bin/python
from __future__ import annotations
import pathlib
import sys
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, List, Tuple
import concurrent.futures
import time


def get_pypi_json(package: str, timeout: int = 10) -> Optional[Dict]:
    """Fetch package metadata from PyPI JSON API."""
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        print(f"  ❌ Error fetching {package}: {e}")
        return None


def find_wheel_url(package_data: Dict, python_version: str = "3.13") -> Optional[Tuple[str, int]]:
    """
    Find a compatible wheel URL for the given Python version.
    Returns (url, size) or None if no compatible wheel found.
    """
    releases = package_data.get("releases", {})
    if not releases:
        return None

    latest_version = max(releases.keys())
    files = releases[latest_version]

    # Filter for wheels and sort by compatibility
    wheels = []
    for file in files:
        if not file.get("packagetype") == "bdist_wheel":
            continue
        filename = file["filename"].lower()
        pv = file.get("python_version", "").lower()

        # Calculate compatibility score (higher = better)
        score = 0
        if f"cp{python_version.replace('.', '')}" in filename:
            score += 100
        if pv == f"=={python_version}":
            score += 100
        if pv.startswith(f">={python_version}"):
            score += 90
        if "py3" in filename and "none" in filename:
            score += 80
        if "abi3" in filename:
            score += 70
        if pv.startswith(">=3."):
            score += 60

        if score > 0:
            wheels.append((score, file))

    if not wheels:
        return None

    # Return the best match
    _, best_wheel = max(wheels, key=lambda x: x[0])
    return best_wheel["url"], best_wheel["size"]


def download_file(url: str, destination: pathlib.Path, expected_size: int, chunk_size: int = 8192) -> Tuple[bool, str]:
    """Download a file with progress indication."""
    print(f"  📥 Downloading {destination.name} ({expected_size / 1024 / 1024:.2f} MB)...")

    try:
        with urllib.request.urlopen(url) as response:
            total_size = int(response.headers.get("content-length", expected_size))
            downloaded = 0

            with open(destination, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    percent = (downloaded / total_size) * 100
                    print(
                        f"    ⬇ {downloaded / 1024 / 1024:.2f} MB / {total_size / 1024 / 1024:.2f} MB ({percent:.1f}%)",
                        end="\r",
                    )
            print(f"    ✅ Downloaded {destination.name} ({downloaded / 1024 / 1024:.2f} MB)")
            return True, ""

    except Exception as e:
        return False, f"Failed: {str(e)}"


def download_package(package: str, wheels_dir: pathlib.Path, python_version: str = "3.13") -> Tuple[str, bool, str]:
    """
    Download a package wheel for the specified Python version.
    Returns (package_name, success, message)
    """
    print(f"🔍 Fetching info for: {package}")

    package_data = get_pypi_json(package)
    if not package_data:
        return package, False, "Failed to fetch package info from PyPI"

    wheel_info = find_wheel_url(package_data, python_version)
    if not wheel_info:
        return package, False, "No compatible wheel found for Python " + python_version

    url, size = wheel_info
    filename = url.split("/")[-1]
    destination = wheels_dir / filename

    # Show download info before starting
    print(f"  📊 Package: {package}")
    print(f"  🔗 URL: {url}")
    print(f"  💾 Size: {size / 1024 / 1024:.2f} MB")

    success, message = download_file(url, destination, size)
    return package, success, message


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Download Python packages from PyPI as wheels")
    parser.add_argument("packages", nargs="+", help="Package name(s) to download")
    parser.add_argument("--python", default="3.13", help="Python version (default: 3.13)")
    parser.add_argument("--workers", type=int, default=4, help="Number of download workers (default: 4)")
    parser.add_argument(
        "--output", type=pathlib.Path, default=pathlib.Path("wheels"), help="Output directory (default: wheels)"
    )
    args = parser.parse_args()

    # Create output directory
    wheels_dir = args.output.resolve()
    wheels_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Saving wheels to: {wheels_dir}\n")

    # Download packages in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_package, pkg, wheels_dir, args.python): pkg for pkg in args.packages}

        success_count = 0
        for future in concurrent.futures.as_completed(futures):
            package, success, message = future.result()
            if success:
                success_count += 1
            else:
                print(f"  ⚠️  {package}: {message}")

    print(f"\n✅ Downloaded {success_count}/{len(args.packages)} packages successfully.")


if __name__ == "__main__":
    main()
