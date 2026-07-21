#!/data/data/com.termux/files/usr/bin/env python
from typing import Optional
"""
Generate a Cargo.toml file from a Cargo.lock file.
Reads package information from Cargo.lock and creates a basic Cargo.toml
with all dependencies listed.
"""

import re
import sys
from pathlib import Path
from typing import List, Dict


def parse_cargo_lock(filepath: str) -> Dict:
    """
    Parse a Cargo.lock file and extract package information.

    Args:
        filepath: Path to the Cargo.lock file

    Returns:
        Dictionary containing parsed data with keys: 'version', 'packages'
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse the lock file version
    version_match = re.search(r"^version\s*=\s*(\d+)", content, re.MULTILINE)
    lock_version = int(version_match.group(1)) if version_match else 3

    packages = []

    if lock_version >= 2:
        # For lock file version 2+, packages are in [[package]] sections
        package_blocks = re.split(r"\n\[\[package\]\]\n", content)
        # Skip the first block (metadata before first package)
        for block in package_blocks[1:]:
            pkg = parse_package_block(block)
            if pkg:
                packages.append(pkg)
    else:
        # For lock file version 1, packages are in [[package]] sections
        # but format is slightly different
        package_blocks = re.split(r"\n\[\[package\]\]\n", content)
        for block in package_blocks[1:]:
            pkg = parse_package_block_v1(block)
            if pkg:
                packages.append(pkg)

    return {"version": lock_version, "packages": packages}


def parse_package_block(block: str) -> Optional[Dict]:
    """
    Parse a package block from Cargo.lock v2+.

    Args:
        block: String containing package information

    Returns:
        Dictionary with package details or None if parsing fails
    """
    pkg = {}

    # Extract fields
    name_match = re.search(r'^name\s*=\s*"([^"]*)"', block, re.MULTILINE)
    version_match = re.search(r'^version\s*=\s*"([^"]*)"', block, re.MULTILINE)
    source_match = re.search(r'^source\s*=\s*"([^"]*)"', block, re.MULTILINE)

    if not name_match or not version_match:
        return None

    pkg["name"] = name_match.group(1)
    pkg["version"] = version_match.group(1)

    if source_match:
        pkg["source"] = source_match.group(1)

    # Extract dependencies if present
    dependencies = []
    dep_section = False
    for line in block.split("\n"):
        if line.strip().startswith("dependencies = ["):
            dep_section = True
            # Extract inline dependencies
            deps = re.findall(r'"([^"]*)"', line)
            dependencies.extend(deps)
            if "]" in line:
                dep_section = False
        elif dep_section:
            deps = re.findall(r'"([^"]*)"', line)
            dependencies.extend(deps)
            if "]" in line:
                dep_section = False

    if dependencies:
        pkg["dependencies"] = dependencies

    return pkg


def parse_package_block_v1(block: str) -> Optional[Dict]:
    """
    Parse a package block from Cargo.lock v1.

    Args:
        block: String containing package information

    Returns:
        Dictionary with package details or None if parsing fails
    """
    pkg = {}

    name_match = re.search(r'^name\s*=\s*"([^"]*)"', block, re.MULTILINE)
    version_match = re.search(r'^version\s*=\s*"([^"]*)"', block, re.MULTILINE)

    if not name_match or not version_match:
        return None

    pkg["name"] = name_match.group(1)
    pkg["version"] = version_match.group(1)

    # In v1, dependencies are listed differently
    dependencies = []
    for line in block.split("\n"):
        dep_match = re.match(r'^\s*"([^"]+)\s+([^"]+)"', line)
        if dep_match:
            dependencies.append(f"{dep_match.group(1)} {dep_match.group(2)}")

    if dependencies:
        pkg["dependencies"] = dependencies

    return pkg


def generate_cargo_toml(
    packages: List[Dict],
    root_package_name: Optional[str] = None,
    root_version: str = "0.1.0",
    include_dev_deps: bool = False,
) -> str:
    """
    Generate Cargo.toml content from parsed package data.

    Args:
        packages: List of parsed package dictionaries
        root_package_name: Name for the root package (optional)
        root_version: Version for the root package
        include_dev_deps: Whether to include dependencies from dev-dependencies

    Returns:
        String containing Cargo.toml content
    """
    lines = []

    # Add package section
    lines.append("[package]")
    if root_package_name:
        lines.append(f'name = "{root_package_name}"')
    else:
        # Use the first package as root if no name provided
        if packages:
            lines.append(f'name = "{packages[0]["name"]}"')
        else:
            lines.append('name = "generated-project"')

    lines.append(f'version = "{root_version}"')
    lines.append('edition = "2021"')
    lines.append("")

    # Add dependencies
    if packages:
        lines.append("[dependencies]")

        root_deps = set()
        if packages and "dependencies" in packages[0]:
            root_deps.update(packages[0]["dependencies"])

        if root_deps:
            # Find the actual dependency packages and their versions
            for dep_name in root_deps:
                dep_pkg = find_package(packages, dep_name)
                if dep_pkg:
                    lines.append(f'{dep_pkg["name"]} = "{dep_pkg["version"]}"')
                else:
                    lines.append(f'{dep_name} = "*"  # Version not found in lock file')
        else:
            # If no direct deps found, add all packages as dependencies
            # excluding the first one (which is likely the root)
            for pkg in packages[1:]:
                lines.append(f'{pkg["name"]} = "{pkg["version"]}"')

    return "\n".join(lines)


def find_package(packages: List[Dict], name: str) -> Optional[Dict]:
    """
    Find a package by name in the packages list.

    Args:
        packages: List of package dictionaries
        name: Package name to find

    Returns:
        Package dictionary or None if not found
    """
    for pkg in packages:
        if pkg["name"] == name:
            return pkg
    return None


def main():
    """Main function to run the script."""
    lock_file = "Cargo.lock"

    # Allow specifying a different lock file
    if len(sys.argv) > 1:
        lock_file = sys.argv[1]

    if not Path(lock_file).exists():
        print(f"Error: {lock_file} not found!")
        sys.exit(1)

    print(f"Parsing {lock_file}...")
    data = parse_cargo_lock(lock_file)

    if not data["packages"]:
        print("No packages found in lock file!")
        sys.exit(1)

    print(f"Found {len(data['packages'])} packages (lock file v{data['version']})")

    # Generate Cargo.toml
    toml_content = generate_cargo_toml(
        data["packages"],
        root_package_name=None,  # Will use first package name
        root_version="0.1.0",
    )

    # Write to Cargo.toml
    output_file = "Cargo.toml"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(toml_content)

    print(f"Generated {output_file}")
    print("\nPreview:")
    print("-" * 50)
    print(toml_content)


if __name__ == "__main__":
    main()
