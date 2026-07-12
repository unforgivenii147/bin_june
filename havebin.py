#!/data/data/com.termux/files/usr/bin/env python
import os
import subprocess

from Pathlib import Path


from pathlib import Path


def get_file_age(path: (str | Path), str_mode: bool = False) -> float | str:
    from os import stat as os_stat
    from time import time as time_time

    path = Path(path)
    current_time = time_time()
    file_stat = os_stat(path)
    file_creation_time = file_stat.st_ctime
    age = current_time - file_creation_time
    int_age = int(age)
    if not str_mode:
        if not path.exists():
            return 0.0
        if not path.is_file():
            return -1.0
        return age
    if int_age < 0:
        return "0 sec"
    units = [
        ("y", 365 * 24 * 60 * 60),
        ("m", 30 * 24 * 60 * 60),
        ("d", 24 * 60 * 60),
        ("h", 60 * 60),
        ("min", 60),
        ("sec", 1),
    ]
    parts = []
    for name, seconds_per_unit in units:
        value, int_age = divmod(int_age, seconds_per_unit)
        if value:
            parts.append(f"{value} {name}")
    return ", ".join(parts) if parts else "0 sec"


def get_installed_pkgs():
    packages = []
    pip_freeze_path = Path("/sdcard/data/pip.freeze")
    file_age = get_file_age(pip_freeze_path)
    if file_age < 60 * 60 * 24:
        lines = pip_freeze_path.read_text(encoding="utf8").splitlines(keepends=False)
        for line in lines:
            if not line.startswith("#") and "==" in line:
                name, _ = line.split("==", 1)
                packages.append(name)
        return packages
    from importlib.metadata import distributions

    for dist in distributions():
        meta = dist.metadata
        name = meta.get("Name") or meta.get("name")
        if not name:
            continue
        name = name.strip()
        packages.append(name)
    return packages


get_ipkgs = get_installed_pkgs


def find_packages_with_bin_scripts(output_file: str = "have_scripts.txt") -> None:
    print("Starting search for packages with 'bin' scripts...")
    try:
        installed_packages = get_ipkgs()
        if not installed_packages:
            print("No Python packages found via 'pip list'. Please ensure pip is installed and accessible.")
            return
        print(f"Found {len(installed_packages)} installed packages. Checking each for 'bin' scripts...")
        packages_with_scripts = []
        total_packages = len(installed_packages)
        for i, package_name in enumerate(installed_packages):
            print(f"[{i + 1}/{total_packages}] Checking '{package_name}'...", end="\r")
            try:
                result = subprocess.run(
                    ["pip", "show", "-f", package_name],
                    capture_output=True,
                    text=True,
                    check=True,
                    encoding="utf-8",
                    errors="ignore",
                )
                lines = result.stdout.split("\n")
                bin_indicators = [os.path.join(os.sep, "bin", ""), os.path.join("bin", ""), os.path.join("scripts", "")]
                found_script_in_bin = False
                for line in lines:
                    line = line.strip()
                    if line.startswith("Location:"):
                        continue
                    if line.startswith("Files:"):
                        continue
                    for indicator in bin_indicators:
                        if (
                            indicator in line.lower()
                            and (
                                line.endswith(".py")
                                or os.path.splitext(line)[1] == ""
                                or os.path.splitext(line)[1] == ".exe"
                            )
                            and not any(
                                exclude_part in line
                                for exclude_part in ["__pycache__", ".dist-info", ".egg-info", ".pth"]
                            )
                        ):
                            found_script_in_bin = True
                            break
                    if found_script_in_bin:
                        break
                if found_script_in_bin:
                    packages_with_scripts.append(package_name)
            except subprocess.CalledProcessError:
                pass
            except Exception as e:
                print(f"\nAn unexpected error occurred while checking '{package_name}': {e}")
        with Path(output_file).open("w", encoding="utf-8") as f:
            f.writelines(pkg + "\n" for pkg in packages_with_scripts)
        print(f"\nSearch complete. Found {len(packages_with_scripts)} packages with 'bin' scripts.")
        print(f"List saved to '{output_file}'.")
    except FileNotFoundError:
        print("Error: 'pip' command not found. Please ensure Python and pip are installed and in your PATH.")
    except subprocess.CalledProcessError as e:
        print(f"Error running pip command: {e.cmd}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    find_packages_with_bin_scripts()
