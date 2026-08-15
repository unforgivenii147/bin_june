#!/data/data/com.termux/files/home/.local/bin/python
from pathlib import Path
from dh import should_skip, get_files, move_dir


def has_lua(root_dir):
    lua_files = []
    lua_files = get_files(root_dir, ext=[".lua"])
    if lua_files:
        return True
    return False


def move_to_start(src):
    dest = "/data/data/com.termux/files/home/.vim/pack/plugins/start"
    import shutil

    target_path = f"{dest}/{src.name}"
    shutil.copytree(str(src), target_path)
    shutil.rmtree(src)


if __name__ == "__main__":
    cwd = Path.cwd()
    for dirpath in cwd.iterdir():
        if not dirpath.is_dir():
            continue
        if not has_lua(dirpath):
            print(f" - {dirpath.name}")
            ans = input(f"move {dirpath.name} ?")
            if ans == "y":
                move_to_start(dirpath)
