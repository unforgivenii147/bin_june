#!/data/data/com.termux/files/usr/bin/python

import os
import sys
from pathlib import Path
from dh import MIME2EXT, cprint, is_binary, runcmd, unique_path

CONFIRM = "-y" in sys.argv


def fix_by_shebang(path) -> bool:
    if is_binary(path) or not path.stat().st_size:
        return False
    try:
        content = path.read_text(encoding="utf8")
    except:
        return False
    fl = content.splitlines()[0]
    if fl.startswith("#!") and ("bash" in fl or "/bin/sh" in fl):
        new_path = path.with_suffix(".sh")
        if new_path.exists():
            new_path = unique_path(new_path)
        path.rename(new_path)
        return True
    if fl.startswith("#!") and "python" in fl:
        new_path = path.with_suffix(".py")
        if new_path.exists():
            new_path = unique_path(new_path)
        path.rename(new_path)
        return True
    return False


def get_file_mime(path) -> str:
    _, txt, _ = runcmd(["file", "--brief", "--mime-type", str(path)], show_output=False)
    return txt


def safe_rename(old_path, new_path):
    base, ext = os.path.splitext(new_path)
    counter = 1
    while Path(new_path).exists():
        counter += 1
    cprint(f"{old_path} -> {new_path} ?")
    Path(old_path).rename(new_path)
    return new_path


def check_files(directory: Path):
    mismatched_files = []
    for root, _, files in os.walk(directory):
        for name in files:
            path = Path(root) / name
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            ext = path.suffix.lower()
            if ext in {".css", ".js"}:
                continue
            if fix_by_shebang(path):
                continue
            mime = get_file_mime(path)
            print(f"{name} --> {mime}")
            if mime:
                print(f"mime={mime}")
                expected_exts = MIME2EXT.get(mime.strip(), [])
                print(f"expected exts ={expected_exts}")
                if ".txt" in expected_exts:
                    continue
                if expected_exts and ext not in expected_exts:
                    new_path = None
                    new_ext = expected_exts[0]
                    new_name = path.stem + new_ext
                    print(f"new name = {new_name}")
                    new_path = Path(root) / new_name
                    if new_name == name:
                        continue
                    if new_path.exists():
                        new_path = unique_path(new_path)
                    if CONFIRM:
                        print(f"{path.suffix} -> {new_path.suffix}")
                        ans = input()
                        if ans == "y":
                            path.rename(new_path)
                    else:
                        path.rename(new_path)
                    mismatched_files.append((path, ext, mime, new_path))
    return mismatched_files


def main() -> None:
    cwd = Path.cwd()
    mismatches = check_files(cwd)
    if mismatches:
        print("Files with mismatched extensions:")
        for path, _ext, mime, new_path in mismatches:
            if new_path:
                print(f"\x1b[5;93m{path.name} {mime} \x1b[5;96m{new_path.name}]\x1b[0m")
            else:
                print(f"{path.name} -> \x1b[5m;94mdetected: {mime}\x1b[0m")
    else:
        cprint("no mismatch")


if __name__ == "__main__":
    main()
