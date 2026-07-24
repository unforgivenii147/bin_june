#!/data/data/com.termux/files/home/.local/bin/python
"""
Extract all .tar.xz files in current directory using parallel processing,
then remove the original archive files.
"""

import sys
import tarfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def extract_and_remove(tar_path: Path) -> tuple[Path, bool, str]:
    """
    Extract a single .tar.xz file and remove it if successful.

    Args:
        tar_path: Path to the .tar.xz file

    Returns:
        Tuple of (file_path, success_flag, error_message)
    """
    try:
        # Determine extraction directory (same as archive, without extension)
        extract_dir = tar_path.parent / tar_path.stem.replace(".tar", "")

        # Create extraction directory if it doesn't exist
        extract_dir.mkdir(parents=True, exist_ok=True)

        # Extract the archive
        with tarfile.open(tar_path, "r:xz") as tar:
            tar.extractall(path=extract_dir)

        # Remove the original archive file
        tar_path.unlink()

        return (tar_path, True, f"✅ Extracted and removed: {tar_path.name}")

    except tarfile.ReadError:
        return (tar_path, False, f"❌ Not a valid tar.xz file: {tar_path.name}")
    except tarfile.CompressionError:
        return (tar_path, False, f"❌ Compression error in: {tar_path.name}")
    except PermissionError:
        return (tar_path, False, f"❌ Permission denied: {tar_path.name}")
    except Exception as e:
        return (tar_path, False, f"❌ Error processing {tar_path.name}: {str(e)}")


def main():
    """Main function to process all .tar.xz files in current directory."""
    current_dir = Path.cwd()

    # Find all .tar.xz files
    tar_files = list(current_dir.glob("*.tar.xz"))

    if not tar_files:
        print("ℹ️  No .tar.xz files found in current directory.")
        return

    print(f"📦 Found {len(tar_files)} .tar.xz file(s) to process...\n")

    # Process files in parallel
    with ProcessPoolExecutor() as executor:
        # Submit all tasks
        future_to_file = {executor.submit(extract_and_remove, tar_path): tar_path for tar_path in tar_files}

        # Collect results as they complete
        success_count = 0
        failure_count = 0

        for future in as_completed(future_to_file):
            file_path, success, message = future.result()

            if success:
                success_count += 1
            else:
                failure_count += 1

            print(message)

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"✅ Successfully processed: {success_count} file(s)")
    if failure_count > 0:
        print(f"❌ Failed: {failure_count} file(s)")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)
