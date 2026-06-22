#!/data/data/com.termux/files/usr/bin/python
from pathlib import Path
from datetime import datetime
import os
import sys
from dotenv import load_dotenv
from git import Repo, exc as GitExc

# Load GITHUB_TOKEN from ~/.env
load_dotenv(Path.home() / '.env')
GITHUB_USERNAME = "unforgivenii147"

def ensure_git_repo() -> Repo:
    try:
        return Repo('.')
    except GitExc.InvalidGitRepositoryError:
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
        print(f"Symlinked {home_gitignore} -> {local_gitignore}")
    except Exception as e:
        print(f"Failed to create symlink: {e}", file=sys.stderr)
        sys.exit(1)

def main() -> None:
    repo = ensure_git_repo()
    symlink_global_gitignore()

    # Stage all changes
    repo.git.add('--all')

    # Commit with timestamp
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto-commit at {now}"
    try:
        repo.git.commit('-m', commit_msg)
    except GitExc.GitCommandError:
        print("Nothing to commit (no changes).", file=sys.stderr)
        sys.exit(0)

    # Authenticate and push
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("GITHUB_TOKEN not found in ~/.env", file=sys.stderr)
        sys.exit(1)

    origin = repo.remote('origin')
    old_url = origin.url
    modified_url = False

    try:
        branch = repo.active_branch.name

        # Inject token into HTTPS URL for GitHub auth
        if old_url.startswith('https://github.com/'):
            new_url = old_url.replace(
                'https://github.com/',
                f'https://{GITHUB_USERNAME}:{token}@github.com/'
            )
            origin.set_url(new_url)
            modified_url = True

        print(f"Pushing to origin/{branch}...")
        origin.push(refspec=f'{branch}:{branch}')
        print(f"Pushed to origin/{branch} with message: {commit_msg}")

    except GitExc.GitCommandError as e:
        print(f"Push failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if modified_url:
            origin.set_url(old_url)

if __name__ == "__main__":
    main()
