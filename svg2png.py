#!/data/data/com.termux/files/usr/bin/env python


from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image


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
    png_file = path.with_suffix(".png")
    try:
        with path.open("rb") as image:
            imageBinary = BytesIO(image.read())
            buff = BytesIO()
            cairosvg.svg2png(bytestring=imageBinary.getvalue(), write_to=buff)
            buff.seek(0)
            img = Image.open(buff)
            img.save(png_file)
    except:
        pass


def main() -> None:
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".svg"])
    mpf3(process_file, files)


if __name__ == "__main__":
    main()
