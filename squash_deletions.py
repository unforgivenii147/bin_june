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

    # Verify a previous commit actually exists to amend into
    try:
        run_git_command(["log", "-1"])
    except SystemExit:
        print("❌ Error: No previous commit found to squash into. Create an initial commit first.")
        sys.exit(1)

    print("🔍 Searching repository history for deleted files...")

    # Step 1: Extract paths of files historically deleted across the git log
    log_output = run_git_command(["log", "--diff-filter=D", "--name-only", "--pretty=format:"])
    historically_deleted = {line.strip() for line in log_output.splitlines() if line.strip()}

    if not historically_deleted:
        print("ℹ️  No deleted files found in the git commit log.")
        return

    # Step 2: Correlate with current unstaged/staged file system status flags
    status_output = run_git_command(["status", "--porcelain"])

    locally_removed_files = []
    for line in status_output.splitlines():
        if len(line) > 3:
            status = line[:2]
            file_path = line[3:].strip()
            # Catch items tracked as deleted ('D') that match historical data
            if "D" in status and file_path in historically_deleted:
                locally_removed_files.append(file_path)

    if not locally_removed_files:
        print("🎉 No pending file deletions match historical records.")
        return

    print(f"⚠️  Found {len(locally_removed_files)} deleted file(s) to squash into the last commit:")
    for path in locally_removed_files:
        print(f"   -> {path}")

    # Step 3: Stage the deletions
    print("\n🛠️  Staging file deletions...")
    for path in locally_removed_files:
        run_git_command(["add", path])

    # Step 4: Squash into previous commit via --amend
    print("💾 Squashing changes into previous commit (git commit --amend --no-edit)...")
    amend_output = run_git_command(["commit", "--amend", "--no-edit"])

    print("\n📊 Git Amend Summary:")
    print(amend_output)


if __name__ == "__main__":
    main()
