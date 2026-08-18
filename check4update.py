#!/data/data/com.termux/files/home/.local/bin/python
"""
Check installed packages for available updates using parallel processing.
Saves upgradable packages to upgradable.txt
"""

from __future__ import annotations
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple


def get_installed_packages(site_dir: Path) -> List[Dict[str, str]]:
    packages = []
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json", "--path", str(site_dir)],
            capture_output=True,
            text=True,
            check=True,
        )
        packages = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error listing packages: {e.stderr}")
    except json.JSONDecodeError as e:
        print(f"Error parsing package list: {e}")
    return packages


def check_package_update(package_info: Dict[str, str]) -> Tuple[str, str, str, bool]:
    package_name = package_info["name"]
    current_version = package_info["version"]
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--dry-run", "--quiet", f"{package_name}==latest"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        result = subprocess.run(
            [sys.executable, "-m", "pip", "index", "versions", package_name], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if "Available versions:" in line:
                    versions_str = line.split("Available versions:")[1].strip()
                    versions = [v.strip() for v in versions_str.split(",")]
                    if versions:
                        latest_version = versions[0]
                        if current_version != latest_version:
                            return (package_name, current_version, latest_version, True)
                        break
    except subprocess.TimeoutExpired:
        print(f"Timeout checking {package_name}")
    except Exception as e:
        print(f"Error checking {package_name}: {e}")
    return (package_name, current_version, current_version, False)


def check_updates_parallel(packages: List[Dict[str, str]], max_workers: int = 8) -> List[Tuple[str, str, str]]:
    upgradable = []
    print(f"Checking {len(packages)} packages for updates using {max_workers} workers...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_package = {executor.submit(check_package_update, pkg): pkg["name"] for pkg in packages}
        completed = 0
        for future in as_completed(future_to_package):
            package_name = future_to_package[future]
            completed += 1
            try:
                result = future.result()
                name, current_ver, latest_ver, has_update = result
                if has_update:
                    upgradable.append((name, current_ver, latest_ver))
                    print(f"[{completed}/{len(packages)}] {name}: {current_ver} -> {latest_ver} (UPDATE AVAILABLE)")
                else:
                    print(f"[{completed}/{len(packages)}] {name}: {current_ver} (up-to-date)")
            except Exception as e:
                print(f"[{completed}/{len(packages)}] Error processing {package_name}: {e}")
    return upgradable


def save_upgradable_packages(upgradable: List[Tuple[str, str, str]], output_file: Path):
    try:
        with open(output_file, "w") as f:
            f.write("# Packages with available updates\n")
            f.write(f"# Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("# Format: package_name current_version -> latest_version\n\n")
            for name, current_ver, latest_ver in upgradable:
                f.write(f"{name}=={current_ver}  # -> {latest_ver}\n")
        print(f"\nResults saved to {output_file}")
        print(f"Found {len(upgradable)} packages with available updates")
    except IOError as e:
        print(f"Error saving results to {output_file}: {e}")


def find_site_packages() -> List[Path]:
    site_dirs = []
    result = subprocess.run(
        [sys.executable, "-c", 'import site; print("\\n".join(site.getsitepackages()))'],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.strip().split("\n"):
        path = Path(line.strip())
        if path.exists():
            site_dirs.append(path)
    result = subprocess.run(
        [sys.executable, "-c", "import site; print(site.getusersitepackages())"],
        capture_output=True,
        text=True,
        check=True,
    )
    user_site = Path(result.stdout.strip())
    if user_site.exists() and user_site not in site_dirs:
        site_dirs.append(user_site)
    return site_dirs


def main():
    print("Python Package Update Checker")
    print("-" * 42)
    site_dirs = find_site_packages()
    if not site_dirs:
        print("No site-packages directories found!")
        sys.exit(1)
    print(f"Found {len(site_dirs)} site-packages directories:")
    for site_dir in site_dirs:
        print(f"  - {site_dir}")
    all_packages = []
    for site_dir in site_dirs:
        print(f"\nScanning {site_dir}...")
        packages = get_installed_packages(site_dir)
        print(f"  Found {len(packages)} packages")
        all_packages.extend(packages)
    if not all_packages:
        print("No packages found!")
        sys.exit(1)
    seen = set()
    unique_packages = []
    for pkg in all_packages:
        if pkg["name"] not in seen:
            seen.add(pkg["name"])
            unique_packages.append(pkg)
    print(f"\nTotal unique packages to check: {len(unique_packages)}")
    upgradable = check_updates_parallel(unique_packages, max_workers=20)
    output_file = Path.cwd() / "upgradable.txt"
    save_upgradable_packages(upgradable, output_file)
    print("\n" + "=" * 42)
    print("Summary:")
    print(f"  Total packages checked: {len(unique_packages)}")
    print(f"  Updates available: {len(upgradable)}")
    print(f"  Up-to-date: {len(unique_packages) - len(upgradable)}")
    if upgradable:
        print("\nPackages with available updates:")
        for name, current_ver, latest_ver in upgradable:
            print(f"  {name}: {current_ver} -> {latest_ver}")


if __name__ == "__main__":
    main()
