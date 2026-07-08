#!/data/data/com.termux/files/usr/bin/env python


from pathlib import Path


def compress_folder_to_tar(folder_path: Path, output_base_name: str, format: str = "tar") -> bool:
    print(f"Simulating: Compressing folder '{folder_path}' to '{output_base_name}.tar'...")
    (folder_path.parent / f"{output_base_name}.tar").touch()
    print(f"Simulating: Created '{output_base_name}.tar'")
    return True


def atomic_write(data: bytes, final_path: Path) -> bool:
    print(f"Simulating: Atomic write to {final_path}")
    return True


def safe_delete(path: Path, max_retries: int = 3) -> bool:
    print(f"Simulating: Deleting '{path}'...")
    if path.is_file() or path.is_dir():
        print(f"Simulating: Successfully deleted '{path}'")
        return True
    print(f"Simulating: Path '{path}' not found for deletion.")
    return False


def compress_file(path: Path) -> bool:
    print(f"Simulating: Compressing file '{path}' with XZ...")
    (path.parent / f"{path.stem}.xz").touch()
    print(f"Simulating: Created '{path.stem}.xz'")
    return True


def get_files(directory: Path) -> list[Path]:
    print(f"Simulating: Getting files in '{directory}'...")
    return [p for p in directory.parent.iterdir() if p.name.endswith(".tar") and p.is_file()]


def get_dirs(cwd: Path) -> list[Path]:
    print(f"Simulating: Getting directories in '{cwd}'...")
    return [d for d in cwd.iterdir() if d.is_dir()]


def should_compress(path: Path) -> bool:
    return True


def main() -> None:
    cwd = Path()
    dirs_to_process = get_dirs(cwd)
    print("\n--- Starting Directory Compression ---")
    for d_path in dirs_to_process:
        if should_compress(d_path):
            print(f"\nProcessing directory: {d_path.name}")
            output_base = d_path.name
            tar_success = compress_folder_to_tar(d_path, output_base, format="tar")
            if tar_success:
                print(f"Successfully created tar for '{d_path.name}'.")
                delete_success = safe_delete(d_path)
                if not delete_success:
                    print(f"Warning: Failed to delete original directory '{d_path.name}' after compression.")
            else:
                print(f"Error: Failed to compress directory '{d_path.name}'. Original directory will NOT be deleted.")
    print("--- Directory Compression Complete ---")
    tar_files_to_process = get_files(cwd)
    print("\n--- Starting .tar File Compression ---")
    for tar_file_path in tar_files_to_process:
        if should_compress(tar_file_path) and tar_file_path.suffix.lower() == ".tar":
            print(f"\nProcessing .tar file: {tar_file_path.name}")
            xz_success = compress_file(tar_file_path)
            if xz_success:
                print(f"Successfully created XZ archive for '{tar_file_path.name}'.")
                delete_success = safe_delete(tar_file_path)
                if not delete_success:
                    print(f"Warning: Failed to delete original tar file '{tar_file_path.name}' after XZ compression.")
            else:
                print(
                    f"Error: Failed to compress '{tar_file_path.name}' with XZ. Original tar file will NOT be deleted."
                )
    print("--- .tar File Compression Complete ---")


if __name__ == "__main__":
    main()
