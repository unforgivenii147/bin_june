#!/data/data/com.termux/files/usr/bin/env python
import os
import subprocess
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def is_git_repo(path: Path) -> bool:
    return (path / ".git").is_dir()


def git_pull(repo_path: Path) -> None:
    print(f"\n==> Pulling in repo: {repo_path}")
    try:
        subprocess.run(["git", "-C", str(repo_path), "restore", "."], check=True)
    except subprocess.CalledProcessError:
        print(f"⚠️  git pull failed in: {repo_path}")


def main() -> None:
    root = Path.cwd()
    for dirpath, _dirnames, _filenames in os.walk(root):
        current = Path(dirpath)
        if is_git_repo(current):
            git_pull(current)
    print("\nDone.")


if __name__ == "__main__":
    main()
