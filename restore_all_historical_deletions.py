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

    print("🔍 Analyzing repository history for all historical file deletions...")

    # Step 1: Query the log for all deletion events.
    # --diff-filter=D filters for items that were deleted.
    # %H retrieves the exact commit hash where the deletion occurred.
    # --name-only spits out the file paths involved in that specific commit.
    log_output = run_git_command(["log", "--diff-filter=D", "--pretty=format:%H", "--name-only"])

    if not log_output:
        print("🎉 No deleted files were found in this repository's entire history.")
        return

    # Step 2: Parse the log output to find the last-known commit for each deleted path
    # Because a file could be deleted, recreated, and deleted again, we want its most recent deletion.
    # We will map: file_path -> deletion_commit_hash
    deleted_files_map = {}
    current_commit_hash = None

    for line in log_output.splitlines():
        line = line.strip()
        if not line:
            continue

        # If the line is 40 characters long, it's a commit hash
        if len(line) == 40 and " " not in line:
            current_commit_hash = line
        else:
            # It's a file path associated with the current_commit_hash
            file_path = line
            # Only save the first time we see it (which is the most recent deletion in reverse log history)
            if file_path not in deleted_files_map:
                deleted_files_map[file_path] = current_commit_hash

    # Step 3: Filter out files that currently exist in your working directory
    # We do this so we don't accidentally overwrite or corrupt any files you've recreated.
    files_to_restore = []
    for path_str, deletion_commit in deleted_files_map.items():
        if not Path(path_str).exists():
            files_to_restore.append((path_str, deletion_commit))

    if not files_to_restore:
        print("ℹ️  All historically deleted files are already active or restored in your workspace.")
        return

    print(f"⚠️  Found {len(files_to_restore)} historically deleted file(s) missing from your workspace.\n")

    # Step 4: Recover files by checking them out from the commit right BEFORE they were deleted
    # We use the caret symbol (commit_hash^) to target the parent commit where the file still existed.
    restored_count = 0
    for path_str, deletion_commit in files_to_restore:
        print(f"🔄 Restoring: {path_str} (From commit prior to {deletion_commit[:8]})")
        try:
            # Pull the file content back to disk using the commit state prior to deletion
            run_git_command(["checkout", f"{deletion_commit}^", "--", path_str])

            # Immediately add it to the staging area
            run_git_command(["add", path_str])
            restored_count += 1
        except Exception:
            # If checking out fails (e.g., if the deletion happened in the initial/first commit and has no parent ^)
            # fallback to trying to grab it directly from that commit if possible or skip gracefully.
            try:
                run_git_command(["checkout", deletion_commit, "--", path_str])
                run_git_command(["add", path_str])
                restored_count += 1
            except Exception as fallback_err:
                print(f"   ❌ Could not restore {path_str}: {fallback_err}")

    # Step 5: Wrap everything into a single clean commit
    if restored_count > 0:
        print("\n💾 Committing restored files into the repository repository...")
        commit_output = run_git_command(["commit", "-m", "removed files"])
        print("\n📊 Git Commit Summary:")
        print(commit_output)
    else:
        print("\n❌ No files were successfully restored.")


if __name__ == "__main__":
    main()
