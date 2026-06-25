#!/data/data/com.termux/files/usr/bin/python
import logging
import multiprocessing
import site
import sys
import zipfile
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("wheel_repack.log", mode="w", encoding="utf-8"),
    ],
)


def verify_and_get_files(dist_info_dir):
    """
    Parses the RECORD file inside .dist-info.
    Verifies all listed files exist (ignoring .pyc files).
    Returns a list of tuples: (absolute_path_on_disk, relative_path_for_wheel)
    """
    record_path = dist_info_dir / "RECORD"
    if not record_path.exists():
        logging.error(f"Missing RECORD file in metadata directory: {dist_info_dir.name}")
        return None

    site_packages_root = dist_info_dir.parent
    files_to_pack = []

    with open(record_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            # RECORD rows are comma-separated: path,hash,size
            parts = line.split(",")
            rel_path_str = parts[0]

            # Normalize path delimiters for cross-platform safety
            rel_path = Path(rel_path_str.replace("\\", "/"))
            abs_path = (site_packages_root / rel_path).resolve()

            # Skip the RECORD file itself (the wheel writer recreates it) or .pyc files
            if rel_path.name == "RECORD" or rel_path.suffix == ".pyc":
                continue

            # Verify existence
            if not abs_path.exists():
                # Check if it's a directory (RECORD usually tracks files, but just in case)
                if not abs_path.is_dir():
                    logging.warning(f"Aborting {dist_info_dir.name}: Missing file -> {rel_path}")
                    return None

            files_to_pack.append((abs_path, rel_path))

    return files_to_pack


def build_wheel_worker(args):
    """
    Worker function executed in parallel.
    Compresses verified package files into a .whl file.
    """
    dist_info_dir_str, output_dir_str = args
    dist_info_dir = Path(dist_info_dir_str)
    output_dir = Path(output_dir_str)

    # Extract clean naming tokens from .dist-info directory name
    # Example: "requests-2.28.1.dist-info" -> name: "requests", version: "2.28.1"
    folder_name = dist_info_dir.stem
    if "-" not in folder_name:
        logging.error(f"Skipping invalid metadata folder format: {dist_info_dir.name}")
        return False

    name, version = folder_name.split("-", 1)

    # Generate a standard pure-python wheel filename
    # Format: {distribution}-{version}-{build_tag}-{python_tag}-{abi_tag}-{platform_tag}.whl
    wheel_filename = f"{name}-{version}-py3-none-any.whl"
    target_wheel_path = output_dir / wheel_filename

    # Step 1: Integrity Check
    files_to_pack = verify_and_get_files(dist_info_dir)
    if files_to_pack is None:
        return False

    # Step 2: Build the Wheel Archive
    try:
        logging.info(f"📦 Packaging {name} ({version})...")

        # Open ZipFile (wheels are fundamentally structured ZIP binaries)
        with zipfile.ZipFile(target_wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as whl:
            for abs_path, rel_path in files_to_pack:
                # write() takes (source_file, archive_destination_path)
                # This guarantees that files sit in their structured subfolders, NOT the wheel root!
                whl.write(abs_path, rel_path)

        logging.info(f"✅ Successfully created: {wheel_filename}")
        return True

    except Exception as e:
        logging.error(f"❌ Failed to archive {name}: {e}")
        # Clean up partial broken files if any
        if target_wheel_path.exists():
            target_wheel_path.unlink()
        return False


def main():
    # Identify user site-packages
    user_site = site.getusersitepackages()
    user_site_path = Path(user_site).resolve()

    if not user_site_path.exists():
        logging.error(f"User site-packages directory does not exist: {user_site_path}")
        return

    # Define target directory (~/tmp/whl expanded safely)
    output_dir = Path("~/tmp/whl").expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f"Source Directory: {user_site_path}")
    logging.info(f"Destination Directory: {output_dir}\n")

    # Locate all metadata directories representing installed packages
    dist_info_dirs = list(user_site_path.glob("*.dist-info"))

    if not dist_info_dirs:
        logging.info("No packages found in user site-packages to repack.")
        return

    # Prepare job payloads for the multiprocessing pool (strings are safer for serialization)
    tasks = [(str(d), str(output_dir)) for d in dist_info_dirs]

    # Initialize process pool utilizing available CPU cores
    num_cores = multiprocessing.cpu_count()
    logging.info(f"Spawning pool with {num_cores} parallel workers...\n")

    with multiprocessing.Pool(processes=num_cores) as pool:
        results = pool.map(build_wheel_worker, tasks)

    # Summary Statistics
    successful_builds = sum(1 for r in results if r)
    logging.info("\n=== REPACKING TASK COMPLETE ===")
    logging.info(f"Total evaluated packages: {len(dist_info_dirs)}")
    logging.info(f"Successfully compiled:    {successful_builds}")
    logging.info(f"Skipped / Failed:         {len(dist_info_dirs) - successful_builds}")
    logging.info("Check 'wheel_repack.log' for detailed warnings or error reports.")


if __name__ == "__main__":
    main()
