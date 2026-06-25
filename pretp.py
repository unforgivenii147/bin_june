#!/data/data/com.termux/files/usr/bin/python

import concurrent.futures
import os
import subprocess

from tqdm import tqdm


def format_file(file_path) -> str | None:
    try:
        subprocess.run(
            ["npx", "prettier", "--write", file_path],
            capture_output=True,
            text=True,
            check=True,
        )
        return None
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return f"{file_path}: {(e.stderr if hasattr(e, 'stderr') else e)!s}"


def main() -> None:
    target_extensions = (
        ".js",
        ".css",
        ".htm",
        ".html",
        ".ts",
        ".jsx",
        ".tsx",
        ".xml",
        ".json",
    )
    exclude_dirs = {".git"}
    exclude_extensions = (".min.js", ".min.css")
    files_to_format = []
    print("Scanning directory for files...")
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        files_to_format.extend(
            (
                os.path.join(root, file)
                for file in files
                if file.endswith(target_extensions) and (not file.endswith(exclude_extensions))
            )
        )
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
