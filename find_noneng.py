#!/data/data/com.termux/files/home/.local/bin/python
"""
Scan the current directory recursively for text-based files, detect non-English lines,
and save results to noneng.txt.

Usage:
  python find_noneng.py            # default: recurse from . , min confidence 0.6
  python find_noneng.py --min 0.0  # include lower-confidence detections
  python find_noneng.py --ext py,md,txt  # limit to these extensions

Requirements:
  - detector.py available in the same directory (the module you already have)
  - optional: gcld3 and pycld2 for best accuracy
"""

from __future__ import annotations
import os
import argparse
from typing import Iterable, List, Tuple
import pathlib
import csv
import sys

from cld import (
    detect_language,
    detect_language_from_path,
    is_probably_text_bytes,
    read_file_bytes,
    safe_text_from_bytes,
)

DEFAULT_MAX_PROBE = 4096  # bytes to probe for binary/text detection
DEFAULT_READ_BYTES = 2 * 1024 * 1024  # up to 2MB per-file read

def find_files(
    root: str = ".", recursive: bool = True, exts: Iterable[str] | None = None, skip_hidden: bool = True
) -> Iterable[str]:
    exts_set = {e.lower().lstrip(".") for e in exts} if exts else None
    for dirpath, dirnames, filenames in os.walk(root):
        if skip_hidden:
            # remove hidden directories from walk
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if skip_hidden and fn.startswith("."):
                continue
            full = os.path.join(dirpath, fn)
            if exts_set:
                if os.path.splitext(fn)[1].lstrip(".").lower() not in exts_set:
                    continue
            yield full
        if not recursive:
            break

def is_text_file(path: str, max_probe: int = DEFAULT_MAX_PROBE) -> bool:
    try:
        sample = read_file_bytes(path, max_bytes=max_probe)
        return is_probably_text_bytes(sample)
    except Exception:
        return False

def scan_file_lines(path: str, min_confidence: float = 0.6) -> List[Tuple[str, int, str, float, str]]:
    """
    Returns list of tuples (path, line_no, lang_code, confidence, line_text)
    for lines in `path` that are detected as non-English and meet min_confidence.
    """
    results = []
    try:
        raw = read_file_bytes(path, max_bytes=DEFAULT_READ_BYTES)
    except Exception:
        return results
    if not is_probably_text_bytes(raw):
        return results
    text = safe_text_from_bytes(raw)
    # splitlines preserves no trailing newline; line numbers start at 1
    for i, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        # optional: skip extremely short lines that are unlikely natural language
        if len(line) < 3:
            continue
        res = detect_language(line, filename=os.path.basename(path))
        lang = (res.get("language_code") or "und").lower()
        conf = float(res.get("confidence") or 0.0)
        # treat "und" as unknown; we only record explicit non-English detections
        if lang != "en" and lang != "und" and conf >= min_confidence:
            results.append((path, i, lang, conf, raw_line))
    return results

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Find non-English lines in text files and save to noneng.txt")
    parser.add_argument("--root", "-r", default=".", help="Root directory to scan (default: .)")
    parser.add_argument(
        "--ext",
        "-e",
        default="",
        help="Comma-separated extensions to include (e.g. py,md,txt). Default: all text files.",
    )
    parser.add_argument(
        "--min", "-m", type=float, default=0.6, help="Minimum confidence to report (0..1). Default: 0.6"
    )
    parser.add_argument("--out", "-o", default="noneng.txt", help="Output filename (default: noneng.txt)")
    parser.add_argument("--no-recursive", action="store_true", help="Do not recurse into subdirectories")
    parser.add_argument(
        "--skip-hidden", action="store_true", default=True, help="Skip hidden files and directories (default: True)"
    )
    args = parser.parse_args(argv)

    exts = [e.strip().lower() for e in args.ext.split(",") if e.strip()] if args.ext else None
    out_path = args.out

    # Prepare output file and write header
    with open(out_path, "w", encoding="utf-8", newline="") as out_f:
        writer = csv.writer(out_f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["file", "line_no", "lang", "confidence", "text"])

        total_found = 0
        files_scanned = 0
        for fp in find_files(root=args.root, recursive=not args.no_recursive, exts=exts, skip_hidden=args.skip_hidden):
            # quick text probe to skip binary files
            try:
                if not is_text_file(fp):
                    continue
            except Exception:
                continue
            files_scanned += 1
            matches = scan_file_lines(fp, min_confidence=args.min)
            for path, line_no, lang, conf, raw_line in matches:
                # replace newlines/tabs in the stored line
                safe_line = raw_line.replace("\r", " ").replace("\n", " ").replace("\t", " ")
                writer.writerow([path, str(line_no), lang, f"{conf:.3f}", safe_line])
                total_found += 1

    print(f"Scanned files: {files_scanned}; non-English lines found: {total_found}; results saved to {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
