from __future__ import annotations
import sys
import tarfile
import zipfile
from collections import deque
from collections.abc import Callable
from pathlib import Path
from dh import _clean_fname, get_files


def unique_path(path: Path | str) -> Path:
    path = _clean_fname(Path(path))
    if not path.exists():
        return path
    parent = path.parent
    suffixes = path.suffixes
    if suffixes:
        first_suffix_index = path.name.find(suffixes[0])
        stem = path.name[:first_suffix_index]
        full_suffix = "".join(suffixes)
    else:
        stem = path.name
        full_suffix = ""
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{full_suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)((delayed(process_function)(file_str, **kwargs) for file_str in file_strings))


def process_file(path: str | Path) -> None:
    path = Path(path)
    new_name = ""
    if path.name.endswith(".txz"):
        new_name = path.name.replace(".txz", ".whl")
    elif path.name.endswith(".tar.xz"):
        new_name = path.name.replace(".tar.xz", ".whl")
    else:
        return
    target = path.with_name(new_name)
    if target.exists():
        print(f"[SKIP] {target.name} already exists")
        target = unique_path(target)
    try:
        with tarfile.open(path, "r:xz") as tf, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for member in tf.getmembers():
                if member.isdir():
                    continue
                extracted = tf.extractfile(member)
                if extracted is None:
                    continue
                zf.writestr(member.name, extracted.read())
        print(f"[OK] {target.name}")
    except Exception as e:
        print(f"[ERROR] {path.name}: {e}")


def main() -> None:
    args = sys.argv[1:]
    cwd = Path().cwd()
    files = [Path(arg) for arg in args] if args else get_files(cwd, ext=[".tar.xz", ".txz"])
    if len(files) == 1:
        process_file(files[0])
        sys.exit(1)
    mpf3(process_file, files)


if __name__ == "__main__":
    sys.exit(main())
