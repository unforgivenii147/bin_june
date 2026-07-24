#!/data/data/com.termux/files/home/.local/bin/python
import subprocess
import sys
from pathlib import Path


def run_git_command(args: list[str]) -> str:
    """Executes a git command and returns the standard output string."""
    try:
        result = subprocess.run(["git"] + args, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Git error executing {' '.join(e.cmd)}:\n{e.stderr.strip()}")
        sys.exit(1)


def main():
    # Ensure this is being run inside a valid git repository
    repo_root = Path(".")
    if not (repo_root / ".git").exists() and not run_git_command(["rev-parse", "--is-inside-work-tree"]) == "true":
        print("❌ Error: Current directory is not a Git repository root.")
        sys.exit(1)

    print("🔍 Searching repository history for deleted files...")

    # Step 1: Get names of all files deleted in the repo log history (across all commits)
    # --diff-filter=D extracts only 'Deleted' status logs
    # --name-only lists only paths instead of full diff blocks
    log_output = run_git_command(["log", "--diff-filter=D", "--name-only", "--pretty=format:"])

    # Clean up empty lines and create a unique set of historically deleted file paths
    historically_deleted = {line.strip() for line in log_output.splitlines() if line.strip()}

    if not historically_deleted:
        print("ℹ️  No deleted files found in the git commit log log.")
        return

    # Step 2: Get status of files in the current working tree to see what is missing/unstaged
    # 'git status --porcelain' outputs predictable machine-readable file status flags
    status_output = run_git_command(["status", "--porcelain"])

    # We want files marked with a ' D' or 'D ' (locally deleted but unstaged or tracked deletions)
    locally_removed_files = []
    for line in status_output.splitlines():
        if len(line) > 3:
            status = line[:2]
            file_path = line[3:].strip()
            # If the file is tracked as deleted locally and matches our historical deletion index
            if "D" in status and file_path in historically_deleted:
                locally_removed_files.append(file_path)

    if not locally_removed_files:
        print("🎉 No pending historical file deletions need to be tracked or staged.")
        return

    print(f"⚠️  Found {len(locally_removed_files)} deleted file(s) to process:")
    for path in locally_removed_files:
        print(f"   -> {path}")

    # Step 3: Stage the deleted files to the current tracking index
    print("\n🛠️ Staging deleted files (git add -A)...")
    for path in locally_removed_files:
        run_git_command(["add", path])

    # Step 4: Commit the staged deletions
    commit_message = "removed files"
    print(f'💾 Committing changes: git commit -m "{commit_message}"')
    commit_output = run_git_command(["commit", "-m", commit_message])

    print("\n📊 Git Commit Summary:")
    print(commit_output)


if __name__ == "__main__":
    main()
