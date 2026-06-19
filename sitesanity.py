#!/data/data/com.termux/files/usr/bin/python
import argparse
import importlib.metadata
import logging
import sys
from fnmatch import fnmatch
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def parse_arguments():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Sanity check installed Termux Python packages.")
    parser.add_argument(
        "-i",
        "--ignore",
        action="append",
        default=[],
        help="Glob pattern or filename to ignore when checking package files (e.g., '*.md'). Can be used multiple times.",
    )
    return parser.parse_args()


def should_ignore_file(file_path: Path, ignore_patterns: list[str]) -> bool:
    """Checks if a file should be ignored based on .pyc suffix or user glob patterns."""
    if file_path.suffix == ".pyc":
        return True

    name = file_path.name
    for pattern in ignore_patterns:
        if fnmatch(name, pattern):
            return True
    return False


def check_package_files(dist, ignore_patterns: list[str]) -> list[str]:
    """Verifies that non-ignored files declared in the package manifest exist on disk."""
    missing_files = []

    if dist.files is None:
        return missing_files

    for package_file in dist.files:
        file_path = Path(dist.locate_file(package_file))

        if should_ignore_file(file_path, ignore_patterns):
            continue

        if not file_path.exists():
            missing_files.append(str(package_file))

    return missing_files


def check_package_dependencies(dist, installed_map: dict[str, str]) -> tuple[list[str], list[str]]:
    """Validates ONLY core package dependency requirements against the current environment.

    Filters out environment extras, development flags, and testing packages.
    """
    broken_deps = []
    clean_reqs_for_file = []

    if dist.requires is None:
        return broken_deps, clean_reqs_for_file

    for req_str in dist.requires:
        # Ignore optional features, testing suites, or extra markers
        if "extra ==" in req_str or "extra =" in req_str:
            continue

        # Split baseline requirements from target marker parameters
        parts = req_str.split(";")
        base_requirement = parts[0].strip()

        # Isolate package name out of operational bounds (e.g., requests>=2.0 -> requests)
        dep_name = base_requirement
        for op in ["<", ">", "=", "!", "~"]:
            if op in dep_name:
                dep_name = dep_name.split(op)[0].strip()

        if not dep_name:
            continue

        # If the core package is missing, track it
        if dep_name.lower() not in installed_map:
            broken_deps.append(base_requirement)
            clean_reqs_for_file.append(base_requirement)

    return broken_deps, clean_reqs_for_file


def main():
    args = parse_arguments()
    logging.info("Starting Termux site-packages verification scan...\n")

    distributions = list(importlib.metadata.distributions())
    installed_map = {d.metadata["Name"].lower(): d.version for d in distributions}

    unique_missing_deps = set()
    corrupted_packages_count = 0
    broken_deps_count = 0

    for dist in distributions:
        pkg_name = dist.metadata["Name"]
        pkg_version = dist.version
        origin_path = getattr(dist, "_path", "Unknown Environment Space")

        # Check files and missing dependencies
        missing_files = check_package_files(dist, args.ignore)
        missing_deps, file_deps = check_package_dependencies(dist, installed_map)

        if missing_files or missing_deps:
            print(f"📦 PACKAGE: {pkg_name} ({pkg_version})")
            print(f"   Location Target: {origin_path}")

            if missing_files:
                corrupted_packages_count += 1
                print(f"   ❌ Missing Files ({len(missing_files)}):")
                for f in missing_files[:5]:
                    print(f"      - {f}")
                if len(missing_files) > 5:
                    print(f"      - ... and {len(missing_files) - 5} more files missing.")

            if missing_deps:
                broken_deps_count += 1
                print(f"   ⚠️  Unresolved Core Dependencies:")
                for dep in missing_deps:
                    print(f"      - Missing requirement: {dep}")

                # Save the cleaned requirements strings
                for clean_dep in file_deps:
                    unique_missing_deps.add(clean_dep)

            print("-" * 60)

    # Save clean dependencies to requirements.txt if found
    if unique_missing_deps:
        req_file = Path("requirements.txt")
        with open(req_file, "w", encoding="utf-8") as f:
            for dep in sorted(unique_missing_deps):
                f.write(f"{dep}\n")
        logging.info(f"📝 Saved {len(unique_missing_deps)} unique main dependencies to: {req_file.resolve()}")

    # Output Summary
    logging.info("=== SCAN SUMMARY ===")
    logging.info(f"Total packages evaluated: {len(distributions)}")
    logging.info(f"Packages with missing files: {corrupted_packages_count}")
    logging.info(f"Packages with missing dependencies: {broken_deps_count}")


if __name__ == "__main__":
    main()
