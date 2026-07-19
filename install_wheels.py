#!/data/data/com.termux/files/usr/bin/env python
"""
Install Python wheels with platform-aware installation strategy.
Pure Python wheels -> user site-packages
Platform-specific wheels -> system site-packages
"""

from __future__ import annotations

import platform
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Tuple


def is_pure_python_wheel(wheel_path: Path) -> bool:
    """Check if a wheel is pure Python by inspecting its filename and metadata."""
    wheel_name = wheel_path.stem
    if "-none-any" in wheel_name:
        return True

    # Method 2: Inspect WHEEL metadata file inside the wheel
    try:
        with zipfile.ZipFile(wheel_path, "r") as zf:
            # Look for WHEEL metadata file
            for name in zf.namelist():
                if name.endswith(".dist-info/WHEEL") or name.endswith(".dist-info/METADATA"):
                    with zf.open(name) as f:
                        content = f.read().decode("utf-8")
                        # Check if Root-Is-Purelib is true
                        if "Root-Is-Purelib: true" in content:
                            return True
                        if "Root-Is-Purelib: false" in content:
                            return False
    except Exception as e:
        print(f"Warning: Could not inspect {wheel_path.name}: {e}")

    # Method 3: Check if wheel contains platform-specific extensions
    try:
        with zipfile.ZipFile(wheel_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith((".so", ".pyd", ".dll", ".dylib")):
                    return False
        return True
    except Exception as e:
        print(f"Warning: Could not inspect {wheel_path.name}: {e}")
        return False


def install_wheel(wheel_path: Path, user_install: bool) -> Tuple[Path, bool, str]:
    """Install a single wheel and return status."""
    try:
        install_flag = "--user" if user_install else ""
        cmd = [sys.executable, "-m", "pip", "install", str(wheel_path)]

        if user_install:
            cmd.insert(3, "--user")

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        install_type = "user site-packages" if user_install else "system site-packages"
        return wheel_path, True, f"✓ {wheel_path.name} -> {install_type}"

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        return wheel_path, False, f"✗ {wheel_path.name}: {error_msg}"
    except Exception as e:
        return wheel_path, False, f"✗ {wheel_path.name}: {e!s}"


def get_wheel_type(wheel_path: Path) -> str:
    """Determine wheel type for display purposes."""
    try:
        wheel_name = wheel_path.stem
        parts = wheel_name.split("-")
        if len(parts) >= 4:
            platform_tag = parts[-1]
            if "none-any" in wheel_name:
                return "Pure Python (any platform)"
            elif "android" in platform_tag.lower():
                return f"Android-specific ({platform_tag})"
            elif "linux" in platform_tag.lower():
                return f"Linux-specific ({platform_tag})"
            else:
                return f"Platform-specific ({platform_tag})"
    except:
        pass
    return "Unknown"


def main():
    # Get current directory
    current_dir = Path.cwd()

    # Find all .whl files
    wheel_files = list(current_dir.glob("*.whl"))

    if not wheel_files:
        print("No .whl files found in current directory.")
        return

    print(f"Found {len(wheel_files)} wheel(s) in {current_dir}")
    print(f"Python version: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print("=" * 60)

    # Analyze wheels
    install_tasks = []

    for wheel in wheel_files:
        is_pure = is_pure_python_wheel(wheel)
        wheel_type = get_wheel_type(wheel)
        install_type = "USER site-packages" if is_pure else "SYSTEM site-packages"

        print(f"Analyzing: {wheel.name}")
        print(f"  Type: {wheel_type}")
        print(f"  Target: {install_type}")

        install_tasks.append((wheel, is_pure))

    print("\n" + "=" * 60)
    print("Starting parallel installation...")
    print("=" * 60)

    # Install wheels in parallel
    successful = []
    failed = []

    max_workers = min(4, len(wheel_files))  # Limit concurrent installations

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all installation tasks
        future_to_wheel = {executor.submit(install_wheel, wheel, is_pure): wheel for wheel, is_pure in install_tasks}

        # Process completed installations
        for future in as_completed(future_to_wheel):
            wheel = future_to_wheel[future]
            try:
                wheel_path, success, message = future.result()
                print(message)

                if success:
                    successful.append(wheel_path)
                else:
                    failed.append((wheel_path, message))
            except Exception as e:
                print(f"✗ Error processing {wheel.name}: {e}")
                failed.append((wheel, str(e)))

    # Print summary
    print("\n" + "=" * 60)
    print("INSTALLATION SUMMARY")
    print("=" * 60)
    print(f"Total wheels: {len(wheel_files)}")
    print(f"✓ Successfully installed: {len(successful)}")
    print(f"✗ Failed: {len(failed)}")

    if successful:
        print("\nSuccessfully installed:")
        for wheel in successful:
            is_pure = is_pure_python_wheel(wheel)
            location = "user site" if is_pure else "system site"
            print(f"  ✓ {wheel.name} -> {location}")

    if failed:
        print("\nFailed installations:")
        for wheel, error in failed:
            print(f"  ✗ {wheel.name}: {error}")

    print("\nDone!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInstallation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
