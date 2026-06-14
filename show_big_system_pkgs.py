#!/data/data/com.termux/files/usr/bin/python
import json
import re
import subprocess
import sys
from datetime import datetime
from functools import partial
from multiprocessing import Pool, cpu_count


def format_size(bytes_size) -> str:
    """Format bytes to human readable size"""
    if bytes_size == 0:
        return "N/A"

    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"


def parse_size(size_str: str) -> int:
    """Parse size string like '10.5 MB' or '1024 kB' to bytes"""
    size_str = size_str.strip()

    # Pattern matches: number followed by optional space and unit (KB, MB, etc)
    match = re.match(r"([\d.]+)\s*([KMGT]?)B?", size_str, re.IGNORECASE)
    if not match:
        return 0

    value = float(match.group(1))
    unit = match.group(2).upper()

    multipliers = {"": 1, "K": 1024, "M": 1024 * 1024, "G": 1024 * 1024 * 1024, "T": 1024 * 1024 * 1024 * 1024}

    return int(value * multipliers.get(unit, 1))


def get_all_packages():
    """Get list of all available packages using apt list"""
    try:
        print("📦 Fetching list of all available packages...")
        result = subprocess.run(["apt", "list", "--all-versions"], capture_output=True, text=True, check=True)

        packages = []
        lines = result.stdout.strip().split("\n")

        for line in lines:
            # Skip header and empty lines
            if line and not line.startswith("Listing") and "/" in line:
                # Extract package name (before the first '/')
                pkg_name = line.split("/", 1)[0]
                if pkg_name not in packages:  # Avoid duplicates
                    packages.append(pkg_name)

        return packages
    except subprocess.CalledProcessError as e:
        print(f"Error getting package list: {e}")
        return []


def get_package_info(package):
    """Get download size for a single package"""
    try:
        result = subprocess.run(
            ["apt", "show", package], capture_output=True, text=True, check=False, timeout=10
        )  # Timeout to avoid hanging

        if result.returncode != 0:
            return (package, 0, False)

        # Look for Download-Size line
        for line in result.stdout.split("\n"):
            if line.startswith("Download-Size:"):
                size_part = line.replace("Download-Size:", "").strip()
                size_bytes = parse_size(size_part)
                return (package, size_bytes, True)

        return (package, 0, False)
    except subprocess.TimeoutExpired:
        return (package, 0, False)
    except Exception:
        return (package, 0, False)


def process_packages_parallel(packages, threshold_bytes: int, num_processes: int | None = None):
    """Process packages in parallel using multiprocessing"""
    if num_processes is None:
        num_processes = min(cpu_count(), 8)  # Limit to 8 processes max

    print(f"🚀 Using {num_processes} parallel processes...")

    # Create a pool of workers
    with Pool(processes=num_processes) as pool:
        # Use imap_unordered for better performance with progress tracking
        results = []
        completed = 0
        total = len(packages)

        print(f"📊 Processing {total} packages...\n")

        # Process in chunks for better progress reporting
        for result in pool.imap_unordered(get_package_info, packages, chunksize=10):
            results.append(result)
            completed += 1

            # Update progress every 50 packages
            if completed % 50 == 0 or completed == total:
                progress = (completed / total) * 100
                print(f"⏳ Progress: {completed}/{total} ({progress:.1f}%)", end="\r")

        print("\n✅ Processing complete!                    \n")

        # Filter packages above threshold
        large_packages = {}
        all_packages = {}
        no_size = 0

        for pkg, size, has_info in results:
            if has_info and size > 0:
                all_packages[pkg] = size
                if size >= threshold_bytes:
                    large_packages[pkg] = size
            else:
                no_size += 1
                all_packages[pkg] = 0  # Store as 0 for packages with no size info

        return large_packages, all_packages, no_size, total


def save_json_results(data, filename: str, threshold_mb: float | int, include_all=False) -> bool:
    """Save results to JSON file"""
    output = {
        "metadata": {
            "threshold_mb": threshold_mb,
            "threshold_bytes": threshold_mb * 1024 * 1024,
            "scan_date": datetime.now().isoformat(),
            "total_packages": len(data.get("all_packages", {})),
            "packages_above_threshold": len(data.get("large_packages", {})),
        },
        "packages": data.get("large_packages", {}),
    }

    if include_all:
        output["all_packages"] = data.get("all_packages", {})

    try:
        with open(filename, "w") as f:
            json.dump(output, f, indent=2, sort_keys=True)
        return True
    except Exception as e:
        print(f"Error saving JSON: {e}")
        return False


def main() -> None:
    # Default threshold 10 MB
    default_threshold_mb = 10

    # Get threshold from command line if provided
    if len(sys.argv) > 1:
        try:
            threshold_mb = float(sys.argv[1])
        except ValueError:
            print(f"Error: Invalid threshold '{sys.argv[1]}'. Using default {default_threshold_mb}MB.")
            threshold_mb = default_threshold_mb
    else:
        threshold_mb = default_threshold_mb

    threshold_bytes = int(threshold_mb * 1024 * 1024)

    # Optional: specify number of processes
    num_processes = 12
    if len(sys.argv) > 2:
        try:
            num_processes = int(sys.argv[2])
        except ValueError:
            pass

    print(f"🔍 Scanning ALL available packages larger than {threshold_mb}MB...")
    print("=" * 35)

    # Get all available packages
    packages = get_all_packages()

    if not packages:
        print("❌ No packages found or error retrieving package list.")
        print("Make sure you have internet connection and run 'pkg update' first.")
        return

    print(f"📦 Found {len(packages)} available packages.")

    # Process packages in parallel
    large_packages, all_packages, no_size, total = process_packages_parallel(packages, threshold_bytes, num_processes)

    print("=" * 35)
    print(f"\n📊 RESULTS: Found {len(large_packages)} packages larger than {threshold_mb}MB")
    print("-" * 35)

    if large_packages:
        # Sort by size (largest first)
        sorted_packages = sorted(large_packages.items(), key=lambda x: x[1], reverse=True)

        total_size = 0
        print(f"{'PACKAGE NAME':<40} {'DOWNLOAD SIZE':>15}")
        print("-" * 35)

        # Show top 50 packages if there are many
        display_count = min(len(sorted_packages), 50)
        for i, (pkg, size) in enumerate(sorted_packages[:display_count]):
            print(f"{pkg:<40} {format_size(size):>15}")
            total_size += size

        if len(sorted_packages) > 50:
            print(f"\n... and {len(sorted_packages) - 50} more packages")
            # Calculate total size including remaining packages
            for _, size in sorted_packages[50:]:
                total_size += size

        print("-" * 35)
        print(f"{'TOTAL SIZE:':<40} {format_size(total_size):>15}")
        print(f"{'TOTAL PACKAGES:':<40} {len(large_packages):>15}")
    else:
        print("✅ No packages found exceeding the threshold.")

    print(f"\n📈 Statistics:")
    print(f"   Total packages checked: {total}")
    print(f"   Packages with size info: {total - no_size}")
    print(f"   Packages below threshold: {total - len(large_packages) - no_size}")
    print(f"   Packages with no size info: {no_size}")

    # Prepare data for JSON
    json_data = {"large_packages": large_packages, "all_packages": all_packages}

    # Always save JSON with packages above threshold
    if large_packages:
        json_filename = f"packages_above_{threshold_mb}mb.json"
        if save_json_results(json_data, json_filename, threshold_mb, include_all=False):
            print(f"\n💾 Results saved to: {json_filename}")
            print(f"   Format: {{'package_name': size_in_bytes}} for packages > {threshold_mb}MB")

    # Ask if user wants to save all packages (including smaller ones)
    save_all = input("\n💾 Save ALL packages (including smaller ones) to JSON? (y/n): ").lower()
    if save_all == "y":
        all_json_filename = f"all_packages_sizes.json"
        if save_json_results(json_data, all_json_filename, threshold_mb, include_all=True):
            print(f"✅ All packages saved to: {all_json_filename}")
            print(f"   Format: {{'package_name': size_in_bytes}} for ALL packages")

    # Also save a simple format (just {pkg: size} without metadata)
    save_simple = input("\n💾 Save simple JSON (just {package: size})? (y/n): ").lower()
    if save_simple == "y":
        simple_filename = f"packages_sizes_{threshold_mb}mb.json"
        try:
            with open(simple_filename, "w") as f:
                json.dump(large_packages, f, indent=2, sort_keys=True)
            print(f"✅ Simple JSON saved to: {simple_filename}")
            print(f'   Format: {{"package1": 12345678, "package2": 98765432}}')
        except Exception as e:
            print(f"Error saving simple JSON: {e}")


if __name__ == "__main__":
    # Required for multiprocessing on some platforms
    from multiprocessing import freeze_support

    freeze_support()
    main()
