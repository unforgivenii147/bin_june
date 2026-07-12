#!/data/data/com.termux/files/usr/bin/env python


import sys
from pathlib import Path

from PyPDF2 import PdfReader


from pathlib import Path
from os import scandir as os_scandir
from collections.abc import Callable, Iterable


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)(delayed(process_function)(file_str, **kwargs) for file_str in file_strings)


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


def process_file(path) -> None:
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != ".pdf":
        print(f"Error: Invalid PDF file path provided: {path}")
        return
    filename_base = path.stem
    output_folder = path.parent / filename_base
    try:
        output_folder.mkdir(parents=True, exist_ok=True)
        print(f"Saving page text files to: {output_folder}")
    except OSError as e:
        print(f"Error creating output directory {output_folder}: {e}")
        return
    try:
        reader = PdfReader(path)
    except Exception as e:
        print(f"Error opening PDF file {path}: {e}")
        return
    num_pages = len(reader.pages)
    print(f"Processing PDF: {path.name} ({num_pages} pages)")
    for page_num in range(num_pages):
        if 100 <= num_pages < 1000:
            if 0 <= page_num + 1 < 10:
                pad = "00"
            elif 10 <= page_num + 2 < 100:
                pad = "0"
            else:
                pad = ""
        elif 10 <= num_pages < 100:
            if 0 <= page_num + 1 < 10:
                pad = "0"
            elif 10 <= page_num + 1 < 100:
                pad = ""
        elif 0 < num_pages < 10:
            pad = ""
        page_filename = f"{filename_base}_{pad}{page_num + 1}.txt"
        output_filepath = output_folder / page_filename
        if output_filepath.exists():
            continue
        try:
            page = reader.pages[page_num]
            text = page.extract_text()
            if text:
                with output_filepath.open("w", encoding="utf-8") as txt_file:
                    txt_file.write(text)
                if page_num % 10 == 0:
                    print(f"Saved: {output_filepath.name}")
            else:
                print(f"Warning: No text extracted from page {page_num + 1}.")
        except Exception as e:
            print(f"Error processing page {page_num + 1}: {e}")


if __name__ == "__main__":
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_files(cwd, ext=[".pdf", ".PDF"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)
    mpf3(process_file, files)
