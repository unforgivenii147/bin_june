#!/data/data/com.termux/files/usr/bin/env python
from collections import deque
from collections.abc import Callable, Iterable
from io import BytesIO
from os import scandir as os_scandir
from pathlib import Path
import cairosvg
from PIL import Image


def get_files(path: str | Path, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    skip_dirs = {".git", "__pycache__"}
    queue = deque([path])
    files = []
    while queue:
        current = queue.popleft()
        try:
            entries = current.iterdir()
        except (PermissionError, OSError):
            continue
        for item in entries:
            if item.is_symlink():
                continue
            if item.is_dir() and item.name not in skip_dirs:
                queue.append(item)
            elif item.is_file():
                if ext is None or item.suffix in ext:
                    files.append(item)
    return files


def mpf3(process_function: Callable, files: list[Path], **kwargs):
    from joblib import Parallel, delayed

    file_strings = [str(f) for f in files]
    return Parallel(n_jobs=-1)((delayed(process_function)(file_str, **kwargs) for file_str in file_strings))


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
