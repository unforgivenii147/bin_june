#!/data/data/com.termux/files/usr/bin/python
import os
import shutil
from pathlib import Path


def keep_one_image_per_folder(base_dir):
    """
    Keeps only one image in each folder within the base directory.
    Deletes all other image files from each folder.

    Args:
        base_dir: Path to the directory containing the group folders
    """
    base_path = Path(base_dir)

    # Common image extensions
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".heic", ".heif", ".raw"}

    # Find all group folders matching pattern similar_group_number
    group_folders = []
    for folder in base_path.iterdir():
        if folder.is_dir() and folder.name.startswith("similar_"):
            try:
                # Validate that the number part is numeric
                num_part = folder.name.split("_")[-1]
                int(num_part)  # Try to convert to int
                group_folders.append(folder)
            except ValueError:
                print(f"Skipping {folder.name}: doesn't match expected pattern")
                continue

    print(f"Found {len(group_folders)} group folders")

    for folder in group_folders:
        print(f"\nProcessing: {folder.name}")

        # Get all image files in the folder
        image_files = []
        for file in folder.iterdir():
            if file.is_file() and file.suffix.lower() in image_extensions:
                image_files.append(file)

        if len(image_files) == 0:
            print(f"  No images found in {folder.name}")
            continue

        if len(image_files) == 1:
            print(f"  Already has only 1 image: {image_files[0].name}")
            continue

        # Keep the first image, delete the rest
        keep_file = image_files[0]
        print(f"  Keeping: {keep_file.name}")

        for file in image_files[1:]:
            try:
                file.unlink()  # Delete the file
                print(f"  Deleted: {file.name}")
            except Exception as e:
                print(f"  Error deleting {file.name}: {e}")

        print(f"  Done! {len(os.listdir(folder))} files remaining in folder")

    print(f"\n✅ Completed! Processed {len(group_folders)} folders.")


if __name__ == "__main__":
    # Update this path to your base directory
    base_directory = Path.cwd()

    # Verify the path exists
    if not os.path.exists(base_directory):
        print(f"Error: Directory '{base_directory}' not found!")
        print("Please update the 'base_directory' variable with the correct path.")
    else:
        # Ask for confirmation
        print(f"⚠️  WARNING: This will delete images from folders in: {base_directory}")
        print("Only ONE image will be kept per folder. This action cannot be undone!")

        response = input("Do you want to continue? (yes/no): ").strip().lower()

        if response == "yes" or response == "y":
            keep_one_image_per_folder(base_directory)
        else:
            print("Operation cancelled.")
