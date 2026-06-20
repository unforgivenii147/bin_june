#!/data/data/com.termux/files/usr/bin/python
import csv
import os
import zipfile
from pathlib import Path


def is_empty_wheel(wheel_path: str) -> bool:
    print(f"checking {wheel_path}")
    try:
        with zipfile.ZipFile(wheel_path, "r") as z:
            # Find .dist-info directory (can be .dist-info or .dist-info/)
            dist_info_dirs = [
                name.rstrip("/")
                for name in z.namelist()
                if name.endswith(".dist-info/") or name == name.rstrip("/") + "/" and name.endswith(".dist-info")
            ]
            # Simpler: just check for any name containing .dist-info
            dist_info = next((name.rstrip("/") for name in z.namelist() if ".dist-info" in name), None)

            if not dist_info:
                return False

            record_path = f"{dist_info}/RECORD"
            if record_path not in z.namelist():
                return False

            # Check RECORD contents
            with z.open(record_path) as f:
                reader = csv.reader(line.decode("utf-8") for line in f)
                for row in reader:
                    if not row:
                        continue
                    file_path = row[0]
                    # If any file is outside .dist-info, it's not empty
                    if not file_path.startswith(f"{dist_info}/"):
                        return False

            return True

    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError):
        return False


def main() -> None:
    """Find and print empty wheel files in current directory."""
    # Use Path for cleaner file handling
    current_dir = Path(".")
    wheel_files = list(current_dir.glob("*.whl"))

    if not wheel_files:
        return

    empty_wheels = [str(w) for w in wheel_files if is_empty_wheel(str(w))]

    if not empty_wheels:
        print("No empty wheel files found")
        return

    # Print one per line for better readability
    print("\n".join(empty_wheels))


if __name__ == "__main__":
    main()
