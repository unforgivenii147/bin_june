#!/data/data/com.termux/files/home/.local/bin/python
import os
import shutil
import subprocess
import sys
from pathlib import Path
from subprocess import CompletedProcess


def run_git_command(cmd: list[str], check: bool = True, capture_output: bool = True) -> CompletedProcess[str] | None:
    """Helper to run git commands securely without shell=True."""
    try:
        return subprocess.run(cmd, check=check, capture_output=capture_output, text=True)
    except subprocess.CalledProcessError:
        return None


def is_git_repository(repo_path: Path = Path(".")) -> bool:
    """Pure Python check for .git directory existence."""
    git_dir = repo_path / ".git"
    return git_dir.is_dir() or git_dir.is_file()  # Supports normal repos and git worktrees/submodules


def get_current_branch(repo_path: Path = Path(".")) -> str | None:
    """Pure Python resolution of the current HEAD branch."""
    head_file = repo_path / ".git" / "HEAD"
    if not head_file.is_file():
        return None

    try:
        content = head_file.read_text().strip()
        if content.startswith("ref: refs/heads/"):
            return content.replace("ref: refs/heads/", "")
    except OSError:
        pass

    # Fallback to git CLI if in detached HEAD state or complex setup
    result = run_git_command(["git", "branch", "--show-current"], check=False)
    return result.stdout.strip() if result and result.stdout else None


def get_main_branch_name(repo_path: Path = Path(".")) -> str:
    """Determines main branch by inspecting local refs, falling back to git CLI."""
    heads_dir = repo_path / ".git" / "refs" / "heads"

    if heads_dir.is_dir():
        local_branches = {f.name for f in heads_dir.iterdir() if f.is_file()}
        for candidate in ("main", "master"):
            if candidate in local_branches:
                return candidate

    # Fallback using git commands if refs are packed in .git/packed-refs
    result = run_git_command(["git", "remote", "show", "origin"], check=False)
    if result and "HEAD branch" in result.stdout:
        for line in result.stdout.splitlines():
            if "HEAD branch" in line:
                return line.split(":")[1].strip()

    return "main"


def get_all_branches(repo_path: Path = Path(".")) -> list[str]:
    """Retrieves all local branches using filesystem parsing with CLI fallback."""
    heads_dir = repo_path / ".git" / "refs" / "heads"
    branches = set()

    if heads_dir.is_dir():
        for root, _, files in os.walk(heads_dir):
            for file in files:
                rel_path = Path(root, file).relative_to(heads_dir)
                branches.add(str(rel_path).replace("\\", "/"))

    # Also check packed-refs file if present
    packed_refs = repo_path / ".git" / "packed-refs"
    if packed_refs.is_file():
        try:
            for line in packed_refs.read_text().splitlines():
                if line and not line.startswith(("#", "^")):
                    parts = line.split()
                    if len(parts) == 2 and parts[1].startswith("refs/heads/"):
                        branches.add(parts[1].replace("refs/heads/", ""))
        except OSError:
            pass

    if branches:
        return sorted(list(branches))

    # CLI Fallback
    result = run_git_command(["git", "branch", "--format=%(refname:short)"], check=False)
    if result and result.stdout:
        return [b.strip() for b in result.stdout.splitlines() if b.strip()]
    return []


def delete_branches_except_main() -> list[str]:
    main_branch = get_main_branch_name()
    branches = get_all_branches()
    print(f"Main branch: {main_branch}")
    print(f"Found branches: {', '.join(branches)}")

    deleted_branches = []
    for branch in branches:
        if branch != main_branch:
            print(f"Deleting branch: {branch}")
            result = run_git_command(["git", "branch", "-D", branch], check=False)
            if result and result.returncode == 0:
                deleted_branches.append(branch)
                print(f"✓ Deleted branch: {branch}")
            else:
                print(f"✗ Failed to delete branch: {branch}")
    return deleted_branches


def reset_and_preserve_commit() -> bool:
    """Resets working tree and index to match HEAD exactly, preserving original commit hash."""
    print("Resetting working tree (preserving original commit hash)...")

    # Soft reset / hard reset keeps the commit hash intact
    result = run_git_command(["git", "reset", "--hard", "HEAD"], check=False)
    if not result or result.returncode != 0:
        print("Failed to reset working tree.")
        return False

    # Clean un-tracked files and directories
    run_git_command(["git", "clean", "-fd"], check=False)

    # Optional reflog cleanup to reclaim space
    run_git_command(["git", "reflog", "expire", "--expire=now", "--all"], check=False)
    run_git_command(["git", "gc", "--prune=now"], check=False)

    print("✓ Working directory reset to HEAD. Original commit hash preserved.")
    return True


def main() -> None:
    if not is_git_repository():
        print("Error: Not a git repository!")
        sys.exit(1)

    main_branch = get_main_branch_name()
    current_branch = get_current_branch()

    if current_branch != main_branch:
        print(f"\nSwitching to main branch: {main_branch}")
        result = run_git_command(["git", "checkout", main_branch], check=False)
        if not result or result.returncode != 0:
            print(f"Failed to switch to {main_branch}")
            sys.exit(1)

    print(f"\nDeleting branches except {main_branch}...")
    deleted_branches = delete_branches_except_main()
    if deleted_branches:
        print(f"    Deleted {len(deleted_branches)} branch(es)")
    else:
        print("    No extra branches to delete")

    reset_and_preserve_commit()

    result = run_git_command(["git", "log", "-1", "--format=Commit Hash: %H%nSubject: %s"])
    if result and result.stdout:
        print("\nCurrent HEAD State:")
        print(result.stdout.strip())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)
