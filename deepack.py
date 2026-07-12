#!/data/data/com.termux/files/usr/bin/env python


"""
Repack installed Python packages from system site-packages into wheel files.
Skips pure Python packages and .pyc files, uses parallel processing.
"""

import argparse
import importlib.metadata
import logging
import shutil
import site
import subprocess
import sys
import tempfile
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
            logger.warning(f"Error getting info for package: {e}")
    return packages


def is_pure_python(package_name: str, site_path: Path) -> bool:
    package_dir = site_path / package_name
    if not package_dir.exists():
        alt_name = package_name.replace("-", "_")
        package_dir = site_path / alt_name
    if not package_dir.exists():
        for item in site_path.iterdir():
            if item.is_dir() and item.name.lower().replace("-", "_") == package_name.lower().replace("-", "_"):
                package_dir = item
                break
        else:
            logger.warning(f"Cannot find package directory for {package_name}")
            return True
    extensions = [".so", ".pyd", ".dll", ".dylib"]
    for ext in extensions:
        if any(package_dir.rglob(f"*{ext}")):
            return False
    if any(package_dir.rglob("*.pth")):
        pass
    return True


def get_package_path(package_name: str, site_paths: List[Path]) -> Optional[Path]:
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


def repack_package(args_tuple: Tuple[str, str, Path, List[Path]]) -> Tuple[str, bool, Optional[str]]:
    package_name, version, output_dir, site_paths = args_tuple
    try:
        pkg_path = get_package_path(package_name, site_paths)
        if not pkg_path:
            return package_name, False, f"Package directory not found"
        if is_pure_python(package_name, pkg_path.parent):
            return package_name, False, "Pure Python package - skipped"
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            dest_path = temp_path / package_name
            dest_path.mkdir(parents=True)
            for file_path in pkg_path.rglob("*"):
                if file_path.suffix == ".pyc":
                    continue
                rel_path = file_path.relative_to(pkg_path)
                dest_file = dest_path / rel_path
                if file_path.is_dir():
                    dest_file.mkdir(parents=True, exist_ok=True)
                else:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, dest_file)
            metadata_dir = temp_path / f"{package_name}.dist-info"
            metadata_dir.mkdir(exist_ok=True)
            for site_path in site_paths:
                dist_info = site_path / f"{package_name}.dist-info"
                if not dist_info.exists():
                    alt_name = package_name.replace("-", "_")
                    dist_info = site_path / f"{alt_name}.dist-info"
                if dist_info.exists() and dist_info.is_dir():
                    for item in dist_info.iterdir():
                        if item.is_file():
                            shutil.copy2(item, metadata_dir / item.name)
                    break
            else:
                metadata_file = metadata_dir / "METADATA"
                metadata_file.write_text(
                    f"""
Metadata-Version: 2.1
Name: {package_name}
Version: {version}
""".strip()
                )
                wheel_file = metadata_dir / "WHEEL"
                wheel_file.write_text(
                    """
Wheel-Version: 1.0
Generator: repack-script
Root-Is-Purelib: false
""".strip()
                )
            wheel_cmd = [
                sys.executable,
                "-m",
                "wheel",
                "pack",
                "--build-number",
                "0",
                "--dest-dir",
                str(output_dir),
                str(temp_path),
            ]
            wheel_cmd_alt = [
                sys.executable,
                "-m",
                "wheel",
                "pack",
                "--build-number",
                "0",
                "--dest-dir",
                str(output_dir),
                str(dest_path),
            ]
            try:
                result = subprocess.run(wheel_cmd, capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    result = subprocess.run(wheel_cmd_alt, capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    wheel_files = list(output_dir.glob(f"{package_name.replace('-', '_')}*.whl"))
                    if wheel_files:
                        return (package_name, True, f"Created: {wheel_files[0].name}")
                    else:
                        return (package_name, False, "Wheel created but not found")
                else:
                    return (package_name, False, f"Wheel command failed: {result.stderr[:100]}")
            except Exception as e:
                return package_name, False, f"Error running wheel: {str(e)}"
    except Exception as e:
        return package_name, False, f"Error: {str(e)}"


def main():
    parser = argparse.ArgumentParser(description="Repack installed Python packages into wheel files")
    parser.add_argument(
        "-o", "--output", default="~/tmp/.whl", help="Output directory for wheel files (default: ~/tmp/.whl)"
    )
    parser.add_argument(
        "-p", "--packages", nargs="+", help="Specific packages to repack (default: all non-pure packages)"
    )
    parser.add_argument("-j", "--jobs", type=int, default=4, help="Number of parallel jobs (default: 4)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    site_paths = get_site_packages_paths()
    logger.info(f"Site-packages paths: {[str(p) for p in site_paths]}")
    all_packages = get_installed_packages()
    logger.info(f"Found {len(all_packages)} installed packages")
    if args.packages:
        packages_to_process = [(pkg, ver) for pkg, ver in all_packages if pkg in args.packages]
    else:
        packages_to_process = []
        total = len(all_packages)
        for idx, (pkg, ver) in enumerate(all_packages, 1):
            logger.info(f"Checking package {idx}/{total}: {pkg}")
            pkg_path = get_package_path(pkg, site_paths)
            if pkg_path:
                if not is_pure_python(pkg, pkg_path.parent):
                    packages_to_process.append((pkg, ver))
                    logger.info(f"  ✓ {pkg} is NOT pure Python")
                else:
                    logger.info(f"  - {pkg} is pure Python - skipping")
            else:
                logger.warning(f"  ? {pkg} not found - skipping")
    logger.info(f"Processing {len(packages_to_process)} packages")
    if not packages_to_process:
        logger.info("No packages to process")
        return 0
    process_args = [(pkg, ver, output_dir, site_paths) for pkg, ver in packages_to_process]
    successful = []
    failed = []
    skipped = []
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures = {executor.submit(repack_package, arg): arg[0] for arg in process_args}
        total = len(futures)
        completed = 0
        for future in as_completed(futures):
            completed += 1
            pkg_name, success, message = future.result()
            if success:
                successful.append((pkg_name, message))
                logger.info(f"[{completed}/{total}] ✓ {pkg_name}: {message}")
            elif "Pure Python" in message:
                skipped.append((pkg_name, message))
                logger.info(f"[{completed}/{total}] - {pkg_name}: {message}")
            else:
                failed.append((pkg_name, message))
                logger.error(f"[{completed}/{total}] ✗ {pkg_name}: {message}")
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total packages processed: {len(packages_to_process)}")
    logger.info(f"✓ Successfully repacked: {len(successful)}")
    logger.info(f"- Skipped (pure Python): {len(skipped)}")
    logger.info(f"✗ Failed: {len(failed)}")
    if successful:
        logger.info(f"\nWheel files saved in: {output_dir}")
        for pkg, msg in successful[:5]:
            logger.info(f"  - {msg}")
        if len(successful) > 5:
            logger.info(f"  ... and {len(successful) - 5} more")
    if failed:
        logger.error("\nFailed packages:")
        for pkg, msg in failed:
            logger.error(f"  ✗ {pkg}: {msg}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
