#!/data/data/com.termux/files/usr/bin/env python


import subprocess
import sys
from datetime import datetime
from pathlib import Path
from dh import runcmd


def run(cmd: str) -> None:
    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError:
        print(f"Command failed: {cmd}", file=sys.stderr)
        sys.exit(1)


def ensure_git_repo() -> None:
    try:
        subprocess.check_output("git rev-parse --is-inside-work-tree", shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        print("Not inside a Git repository.", file=sys.stderr)
        sys.exit(1)


def symlink_global_gitignore() -> None:
    home_gitignore = Path.home() / ".gitignore"
    local_gitignore = Path(".gitignore")
    if not home_gitignore.exists():
        print("~/.gitignore does not exist. Create it first if needed.")
        return
    if local_gitignore.exists():
        return
    try:
        local_gitignore.symlink_to(home_gitignore)
        print(f"Symlinked {home_gitignore} → {local_gitignore}")
    except Exception as e:
        print(f"Failed to create symlink: {e}", file=sys.stderr)
        sys.exit(1)


def get_current_branch(cmd: list[str] = ["git", "branch"]) -> str:
    _, txt, _ = runcmd(cmd, show_output=False)
    branch = txt.strip().replace("* ", "")
    return branch


def main() -> None:
    ensure_git_repo()
    symlink_global_gitignore()
    run("git add -A")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto-commit at {now}"
    subprocess.call(f"git commit -m '{commit_msg}'", shell=True)
    branch = get_current_branch()
    run(f"git push origin {branch}")
    print(f"Pushed to origin/{branch} with message: {commit_msg}")


if __name__ == "__main__":
    main()
