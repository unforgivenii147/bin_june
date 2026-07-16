#!/data/data/com.termux/files/usr/bin/env python

"""
Rewrite of the RECORD updater with multiprocessing support.
Recalculates file hashes and sizes for installed packages,
skipping .pyc files and certain metadata files.
"""

import base64
import hashlib
import logging
import multiprocessing
import site
import sys
from pathlib import Path
from typing import Tuple

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


def find_site_packages() -> Path | None:
    try:
        dirs = site.getsitepackages()
    except Exception:
        logger.exception("Failed to get site-packages directories")
        return None
    if not dirs:
        logger.error("No site-packages directories found")
        return None
    path = Path(dirs[0])
    logger.info("Found site-packages: %s", path)
    return path


def calculate_file_hash(filepath: Path) -> str:
    sha256_hash = hashlib.sha256()
    try:
        with filepath.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256_hash.update(chunk)
        raw_hash = sha256_hash.digest()
        b64_hash = base64.urlsafe_b64encode(raw_hash).decode("ascii").rstrip("=")
        return f"sha256={b64_hash}"
    except Exception:
        logger.exception("Error hashing %s", filepath)
        return ""


def get_file_size(filepath: Path) -> int:
    try:
        return filepath.stat().st_size
    except Exception:
        logger.exception("Error getting size for %s", filepath)
        return 0


def parse_record_line(line: str) -> Tuple[str, str, str]:
    parts = line.strip().split(",")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], "", ""


def should_include_file(filepath: Path) -> bool:
    name = filepath.name
    return not (
        filepath.suffix == ".pyc" or name.endswith(".pyc") or name in ("direct_url.json", "INSTALLER", "RECORD")
    )


def process_dist_info(dist_info_dir: Path) -> bool:
    record_path = dist_info_dir / "RECORD"
    logger.info("Processing %s", record_path)
    if not record_path.exists():
        logger.error("RECORD not found: %s", record_path)
        return False
    try:
        with record_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        logger.exception("Failed to read %s", record_path)
        return False
    new_lines = []
    missing_files = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        relative_path, _old_hash, _old_size = parse_record_line(line)
        if relative_path == "RECORD":
            continue
        full_path = dist_info_dir.parent / relative_path
        if not should_include_file(full_path):
            logger.debug("Skipping excluded file: %s", relative_path)
            continue
        if not full_path.exists():
            missing_files.append(relative_path)
            logger.warning("Missing file: %s", relative_path)
            continue
        new_hash = calculate_file_hash(full_path)
        if not new_hash:
            logger.warning("Hash failed for %s, keeping original line", relative_path)
            new_lines.append(raw_line.rstrip("\n"))
            continue
        new_size = get_file_size(full_path)
        new_lines.append(f"{relative_path},{new_hash},{new_size}")
    record_relative = str(record_path.relative_to(dist_info_dir.parent))
    new_lines.append(f"{record_relative},,")
    if missing_files:
        logger.warning(
            "%d missing files in %s: %s",
            len(missing_files),
            dist_info_dir.name,
            ", ".join(missing_files),
        )
    try:
        record_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        logger.info("Updated %s", record_path)
    except Exception:
        logger.exception("Failed to write %s", record_path)
        return False
    try:
        record_hash = calculate_file_hash(record_path)
        record_size = get_file_size(record_path)
        with record_path.open("r", encoding="utf-8") as f:
            final_lines = f.readlines()
        if final_lines:
            last = final_lines[-1].strip().split(",")
            if len(last) >= 1:
                final_lines[-1] = f"{last[0]},{record_hash},{record_size}\n"
        record_path.write_text("".join(final_lines), encoding="utf-8")
        logger.debug("Self-hash updated for %s", record_path)
    except Exception:
        logger.exception("Failed to update self-hash for %s", record_path)
    return True


def main() -> None:
    logger.info("Starting multiprocess RECORD updater")
    site_packages = find_site_packages()
    if not site_packages:
        sys.exit(1)
    dist_info_dirs = sorted(site_packages.glob("*.dist-info"))
    if not dist_info_dirs:
        logger.warning("No .dist-info directories found in %s", site_packages)
        sys.exit(0)
    logger.info("Found %d distribution(s)", len(dist_info_dirs))
    num_workers = max(1, multiprocessing.cpu_count() - 1)
    logger.info("Using %d worker processes", num_workers)
    updated = 0
    failed = 0
    with multiprocessing.Pool(processes=num_workers) as pool:
        for success in pool.imap_unordered(process_dist_info, dist_info_dirs):
            if success:
                updated += 1
            else:
                failed += 1
    logger.info("Summary: %d updated, %d failed", updated, failed)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
