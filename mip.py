#!/data/data/com.termux/files/usr/bin/python
import importlib.metadata
import sys
import zipfile
from pathlib import Path


def parse_version_tuple(version_str: str) -> tuple:
    """Splits version string into numeric parts for safe numeric comparison.

    Example: '2.28.1' -> (2, 28, 1)
    """
    try:
        return tuple(int(x) for x in version_str.split(".") if x.isdigit())
    except Exception:
        # Fallback to standard string comparison if format is non-standard
        return (version_str,)


def get_files(directory: Path, ext: list[str]) -> list[Path]:
    """Finds all files with matching extensions in the directory (non-recursive)."""
    return [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in ext]


def get_installed_packages() -> dict[str, str]:
    """Retrieves all installed packages in the current environment using standard libraries.

       Returns: {"package-name": "version"}
    x"""
    # Normalize names to lowercase to prevent casing mismatches (e.g. PyYAML vs pyyaml)
    return {dist.metadata["Name"].lower(): dist.version for dist in importlib.metadata.distributions()}


def get_wheel_package_info(
    path: Path,
) -> tuple[str, str] | tuple[None, None]:
    """Extracts package name and version from the wheel's internal METADATA file."""
    try:
        with zipfile.ZipFile(path, "r") as zip_ref:
            # Locate the METADATA file inside the .dist-info folder
            metadata_file = next((f for f in zip_ref.namelist() if f.endswith("METADATA")), None)

            if metadata_file:
                pkg_name, pkg_version = None, None
                with zip_ref.open(metadata_file) as f:
                    # Read line by line instead of reading the whole block to optimize memory
                    for line in f:
                        line_str = line.decode("utf-8", errors="ignore")
                        if line_str.startswith("Name:"):
                            pkg_name = line_str.split(":", 1)[1].strip()
                        elif line_str.startswith("Version:"):
                            pkg_version = line_str.split(":", 1)[1].strip()

                        # Exit early if both variables are populated
                        if pkg_name and pkg_version:
                            return (pkg_name, pkg_version)
    except Exception as e:
        print(f"Error reading {path.name}: {e}")
    return (None, None)


def main() -> None:
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".whl"])

    if not files:
        print("Run this script in a directory containing .whl files.")
        sys.exit(1)

    # Get a dictionary of installed packages
    installed = get_installed_packages()

    for path in files:
        pkg_name, pkg_version = get_wheel_package_info(path)

        if pkg_name and pkg_version:
            # Query the dictionary using normalized lowercase naming
            installed_version = installed.get(pkg_name.lower())

            if installed_version:
                # Safe version parsing for proper comparison loops
                v_installed = parse_version_tuple(installed_version)
                v_wheel = parse_version_tuple(pkg_version)

                if v_installed == v_wheel:
                    print(f"🗑️  {pkg_name} == {pkg_version} already installed, deleting {path.name}")
                    path.unlink()

                elif v_installed > v_wheel:
                    print(
                        f"🗑️  Installed version ({installed_version}) is newer than wheel ({pkg_version}), deleting {path.name}"
                    )
                    path.unlink()


if __name__ == "__main__":
    main()
