#!/data/data/com.termux/files/usr/bin/python
from pathlib import Path

import nude
from dh import get_files, mpf3, cprint

nude_path = Path("nude")
nude_path.mkdir(exist_ok=True)


def process_file(path):
    path = Path(path)
    if "nude" in path.parts:
        return
    print(f"{path.name}")
    if nude.is_nude(str(path)):
        cprint(f"{path.name} is nude", "cyan")
        new_path = nude_path / path.name
        path.rename(new_path)


if __name__ == "__main__":
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".jpg", ".jpeg", ".png", ".webp"])
    mpf3(process_file, files)
