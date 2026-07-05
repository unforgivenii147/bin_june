#!/data/data/com.termux/files/usr/bin/python


"""
Find non-pure Python packages in system site-packages and save list to file.
"""

import argparse
import logging
import site
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple
import pkg_resources

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)


def get_site_packages_paths() -> List[Path]:
    paths = []
    for path in site.getsitepackages():
        paths.append(Path(path))
    user_site = site.getusersitepackages()
    if user_site:
        user_path = Path(user_site)
        if user_path.exists():
            paths.append(user_path)
    return paths


def get_installed_packages() -> List[Tuple[str, str]]:
    packages = []
    for dist in pkg_resources.working_set:
        try:
            packages.append((dist.project_name, dist.version))
        except Exception as e:
            logger.warning(f"Error getting info for {dist.project_name}: {e}")
    return packages


def find_package_path(package_name: str, site_paths: List[Path]) -> Optional[Path]:
    for site_path in site_paths:
        pkg_path = site_path / package_name
        if pkg_path.exists() and pkg_path.is_dir():
            return pkg_path
        alt_name = package_name.replace("-", "_")
        pkg_path = site_path / alt_name
        if pkg_path.exists() and pkg_path.is_dir():
            return pkg_path
        for item in site_path.iterdir():
            if item.is_dir() and item.name.lower().replace("-", "_") == package_name.lower().replace("-", "_"):
                return item
    return None


def is_pure_python(package_name: str, site_paths: List[Path]) -> bool:
    pkg_path = find_package_path(package_name, site_paths)
    if not pkg_path:
        logger.warning(f"Cannot find package directory for {package_name}")
        return True
    extensions = [".so", ".pyd", ".dll", ".dylib"]
    for ext in extensions:
        try:
            if any(pkg_path.rglob(f"*{ext}")):
                return False
        except (PermissionError, OSError):
            continue
    return True


def check_package(args_tuple: Tuple[str, str, List[Path]]) -> Tuple[str, str, bool]:
    package_name, version, site_paths = args_tuple
    try:
        is_pure = is_pure_python(package_name, site_paths)
        return package_name, version, is_pure
    except Exception as e:
        logger.error(f"Error checking {package_name}: {e}")
        return package_name, version, True


def main():
    parser = argparse.ArgumentParser(description="Find non-pure Python packages in site-packages")
    parser.add_argument(
        "-o",
        "--output",
        default="binary_packages.txt",
        help="Output file for package list (default: binary_packages.txt)",
    )
    parser.add_argument("-j", "--jobs", type=int, default=4, help="Number of parallel jobs (default: 4)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    site_paths = get_site_packages_paths()
    logger.info(f"Site-packages paths: {[str(p) for p in site_paths]}")
    all_packages = get_installed_packages()
    logger.info(f"Found {len(all_packages)} installed packages")
    if not all_packages:
        logger.error("No packages found")
        return 1
    process_args = [(pkg, ver, site_paths) for pkg, ver in all_packages]
    binary_packages = []
    pure_packages = []
    total = len(process_args)
    completed = 0
    logger.info(f"Checking packages using {args.jobs} parallel jobs...")
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures = {executor.submit(check_package, arg): arg[0] for arg in process_args}
        for future in as_completed(futures):
            completed += 1
            pkg_name, version, is_pure = future.result()
            if not is_pure:
                binary_packages.append((pkg_name, version))
                logger.info(f"[{completed}/{total}] ✓ {pkg_name} is BINARY")
            else:
                pure_packages.append((pkg_name, version))
                if args.verbose:
                    logger.debug(f"[{completed}/{total}] - {pkg_name} is pure Python")
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("# Binary (non-pure Python) packages found in site-packages\n")
        f.write("# Format: package_name==version\n\n")
        for pkg, ver in sorted(binary_packages):
            f.write(f"{pkg}=={ver}\n")
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total packages checked: {total}")
    logger.info(f"Binary packages found: {len(binary_packages)}")
    logger.info(f"Pure Python packages: {len(pure_packages)}")
    logger.info(f"Results saved to: {output_path}")
    if binary_packages:
        logger.info("\nBinary packages:")
        for pkg, ver in binary_packages[:10]:
            logger.info(f"  - {pkg}=={ver}")
        if len(binary_packages) > 10:
            logger.info(f"  ... and {len(binary_packages) - 10} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
