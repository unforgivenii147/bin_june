#!/data/data/com.termux/files/usr/bin/python
"""Commit all files in current directory to a local git repository.
Initializes a new repository if not already inside one.
Automatically pushes to remote if configured.
"""

import sys
from pathlib import Path
from datetime import datetime

from git import Repo, InvalidGitRepositoryError


def main() -> None:
    cwd = Path.cwd()
    try:
        repo = Repo(cwd, search_parent_directories=True)
        print(f"Found existing git repository at {repo.git_dir}")
    except InvalidGitRepositoryError:
        repo = Repo.init(cwd)
        print("Repository initialized.")

    if not repo.is_dirty(untracked_files=True):
        print("No changes to commit.")
        # Still try to push if there are unpushed commits? Probably not.
        return

    repo.git.add("--all")

    commit_message = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        commit = repo.index.commit(commit_message)
        print(f'Committed with message: "{commit_message}"')
        print(f"Commit hash: {commit.hexsha[:7]}")
    except Exception as e:
        print(f"Commit failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Push to remote if it exists
    try:
        # Check if any remotes are configured
        if not repo.remotes:
            print("No remote repository configured. Skipping push.")
            return

        # Get the first remote (usually 'origin')
        remote = repo.remotes[0]

        # Get current branch name
        current_branch = repo.active_branch.name

        print(f"Pushing to remote '{remote.name}'...")
        push_result = remote.push(refspec=f"{current_branch}:{current_branch}")

        # Check push results
        for result in push_result:
            if result.flags & result.ERROR:
                print(f"Push failed: {result.summary}", file=sys.stderr)
                sys.exit(1)
            elif result.flags & result.UP_TO_DATE:
                print("Remote is already up to date.")
            elif result.flags & result.FAST_FORWARD:
                print(f"Successfully pushed to {remote.name}/{current_branch}")
            else:
                print(f"Push result: {result.summary}")

    except Exception as e:
        print(f"Push failed: {e}", file=sys.stderr)
        # Don't exit with error - commit succeeded even if push failed
        print("Commit was successful, but push failed. You can push manually later.")


if __name__ == "__main__":
    main()
