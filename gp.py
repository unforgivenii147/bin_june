#!/data/data/com.termux/files/usr/bin/env python

"""Module for gp.py."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

try:
    from git import GitCommandError, InvalidGitRepositoryError, Repo
except ImportError:
    print("GitPython not found. Install it with: pip install gitpython", file=sys.stderr)
    sys.exit(1)


def symlink_global_gitignore() -> None:
    home_gitignore = Path.home() / ".gitignore"
    local_gitignore = Path(".gitignore")
    if not home_gitignore.exists():
        return
    if local_gitignore.exists() or local_gitignore.is_symlink():
        return
    try:
        local_gitignore.symlink_to(home_gitignore)
        print(f"Symlinked {home_gitignore} → {local_gitignore}")
    except Exception as e:
        print(f"Failed to create symlink: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    try:
        repo = Repo(".", search_parent_directories=True)
    except InvalidGitRepositoryError:
        print("Error: Not a git repository.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error accessing repository: {e}", file=sys.stderr)
        sys.exit(1)

    symlink_global_gitignore()

    try:
        # Stage all changes
        repo.git.add(A=True)

        # Create commit
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"Auto-commit at {now}"
        repo.index.commit(commit_msg)

        # Get current branch
        if repo.head.is_detached:
            print("Error: Could not detect current branch (detached HEAD?).", file=sys.stderr)
            sys.exit(1)

        branch = repo.active_branch.name

        # Push to origin
        origin = repo.remote("origin")
        origin.push(branch)

        print(f"Pushed to origin/{branch} with message: {commit_msg}")

    except GitCommandError as e:
        print(f"Git command error: {e}", file=sys.stderr)
        sys.exit(e.status or 1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
