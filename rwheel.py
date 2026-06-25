#!/data/data/com.termux/files/usr/bin/python
"""
Repack site-packages packages into wheel files.
Works in Termux with Python 3.13.
"""

import argparse
import email.parser
import platform
import sys
import zipfile
from functools import partial
from multiprocessing import Pool, cpu_count
from pathlib import Path


def get_wheel_tags() -> str:
    """Determine appropriate wheel tags for the current platform."""
    python_version = f"{sys.version_info.major}{sys.version_info.minor}"
    abi_tag = f"cp{python_version}"

    # Detect platform
    system = platform.system().lower()
    arch = platform.machine().lower()

    if system == "linux" and "android" in platform.platform().lower():
        platform_tag = "android"
    elif system == "linux":
        platform_tag = "linux_x86_64" if arch == "x86_64" else arch
    else:
        platform_tag = "any"

    return f"cp{python_version}-{abi_tag}-{platform_tag}"


def get_package_info(pkg_path):
    """Extract package metadata."""
    info = {
        "name": pkg_path.name,
        "version": "0.0.0",
        "files": [],
        "data_files": [],
        "scripts": [],
        "has_so": False,
    }

    # Try to read metadata from dist-info or egg-info
    for dist_dir in pkg_path.parent.glob(f"{pkg_path.name}*.dist-info"):
        metadata_path = dist_dir / "METADATA"
        if metadata_path.exists():
            content = metadata_path.read_text(encoding="utf-8", errors="ignore")
            parser = email.parser.Parser()
            msg = parser.parsestr(content)
            info["version"] = msg.get("Version", "0.0.0")
            info["name"] = msg.get("Name", pkg_path.name)
            break

    # Also check egg-info
    for egg_dir in pkg_path.parent.glob(f"{pkg_path.name}*.egg-info"):
        metadata_path = egg_dir / "PKG-INFO"
        if metadata_path.exists():
            content = metadata_path.read_text(encoding="utf-8", errors="ignore")
            parser = email.parser.Parser()
            msg = parser.parsestr(content)
            info["version"] = msg.get("Version", "0.0.0")
            info["name"] = msg.get("Name", pkg_path.name)
            break

    # Check for .so files
    if pkg_path.is_dir() and any(pkg_path.rglob("*.so")):
        info["has_so"] = True

    return info


def collect_package_files(pkg_path, verbose=False):
    """Collect all files belonging to a package."""
    files = []
    site_packages = pkg_path.parent

    # Main package files
    if pkg_path.is_dir():
        for file_path in pkg_path.rglob("*"):
            if file_path.is_file() and not file_path.suffix == ".pyc":
                rel_path = file_path.relative_to(site_packages)
                files.append((rel_path, file_path))
    elif pkg_path.is_file() and pkg_path.suffix == ".py":
        # Single module package
        rel_path = pkg_path.relative_to(site_packages)
        files.append((rel_path, pkg_path))

    # Data files (usually in share/, etc/)
    data_dirs = ["share", "etc", "lib"]
    for data_dir in data_dirs:
        data_path = site_packages.parent / data_dir / pkg_path.name
        if data_path.exists():
            for file_path in data_path.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(site_packages.parent)
                    files.append((rel_path, file_path))

    # Scripts in bin directory
    bin_path = site_packages.parent / "bin"
    if bin_path.exists():
        for script_path in bin_path.glob("*"):
            if script_path.is_file() and (
                script_path.name.startswith(pkg_path.name) or script_path.name == pkg_path.name
            ):
                rel_path = script_path.relative_to(site_packages.parent)
                files.append((rel_path, script_path))

    if verbose:
        print(f"  Collected {len(files)} files for {pkg_path.name}")

    return files


def create_wheel(pkg_path, wheels_dir, dryrun: bool = False, verbose: bool = False) -> bool:
    """Create a wheel file for a package."""
    try:
        pkg_info = get_package_info(pkg_path)
        pkg_name = pkg_info["name"]
        pkg_version = pkg_info["version"]

        # Determine wheel tag
        wheel_tag = get_wheel_tags() if pkg_info["has_so"] else "py3-none-any"

        # Create wheel filename
        wheel_name = f"{pkg_name}-{pkg_version}-{wheel_tag}.whl"
        wheel_path = wheels_dir / wheel_name

        # Check if wheel already exists
        if wheel_path.exists():
            if verbose:
                print(f"  Wheel already exists: {wheel_name} (skipping)")
            return True

        if dryrun:
            print(f"[DRYRUN] Would repack {pkg_name}-{pkg_version} -> {wheel_path}")
            return True

        if verbose:
            print(f"Creating {wheel_name}...")

        # Collect all files
        files = collect_package_files(pkg_path, verbose)

        if not files:
            print(f"Warning: No files found for {pkg_name}")
            return False

        # Create wheel archive
        with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as wheel:
            # Add distribution files
            dist_info_dir = f"{pkg_name}-{pkg_version}.dist-info"

            # Create METADATA
            metadata = f"""Metadata-Version: 2.1
Name: {pkg_name}
Version: {pkg_version}
Generator: custom-repacker
"""
            wheel.writestr(f"{dist_info_dir}/METADATA", metadata)

            # Create WHEEL
            wheel_metadata = f"""Wheel-Version: 1.0
Generator: custom-repacker
Root-Is-Purelib: {str(not pkg_info["has_so"]).lower()}
Tag: {wheel_tag}
"""
            wheel.writestr(f"{dist_info_dir}/WHEEL", wheel_metadata)

            # Create top_level.txt for dist-info
            if pkg_path.is_dir():
                top_level = [pkg_path.name]
                wheel.writestr(f"{dist_info_dir}/top_level.txt", "\n".join(top_level))

            # Add all package files
            record_entries = []
            for rel_path, abs_path in files:
                archive_path = str(rel_path)
                wheel.write(abs_path, archive_path)

                # Calculate hash and size for RECORD (simplified)
                file_size = abs_path.stat().st_size
                record_entries.append(f"{archive_path},sha256=,{file_size}")

                if verbose:
                    print(f"  Added: {archive_path}")

            # Add RECORD file
            record_path = f"{dist_info_dir}/RECORD"
            record_content = "\n".join(record_entries) + f"\n{record_path},,\n"
            wheel.writestr(record_path, record_content)

        if verbose:
            print(f"✓ Created {wheel_name} ({len(files)} files, {wheel_path.stat().st_size} bytes)")

        return True

    except Exception as e:
        print(f"Error repacking {pkg_path.name}: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        return False


def get_packages(site_packages_dir: Path, package_names=None):
    """Get list of packages to repack."""
    packages = []

    # Ignore special directories
    ignore_dirs = {
        "__pycache__",
        "pip",
        "setuptools",
        "wheel",
        "_distutils_hack",
        "pkg_resources",
    }

    for item in site_packages_dir.iterdir():
        if item.name in ignore_dirs:
            continue
        if item.name.startswith("_"):
            continue

        # Regular packages (directories)
        if item.is_dir():
            # Check if it's a namespace package or regular package
            if (item / "__init__.py").exists():
                packages.append(item)
            # Also include directories that have .dist-info
            elif any(item.parent.glob(f"{item.name}*.dist-info")):
                packages.append(item)
        elif item.suffix == ".py" and item.name != "__init__.py":
            # Single module package
            packages.append(item)

    # Filter by package names if provided
    if package_names:
        filtered = []
        for pkg in packages:
            pkg_name = pkg.stem if pkg.suffix == ".py" else pkg.name
            if pkg_name in package_names:
                filtered.append(pkg)
        packages = filtered

    return packages


def repack_sequential(packages, wheels_dir: Path, dryrun, verbose):
    """Repack packages sequentially."""
    results = []
    for pkg in packages:
        results.append(create_wheel(pkg, wheels_dir, dryrun, verbose))
    return results


def repack_parallel(packages, wheels_dir: Path, dryrun, verbose) -> list[bool]:
    """Repack packages in parallel."""
    # Create a partial function with fixed arguments
    repack_func = partial(create_wheel, wheels_dir=wheels_dir, dryrun=dryrun, verbose=verbose)

    with Pool(processes=cpu_count()) as pool:
        results = pool.map(repack_func, packages)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Repack site-packages packages as wheel files")
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Repack all packages (uses multiprocessing)",
    )
    parser.add_argument(
        "--dryrun",
        action="store_true",
        help="Show what would be done without actual repacking",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("packages", nargs="*", help="Package names to repack (sequential mode)")

    args = parser.parse_args()

    # Set up wheels directory
    wheels_dir = Path.home() / "tmp" / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)

    if not args.dryrun:
        print(f"Wheels will be stored in: {wheels_dir}")

    # Determine site-packages directory
    possible_paths = [
        Path(sys.executable).parent
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages",
        Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
        Path(__file__).parent if "__file__" in dir() else Path.cwd(),
    ]

    site_packages = None
    for path in possible_paths:
        if path.exists() and path.is_dir():
            site_packages = path
            break

    if not site_packages:
        print("Could not find site-packages directory")
        return

    print(f"Using site-packages: {site_packages}")

    # Get packages based on arguments
    if args.packages:
        packages = get_packages(site_packages, args.packages)
    elif args.all or not args.packages:
        packages = get_packages(site_packages)
    else:
        packages = []

    if not packages:
        print("No packages found to repack")
        return

    print(f"Found {len(packages)} package(s) to repack")

    if args.dryrun:
        print("\n[DRYRUN MODE] No files will be created")

    # Choose repacking method based on mode
    use_parallel = args.all and len(packages) > 1

    if use_parallel:
        print(f"Using parallel mode with {cpu_count()} processes")
        results = repack_parallel(packages, wheels_dir, args.dryrun, args.verbose)
    else:
        if len(packages) > 1:
            print("Using sequential mode (use -a for parallel)")
        results = repack_sequential(packages, wheels_dir, args.dryrun, args.verbose)

    success_count = sum(results)

    # Show summary
    print(f"\nComplete: {success_count}/{len(packages)} packages repacked successfully")

    if success_count > 0 and not args.dryrun:
        print(f"\nWheels saved in: {wheels_dir}")
        # List created wheels
        wheel_files = list(wheels_dir.glob("*.whl"))
        if wheel_files:
            print("\nCreated wheels:")
            for wheel in sorted(wheel_files, key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
                size_mb = wheel.stat().st_size / (1024 * 1024)
                print(f"  {wheel.name} ({size_mb:.2f} MB)")
            if len(wheel_files) > 10:
                print(f"  ... and {len(wheel_files) - 10} more")


if __name__ == "__main__":
    main()
