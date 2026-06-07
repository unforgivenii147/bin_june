#!/data/data/com.termux/files/usr/bin/python

import subprocess
import sys


def get_installed_packages():
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f='${Package}\t${Status}\t${Version}\n'"], capture_output=True, text=True, check=True
        )
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        print(f"Error listing installed packages: {e.stderr}")
        sys.exit(1)


def check_package_health(package_name):
    try:
        result = subprocess.run(["dpkg", "-l", package_name], capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        for line in lines:
            if package_name in line:
                status = line.split()[0]
                if status.startswith("ii"):
                    return (True, "OK")
                return (False, f"Status: {status}")
    except subprocess.CalledProcessError as e:
        return (False, f"Error checking package: {e.stderr}")


def check_for_updates():
    try:
        result = subprocess.run(["apt-get", "-s", "upgrade"], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error checking for updates: {e.stderr}"


def main():
    print("=== Installed Packages Sanity Check ===")
    installed_pkgs = get_installed_packages()
    print(f"Found {len(installed_pkgs)} installed packages.\n")
    issues_found = 0
    for pkg_info in installed_pkgs:
        pkg_name, _status, _version = pkg_info.split("\t")
        pkg_name = pkg_name.strip("'")
        is_ok, msg = check_package_health(pkg_name)
        if not is_ok:
            print(f"[!] {pkg_name}: {msg}")
            issues_found += 1
    print("\n=== Update Check ===")
    update_info = check_for_updates()
    if "0 upgraded, 0 newly installed" in update_info:
        print("All packages are up to date.")
    else:
        print("Updates are available. Run 'sudo apt-get upgrade' to update.")
        print("--- Update Info ---")
        print(update_info)
    print("\n=== Summary ===")
    print(f"Issues found: {issues_found}")
    if issues_found == 0:
        print("All packages are properly installed.")
    else:
        print("Some packages may need attention.")


if __name__ == "__main__":
    main()
