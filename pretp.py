#!/data/data/com.termux/files/usr/bin/python
from pathlib import Path
import concurrent.futures
import subprocess
from tqdm import tqdm


def format_file(file_path: str) -> str | None:
    try:
        subprocess.run(["npx", "prettier", "--write", str(file_path)], capture_output=True, text=True, check=True)
        return None
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return f"{file_path}: {e.stderr if hasattr(e, 'stderr') else str(e)}"


def main() -> None:
    target_extensions = (".js", ".css", ".htm", ".html", ".ts", ".jsx", ".tsx", ".xml", ".json")
    exclude_dirs = {".git"}
    exclude_extensions = (".min.js", ".min.css")
    files_to_format = []
    print("Scanning directory for files...")

    base_path = Path(".")
    for file_path in base_path.rglob("*"):
        if not file_path.is_file():
            continue

        # Check if any part of the path is in exclude_dirs
        if any(part in exclude_dirs for part in file_path.parts):
            continue

        if file_path.suffix in target_extensions or any(file_path.name.endswith(ext) for ext in target_extensions):
            # target_extensions includes things like .html which is a suffix, but also .htm
            # Let's be more precise
            if any(file_path.name.endswith(ext) for ext in target_extensions) and not any(
                file_path.name.endswith(ext) for ext in exclude_extensions
            ):
                files_to_format.append(str(file_path))

    if not files_to_format:
        print("No matching files found.")
        return
    errors = []
    with (
        tqdm(total=len(files_to_format), desc="Beautifying", unit="file") as pbar,
        concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor,
    ):
        future_to_file = {executor.submit(format_file, f): f for f in files_to_format}
        for future in concurrent.futures.as_completed(future_to_file):
            err = future.result()
            if err:
                errors.append(err)
            pbar.update(1)
    print("\n" + "=" * 30)
    print(f"Finished processing {len(files_to_format)} files.")
    if errors:
        print(f"Encountered {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("All files formatted successfully!")


if __name__ == "__main__":
    main()
