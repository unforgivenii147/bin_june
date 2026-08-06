from __future__ import annotations
from collections import deque
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
import cairosvg
from PIL import Image
from dh import get_files


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
