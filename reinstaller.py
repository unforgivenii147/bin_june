#!/data/data/com.termux/files/home/.local/bin/python
"""
Reinstall all packages installed in site-packages directory using parallel processing.
"""

import subprocess
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple, Set
import site
import argparse
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(f"reinstall_packages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def get_site_packages_dirs() -> List[Path]:
    """Get all site-packages directories."""
    site_dirs = []

    # Get user site-packages
    user_site = site.getusersitepackages()
    if user_site:
        site_dirs.append(Path(user_site))

    # Get system site-packages
    system_sites = site.getsitepackages()
    for s in system_sites:
        site_dirs.append(Path(s))

    # Remove duplicates while preserving order
    seen = set()
    unique_dirs = []
    for d in site_dirs:
        if d.exists() and str(d) not in seen:
            seen.add(str(d))
            unique_dirs.append(d)

    return unique_dirs


def extract_package_name_from_dist_info(dist_info: Path) -> str:
    """Extract package name from .dist-info directory."""
    # Format: package_name-version.dist-info
    name = dist_info.name.replace(".dist-info", "")
    # Remove version number (everything after and including the last hyphen before version)
    parts = name.rsplit("-", 1)
    if len(parts) == 2 and parts[1].replace(".", "").isdigit():
        return parts[0]
    return name


def get_installed_packages(site_dir: Path) -> Set[Tuple[str, Path]]:
    """Get set of installed packages from a site-packages directory."""
    packages = set()

    # Look for .dist-info directories (PEP 376)
    for dist_info in site_dir.glob("*.dist-info"):
        try:
            package_name = extract_package_name_from_dist_info(dist_info)
            packages.add((package_name, site_dir))
        except Exception as e:
            logger.warning(f"Error parsing {dist_info}: {e}")

    # Also look for .egg-info directories
    for egg_info in site_dir.glob("*.egg-info"):
        try:
            package_name = egg_info.name.replace(".egg-info", "")
            packages.add((package_name, site_dir))
        except Exception as e:
            logger.warning(f"Error parsing {egg_info}: {e}")

    return packages


def reinstall_package(package_info: Tuple[str, Path]) -> Tuple[str, bool, str]:
    """Reinstall a single package using pip."""
    package_name, site_dir = package_info

    try:
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-deps",  # Only reinstall this package, not its dependencies
            "--no-cache-dir",  # Don't use cached wheel
            package_name,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per package
        )

        if result.returncode == 0:
            logger.info(f"✓ Successfully reinstalled: {package_name}")
            return (package_name, True, result.stdout)
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            logger.error(f"✗ Failed to reinstall {package_name}: {error_msg}")
            return (package_name, False, error_msg)

    except subprocess.TimeoutExpired:
        logger.error(f"✗ Timeout reinstalling {package_name}")
        return (package_name, False, "Timeout expired")
    except Exception as e:
        logger.error(f"✗ Error reinstalling {package_name}: {str(e)}")
        return (package_name, False, str(e))


def reinstall_all_packages(
    max_workers: int = 4, exclude_packages: Set[str] = None, only_packages: Set[str] = None
) -> None:
    """Reinstall all packages found in site-packages directories."""

    if exclude_packages is None:
        exclude_packages = {"pip", "setuptools", "wheel"}  # Don't reinstall core packages

    # Get all site-packages directories
    site_dirs = get_site_packages_dirs()
    logger.info(f"Found site-packages directories: {[str(d) for d in site_dirs]}")

    # Collect all installed packages
    all_packages = set()
    for site_dir in site_dirs:
        packages = get_installed_packages(site_dir)
        all_packages.update(packages)

    # Filter packages
    if only_packages:
        all_packages = {(name, path) for name, path in all_packages if name in only_packages}

    all_packages = {(name, path) for name, path in all_packages if name not in exclude_packages}

    logger.info(f"Found {len(all_packages)} packages to reinstall")
    logger.info(f"Excluded packages: {exclude_packages}")

    if not all_packages:
        logger.warning("No packages found to reinstall!")
        return

    # Reinstall packages in parallel
    successful = []
    failed = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all reinstall tasks
        future_to_package = {executor.submit(reinstall_package, pkg): pkg[0] for pkg in all_packages}

        # Process completed tasks
        for future in as_completed(future_to_package):
            package_name = future_to_package[future]
            try:
                name, success, message = future.result()
                if success:
                    successful.append(name)
                else:
                    failed.append((name, message))
            except Exception as e:
                logger.error(f"Unexpected error for {package_name}: {e}")
                failed.append((package_name, str(e)))

    # Print summary
    logger.info("=" * 60)
    logger.info("REINSTALLATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"✓ Successfully reinstalled: {len(successful)} packages")
    logger.info(f"✗ Failed to reinstall: {len(failed)} packages")

    if successful:
        logger.info("\nSuccessfully reinstalled packages:")
        for name in sorted(successful):
            logger.info(f"  ✓ {name}")

    if failed:
        logger.info("\nFailed packages:")
        for name, error in failed:
            logger.info(f"  ✗ {name}: {error[:100]}...")


def main():
    parser = argparse.ArgumentParser(
        description="Reinstall all Python packages in site-packages using parallel processing"
    )
    parser.add_argument("-w", "--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    parser.add_argument(
        "-e",
        "--exclude",
        nargs="+",
        default=["pip", "setuptools", "wheel"],
        help="Packages to exclude from reinstallation",
    )
    parser.add_argument("-o", "--only", nargs="+", help="Only reinstall specified packages")
    parser.add_argument(
        "--dry-run", action="store_true", help="Only show what would be reinstalled without actually doing it"
    )
    parser.add_argument(
        "--include-deps", action="store_true", help="Also reinstall dependencies (not recommended, may cause conflicts)"
    )

    args = parser.parse_args()

    # Validate worker count
    if args.workers < 1:
        logger.error("Number of workers must be at least 1")
        sys.exit(1)

    logger.info(f"Starting package reinstallation with {args.workers} workers")

    if args.dry_run:
        logger.info("DRY RUN - No packages will be reinstalled")
        site_dirs = get_site_packages_dirs()
        all_packages = set()
        for site_dir in site_dirs:
            all_packages.update(get_installed_packages(site_dir))

        exclude_set = set(args.exclude)
        only_set = set(args.only) if args.only else None

        if only_set:
            all_packages = {(name, path) for name, path in all_packages if name in only_set}

        all_packages = {(name, path) for name, path in all_packages if name not in exclude_set}

        logger.info(f"Would reinstall {len(all_packages)} packages:")
        for name, path in sorted(all_packages):
            logger.info(f"  - {name} (from {path})")
    else:
        reinstall_all_packages(
            max_workers=args.workers,
            exclude_packages=set(args.exclude),
            only_packages=set(args.only) if args.only else None,
        )


if __name__ == "__main__":
    main()
