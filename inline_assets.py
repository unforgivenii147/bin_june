#!/data/data/com.termux/files/home/.local/bin/python
"""
Make HTML files standalone by inlining referenced CSS and JS files.

- Processes one or more directories recursively (defaults to CWD if none given).
- Downloads remote CSS/JS via HTTP(S) and reads local CSS/JS from disk.
- Inlines them into <style> and <script> blocks, replacing the original tags.
- Updates HTML files in place.
- Silently ignores missing local or remote resources.
- Uses pathlib and parallel (threaded) processing.
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse, urljoin

try:
    import requests
except ImportError:
    sys.exit("Please install 'requests': pip install requests")

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Please install 'beautifulsoup4': pip install beautifulsoup4")


def is_remote(url: str) -> bool:
    return urlparse(url).scheme in ("http", "https")


def fetch_remote(url: str):
    """Download a remote resource. Returns text or None on failure."""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        # requests auto-decodes based on headers; fall back to apparent encoding
        if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding
        return resp.text
    except Exception:
        return None


def fetch_local(ref: str, base_dir: Path):
    """Read a local file referenced from an HTML file. Returns text or None."""
    try:
        # Strip query string / fragment that some build tools append
        ref = ref.split("?", 1)[0].split("#", 1)[0]
        if not ref:
            return None
        candidate = (base_dir / ref).resolve()
        # Stay reasonably safe: only read files, skip anything weird
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass
    return None


def fetch_resource(ref: str, base_dir: Path):
    """Fetch a CSS/JS resource, whether remote or local. Returns text or None."""
    if is_remote(ref):
        return fetch_remote(ref)
    return fetch_local(ref, base_dir)


def process_html_file(html_path: Path):
    """Inline CSS/JS into a single HTML file in place."""
    try:
        content = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return html_path, f"read error: {e}"

    try:
        soup = BeautifulSoup(content, "html.parser")
    except Exception as e:
        return html_path, f"parse error: {e}"

    base_dir = html_path.parent
    modified = False

    # --- Inline <link rel="stylesheet" href="..."> ---
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if not href:
            continue
        css = fetch_resource(href, base_dir)
        if css is None:
            continue
        style = soup.new_tag("style")
        style.string = css
        # Preserve non-href attributes (e.g., media) on the new style tag
        for key, val in link.attrs.items():
            if key in ("href", "rel"):
                continue
            style[key] = val
        link.replace_with(style)
        modified = True

    # --- Inline <script src="..."></script> ---
    for script in soup.find_all("script", src=True):
        src = script.get("src")
        if not src:
            continue
        js = fetch_resource(src, base_dir)
        if js is None:
            continue
        new_script = soup.new_tag("script")
        new_script.string = js
        for key, val in script.attrs.items():
            if key == "src":
                continue
            new_script[key] = val
        script.replace_with(new_script)
        modified = True

    if not modified:
        return html_path, "no changes"

    try:
        html_path.write_text(str(soup), encoding="utf-8")
        return html_path, "updated"
    except Exception as e:
        return html_path, f"write error: {e}"


def gather_html_files(dirs):
    """Collect all *.html / *.htm files from the given paths (files or dirs)."""
    files = []
    seen = set()
    for d in dirs:
        p = Path(d)
        if p.is_file() and p.suffix.lower() in (".html", ".htm"):
            if p not in seen:
                files.append(p)
                seen.add(p)
        elif p.is_dir():
            for pat in ("*.html", "*.htm"):
                for f in p.rglob(pat):
                    if f not in seen:
                        files.append(f)
                        seen.add(f)
        else:
            print(f"Warning: skipping {p} (not a file or directory)", file=sys.stderr)
    return files


def main():
    parser = argparse.ArgumentParser(description="Make HTML files standalone by inlining CSS/JS resources.")
    parser.add_argument(
        "dirs",
        nargs="*",
        help="Directories (or individual HTML files) to process. Defaults to current directory, processed recursively.",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=8,
        help="Number of parallel worker threads (default: 8).",
    )
    args = parser.parse_args()

    targets = [Path(d) for d in args.dirs] if args.dirs else [Path.cwd()]
    html_files = gather_html_files(targets)

    if not html_files:
        print("No HTML files found.", file=sys.stderr)
        return

    print(f"Found {len(html_files)} HTML file(s); processing with {args.workers} worker(s)...")

    updated = 0
    skipped = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(process_html_file, f): f for f in html_files}
        for fut in as_completed(futures):
            path, status = fut.result()
            if status == "updated":
                updated += 1
                print(f"[updated]    {path}")
            elif status == "no changes":
                skipped += 1
                print(f"[unchanged]  {path}")
            else:
                errors += 1
                print(f"[error]      {path} -> {status}", file=sys.stderr)

    print(f"\nDone. Updated: {updated}, Unchanged: {skipped}, Errors: {errors}")


if __name__ == "__main__":
    main()
