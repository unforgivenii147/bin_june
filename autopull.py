#!/data/data/com.termux/files/usr/bin/python

import os
import subprocess
from pathlib import Path


def is_git_repo(path: Path) -> bool:
    return (path / ".git").is_dir()


def git_pull(repo_path: Path):
    print(f"\n==> Pulling in repo: {repo_path}")
    try:
        subprocess.run(["git", "-C", str(repo_path), "pull", "--ff-only"], check=True)
    except subprocess.CalledProcessError:
        print(f"⚠️  git pull failed in: {repo_path}")


def main():
    root = Path.cwd()
    for dirpath, dirnames, _filenames in os.walk(root):
        current = Path(dirpath)
        if is_git_repo(current):
            git_pull(current)
            dirnames[:] = [d for d in dirnames if d != ".git"]
    print("\nDone.")


if __name__ == "__main__":
    main()
