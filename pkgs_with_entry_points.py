#!/data/data/com.termux/files/usr/bin/env python
"""
Script to find Python packages in system site directories and categorize them based on entry_points.txt.
Separates packages into:
1. Pure Python without entry_points
2. Non-pure (binary) without entry_points
3. Pure Python with valid entry_points
4. Non-pure with valid entry_points
Uses multiprocessing for parallel scanning and pathlib for path operations.
Optimized for Linux/Termux - only checks for .so files.
"""

import sys
import json
from pathlib import Path
from multiprocessing import Pool, cpu_count
from typing import List, Tuple, Optional, Dict, Set
import argparse
from datetime import datetime
import re
import configparser


def get_site_packages_dirs() -> List[Path]:
    """Get all system site-packages directories."""
    site_dirs = []

    # Get Python's site-packages paths
    import site

    for path in site.getsitepackages():
        site_dirs.append(Path(path))

    # Also check user site directory
    user_site = site.getusersitepackages()
    if user_site:
        site_dirs.append(Path(user_site))

    # Additional common locations
    common_paths = [
        Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
        Path(sys.prefix)
        / "local"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages",
    ]

    for path in common_paths:
        if path.exists() and path not in site_dirs:
            site_dirs.append(path)

    # Filter to only existing directories
    return [d for d in site_dirs if d.exists() and d.is_dir()]


def get_package_name_from_path(path: Path) -> str:
    """Extract clean package name from path."""
    name = path.name

    # Handle .dist-info directories
    if name.endswith(".dist-info"):
        name = name[:-10]
    # Handle .egg-info directories
    elif name.endswith(".egg-info"):
        name = name[:-9]

    # Remove version numbers (common patterns: package-1.2.3, package-1.2.3-py3.10)
    name = re.sub(r"-\d+\.\d+\.\d+.*$", "", name)
    name = re.sub(r"-\d+\.\d+.*$", "", name)

    # Remove Python version tags
    name = re.sub(r"-py\d+\.\d+$", "", name)
    name = re.sub(r"-py\d+$", "", name)

    return name


def is_pure_python_package(pkg_name: str, site_dir: Path) -> bool:
    """
    Determine if a package is pure Python by checking RECORD file for .so files.
    Returns True if pure Python (no .so files), False if it has binary components.
    Optimized for Linux - only checks for .so files.
    """
    try:
        # Look for .dist-info directory
        dist_info_patterns = [
            f"{pkg_name}*.dist-info",
            f"{pkg_name.replace('-', '_')}*.dist-info",
            f"{pkg_name.replace('_', '-')}*.dist-info",
        ]

        for pattern in dist_info_patterns:
            for dist_info in site_dir.glob(pattern):
                if dist_info.is_dir():
                    # Check RECORD file
                    record_file = dist_info / "RECORD"
                    if record_file.exists():
                        try:
                            content = record_file.read_text(encoding="utf-8", errors="ignore")
                            # Check for .so files in RECORD (Linux shared libraries)
                            if ".so" in content:
                                return False
                        except Exception:
                            # If can't read RECORD, assume it might be binary
                            pass

        # Look for .egg-info directory (fallback for older packages)
        egg_info_patterns = [
            f"{pkg_name}*.egg-info",
            f"{pkg_name.replace('-', '_')}*.egg-info",
            f"{pkg_name.replace('_', '-')}*.egg-info",
        ]

        for pattern in egg_info_patterns:
            for egg_info in site_dir.glob(pattern):
                if egg_info.is_dir():
                    # Check for SOURCES.txt that might list binary files
                    sources_file = egg_info / "SOURCES.txt"
                    if sources_file.exists():
                        try:
                            content = sources_file.read_text(encoding="utf-8", errors="ignore")
                            if ".so" in content:
                                return False
                        except:
                            pass

                    # Check for native_libs.txt
                    native_libs = egg_info / "native_libs.txt"
                    if native_libs.exists():
                        return False

        # If no .dist-info or .egg-info found, check the package directory directly
        # Look for package directory
        package_dir_patterns = [pkg_name, pkg_name.replace("-", "_"), pkg_name.replace("_", "-")]

        for pattern in package_dir_patterns:
            for package_dir in site_dir.glob(pattern):
                if (
                    package_dir.is_dir()
                    and not package_dir.name.endswith(".dist-info")
                    and not package_dir.name.endswith(".egg-info")
                ):
                    # Check for .so files in the package directory
                    for item in package_dir.rglob("*"):
                        if item.is_file() and item.suffix == ".so":
                            return False
                        # Check for C extension modules with .cpython-*.so pattern
                        if item.is_file() and ".cpython-" in str(item) and item.suffix == ".so":
                            return False

        # Default to pure Python if no binary indicators found
        return True

    except Exception:
        # On error, assume it's pure Python
        return True


def parse_entry_points(entry_points_file: Path) -> Dict[str, List[str]]:
    """
    Parse entry_points.txt file and extract console_scripts and gui_scripts.
    Returns dict with script types and their entry names.
    """
    scripts = {"console_scripts": [], "gui_scripts": [], "other": []}

    try:
        if not entry_points_file.exists():
            return scripts

        content = entry_points_file.read_text(encoding="utf-8", errors="ignore")

        # Parse using configparser (entry_points.txt uses INI format)
        config = configparser.ConfigParser()
        try:
            config.read_string(content)

            # Check for console_scripts section
            if config.has_section("console_scripts"):
                for key, value in config.items("console_scripts"):
                    scripts["console_scripts"].append(key)

            # Check for gui_scripts section
            if config.has_section("gui_scripts"):
                for key, value in config.items("gui_scripts"):
                    scripts["gui_scripts"].append(key)

            # Check other sections
            for section in config.sections():
                if section not in ["console_scripts", "gui_scripts"]:
                    for key, value in config.items(section):
                        scripts["other"].append(f"{section}:{key}")

        except:
            # Fallback: simple line-by-line parsing
            lines = content.split("\n")
            current_section = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                elif current_section and "=" in line:
                    key = line.split("=")[0].strip()
                    if current_section == "console_scripts":
                        scripts["console_scripts"].append(key)
                    elif current_section == "gui_scripts":
                        scripts["gui_scripts"].append(key)
                    else:
                        scripts["other"].append(f"{current_section}:{key}")

    except Exception as e:
        # If parsing fails, return empty
        pass

    return scripts


def scan_package(package_path: Path, site_dir: Path) -> Dict[str, any]:
    """
    Scan a single package directory for entry_points.txt and determine if pure Python.
    Returns dictionary with package information.
    """
    pkg_name = get_package_name_from_path(package_path)

    result = {
        "name": pkg_name,
        "has_entry_points": False,
        "entry_points_data": None,
        "is_pure_python": True,
        "error": None,
    }

    try:
        # Check for entry_points.txt in various locations
        entry_points_file = None

        # Check .dist-info directory
        dist_info_patterns = [
            f"{pkg_name}*.dist-info",
            f"{pkg_name.replace('-', '_')}*.dist-info",
            f"{pkg_name.replace('_', '-')}*.dist-info",
            f"{package_path.name}*.dist-info",
        ]

        for pattern in dist_info_patterns:
            for dist_info in site_dir.glob(pattern):
                if dist_info.is_dir():
                    ep_file = dist_info / "entry_points.txt"
                    if ep_file.exists():
                        entry_points_file = ep_file
                        break
            if entry_points_file:
                break

        # Check .egg-info directory
        if not entry_points_file:
            egg_info_patterns = [
                f"{pkg_name}*.egg-info",
                f"{pkg_name.replace('-', '_')}*.egg-info",
                f"{pkg_name.replace('_', '-')}*.egg-info",
                f"{package_path.name}*.egg-info",
            ]

            for pattern in egg_info_patterns:
                for egg_info in site_dir.glob(pattern):
                    if egg_info.is_dir():
                        ep_file = egg_info / "entry_points.txt"
                        if ep_file.exists():
                            entry_points_file = ep_file
                            break
                if entry_points_file:
                    break

        # Check if package directory itself has entry_points.txt
        if not entry_points_file and package_path.is_dir():
            ep_file = package_path / "entry_points.txt"
            if ep_file.exists():
                entry_points_file = ep_file

        # Parse entry points if found
        if entry_points_file:
            result["has_entry_points"] = True
            result["entry_points_data"] = parse_entry_points(entry_points_file)

        # Always determine pure status (for all packages)
        result["is_pure_python"] = is_pure_python_package(pkg_name, site_dir)

    except Exception as e:
        result["error"] = str(e)

    return result


def find_packages_categorized(site_dir: Path) -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Find all packages in a site directory and categorize them.
    Returns tuple:
    - pure_without_ep: Pure Python without entry_points
    - nonpure_without_ep: Non-pure without entry_points
    - pure_with_ep: Pure Python with entry_points
    - nonpure_with_ep: Non-pure with entry_points
    """
    pure_without_ep = []
    nonpure_without_ep = []
    pure_with_ep = []
    nonpure_with_ep = []
    processed_packages = set()  # Avoid duplicates

    try:
        # Collect all potential package markers
        items_to_scan = []

        # Look for package directories and metadata directories
        for item in site_dir.iterdir():
            if item.is_dir():
                # Skip if it's clearly not a package
                if item.name.startswith("_") or item.name.startswith("."):
                    continue

                # Check for __init__.py or it being metadata
                init_file = item / "__init__.py"
                is_package_dir = init_file.exists()
                is_metadata = item.suffix in [".dist-info", ".egg-info"]

                if is_package_dir or is_metadata:
                    items_to_scan.append(item)

        # Scan each item
        for item in items_to_scan:
            result = scan_package(item, site_dir)

            if result["error"] is None:
                pkg_name = result["name"]

                # Avoid duplicates
                if pkg_name in processed_packages:
                    continue
                processed_packages.add(pkg_name)

                # Categorize based on entry_points and purity
                if result["has_entry_points"]:
                    if result["is_pure_python"]:
                        pure_with_ep.append(pkg_name)
                    else:
                        nonpure_with_ep.append(pkg_name)
                else:
                    if result["is_pure_python"]:
                        pure_without_ep.append(pkg_name)
                    else:
                        nonpure_without_ep.append(pkg_name)
            elif result["error"]:
                print(f"Error scanning {item}: {result['error']}", file=sys.stderr)

    except Exception as e:
        print(f"Error scanning directory {site_dir}: {e}", file=sys.stderr)

    return pure_without_ep, nonpure_without_ep, pure_with_ep, nonpure_with_ep


def main():
    parser = argparse.ArgumentParser(
        description="Find Python packages and categorize by entry_points.txt and purity (Linux/Termux optimized)"
    )
    parser.add_argument(
        "--pure-noep-output",
        default="noep_pure.txt",
        help="Output file for pure Python packages without entry_points (default: noep_pure.txt)",
    )
    parser.add_argument(
        "--nonpure-noep-output",
        default="noep_nopure.txt",
        help="Output file for non-pure packages without entry_points (default: noep_nopure.txt)",
    )
    parser.add_argument(
        "--pure-ep-output",
        default="ep_pure.txt",
        help="Output file for pure Python packages with entry_points (default: ep_pure.txt)",
    )
    parser.add_argument(
        "--nonpure-ep-output",
        default="ep_nopure.txt",
        help="Output file for non-pure packages with entry_points (default: ep_nopure.txt)",
    )
    parser.add_argument(
        "--ep-details-output",
        default="ep_details.txt",
        help="Output file for detailed entry_points information (default: ep_details.txt)",
    )
    parser.add_argument("-j", "--json", action="store_true", help="Output in JSON format")
    parser.add_argument(
        "-p", "--processes", type=int, default=None, help=f"Number of processes to use (default: {cpu_count()})"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output")

    args = parser.parse_args()

    # Get site directories
    site_dirs = get_site_packages_dirs()

    if not site_dirs:
        print("No site-packages directories found!", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Found site directories: {[str(d) for d in site_dirs]}")
        print(f"Python version: {sys.version}")
        print(f"Platform: {sys.platform}")

    # Use multiprocessing to scan directories in parallel
    num_processes = args.processes or cpu_count()

    if args.verbose:
        print(f"Using {num_processes} processes")

    all_pure_noep = []
    all_nonpure_noep = []
    all_pure_ep = []
    all_nonpure_ep = []
    all_packages_with_ep_details = []

    with Pool(processes=num_processes) as pool:
        # Map site directories to processes
        results = pool.map(find_packages_categorized, site_dirs)

        # Flatten results
        for pure_noep, nonpure_noep, pure_ep, nonpure_ep in results:
            all_pure_noep.extend(pure_noep)
            all_nonpure_noep.extend(nonpure_noep)
            all_pure_ep.extend(pure_ep)
            all_nonpure_ep.extend(nonpure_ep)

    # Remove duplicates while preserving order
    def deduplicate(lst):
        seen = set()
        unique = []
        for item in lst:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return unique

    unique_pure_noep = deduplicate(all_pure_noep)
    unique_nonpure_noep = deduplicate(all_nonpure_noep)
    unique_pure_ep = deduplicate(all_pure_ep)
    unique_nonpure_ep = deduplicate(all_nonpure_ep)

    # Sort results for consistency
    unique_pure_noep.sort()
    unique_nonpure_noep.sort()
    unique_pure_ep.sort()
    unique_nonpure_ep.sort()

    # Write pure Python without entry_points
    if args.json:
        data = {
            "timestamp": datetime.now().isoformat(),
            "site_directories": [str(d) for d in site_dirs],
            "platform": sys.platform,
            "total": len(unique_pure_noep),
            "packages": unique_pure_noep,
        }
        Path(args.pure_noep_output).write_text(json.dumps(data, indent=2))
    else:
        Path(args.pure_noep_output).write_text("\n".join(unique_pure_noep))

    # Write non-pure without entry_points
    if args.json:
        data = {
            "timestamp": datetime.now().isoformat(),
            "site_directories": [str(d) for d in site_dirs],
            "platform": sys.platform,
            "total": len(unique_nonpure_noep),
            "packages": unique_nonpure_noep,
        }
        Path(args.nonpure_noep_output).write_text(json.dumps(data, indent=2))
    else:
        Path(args.nonpure_noep_output).write_text("\n".join(unique_nonpure_noep))

    # Write pure Python with entry_points
    if args.json:
        data = {
            "timestamp": datetime.now().isoformat(),
            "site_directories": [str(d) for d in site_dirs],
            "platform": sys.platform,
            "total": len(unique_pure_ep),
            "packages": unique_pure_ep,
        }
        Path(args.pure_ep_output).write_text(json.dumps(data, indent=2))
    else:
        Path(args.pure_ep_output).write_text("\n".join(unique_pure_ep))

    # Write non-pure with entry_points
    if args.json:
        data = {
            "timestamp": datetime.now().isoformat(),
            "site_directories": [str(d) for d in site_dirs],
            "platform": sys.platform,
            "total": len(unique_nonpure_ep),
            "packages": unique_nonpure_ep,
        }
        Path(args.nonpure_ep_output).write_text(json.dumps(data, indent=2))
    else:
        Path(args.nonpure_ep_output).write_text("\n".join(unique_nonpure_ep))

    # Write detailed entry_points information for all packages with entry points
    # We need to re-scan to get details (could optimize but fine for now)
    if args.verbose:
        print("\nGathering entry points details...")

    # Collect entry point details for all packages with EP
    ep_details = []
    with Pool(processes=num_processes) as pool:
        # Need to scan again for details - could be optimized but works
        results = pool.map(scan_for_entry_points, site_dirs)
        for details in results:
            ep_details.extend(details)

    # Deduplicate and sort
    seen_ep = set()
    unique_ep_details = []
    for pkg in ep_details:
        if pkg["name"] not in seen_ep:
            seen_ep.add(pkg["name"])
            unique_ep_details.append(pkg)
    unique_ep_details.sort(key=lambda x: x["name"])

    # Write entry points details
    if args.json:
        data = {
            "timestamp": datetime.now().isoformat(),
            "site_directories": [str(d) for d in site_dirs],
            "platform": sys.platform,
            "total": len(unique_ep_details),
            "packages": unique_ep_details,
        }
        Path(args.ep_details_output).write_text(json.dumps(data, indent=2))
    else:
        lines = []
        for pkg in unique_ep_details:
            lines.append(f"{pkg['name']}:")
            if pkg["entry_points"]["console_scripts"]:
                lines.append(f"  console_scripts: {', '.join(pkg['entry_points']['console_scripts'])}")
            if pkg["entry_points"]["gui_scripts"]:
                lines.append(f"  gui_scripts: {', '.join(pkg['entry_points']['gui_scripts'])}")
            if pkg["entry_points"]["other"]:
                lines.append(f"  other: {', '.join(pkg['entry_points']['other'])}")
            lines.append("")
        Path(args.ep_details_output).write_text("\n".join(lines))

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"SUMMARY - Python Package Classification")
    print(f"{'=' * 50}")
    print(f"Platform: {sys.platform}")
    print(f"Site directories: {len(site_dirs)}")
    print()
    print(f"Without entry_points.txt:")
    print(f"  • Pure Python packages: {len(unique_pure_noep)}")
    print(f"  • Non-pure packages:    {len(unique_nonpure_noep)}")
    print(f"  • Subtotal:             {len(unique_pure_noep) + len(unique_nonpure_noep)}")
    print()
    print(f"With entry_points.txt:")
    print(f"  • Pure Python packages: {len(unique_pure_ep)}")
    print(f"  • Non-pure packages:    {len(unique_nonpure_ep)}")
    print(f"  • Subtotal:             {len(unique_pure_ep) + len(unique_nonpure_ep)}")
    print()
    print(
        f"Grand total: {len(unique_pure_noep) + len(unique_nonpure_noep) + len(unique_pure_ep) + len(unique_nonpure_ep)}"
    )
    print(f"{'=' * 50}")

    if args.verbose:
        print(f"\nOutput files:")
        print(f"  Pure no-ep:      {args.pure_noep_output}")
        print(f"  Non-pure no-ep:  {args.nonpure_noep_output}")
        print(f"  Pure with ep:    {args.pure_ep_output}")
        print(f"  Non-pure with ep:{args.nonpure_ep_output}")
        print(f"  EP details:      {args.ep_details_output}")

        if unique_pure_noep:
            print(f"\nSample - Pure packages without EP (first 5):")
            for pkg in unique_pure_noep[:5]:
                print(f"  {pkg}")
            if len(unique_pure_noep) > 5:
                print(f"  ... and {len(unique_pure_noep) - 5} more")

        if unique_pure_ep:
            print(f"\nSample - Pure packages with EP (first 5):")
            for pkg in unique_pure_ep[:5]:
                print(f"  {pkg}")
            if len(unique_pure_ep) > 5:
                print(f"  ... and {len(unique_pure_ep) - 5} more")


def scan_for_entry_points(site_dir: Path) -> List[Dict]:
    """Helper function to get entry points details for all packages."""
    packages_with_ep = []
    processed = set()

    try:
        for item in site_dir.iterdir():
            if not item.is_dir() or item.name.startswith("_") or item.name.startswith("."):
                continue

            init_file = item / "__init__.py"
            is_package = init_file.exists() or item.suffix in [".dist-info", ".egg-info"]

            if is_package:
                result = scan_package(item, site_dir)
                if result["error"] is None and result["has_entry_points"]:
                    pkg_name = result["name"]
                    if pkg_name not in processed:
                        processed.add(pkg_name)
                        packages_with_ep.append({"name": pkg_name, "entry_points": result["entry_points_data"]})
    except:
        pass

    return packages_with_ep


if __name__ == "__main__":
    main()
