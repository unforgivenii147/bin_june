#!/data/data/com.termux/files/usr/bin/python
"""Commit all files in current directory to a local git repository.
Initializes a new repository if not already inside one.
Automatically pushes to remote if configured.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from git import Repo, InvalidGitRepositoryError


def load_git_token() -> str | None:
    """Load GitHub token from .env file in the script's directory."""
    # Get the directory where this script is located
    home_dir = Path.home()
    env_path = home_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
    else:
        print(f"No .env file found at {env_path}")
        return None
    
    # Try different possible environment variable names
    token = (os.getenv("GITHUB_TOKEN") or 
             os.getenv("GH_TOKEN") or 
             os.getenv("GIT_TOKEN"))
    
    if token:
        print("GitHub token found")
        # Mask token for security in output
        masked_token = token[:4] + "..." + token[-4:] if len(token) > 8 else "***"
        print(f"Using token: {masked_token}")
    else:
        print("No GitHub token found in .env file")
    
    return token


def setup_git_auth(repo: Repo, token: str = None) -> None:
    """Configure git authentication using token."""
    if not token:
        return
        
    try:
        # Method 1: Update remote URL with token
        for remote in repo.remotes:
            for url in remote.urls:
                if "github.com" in url:
                    if url.startswith("https://") and "@github.com" not in url:
                        new_url = url.replace("https://", f"https://oauth2:{token}@")
                        if new_url != url:
                            remote.set_url(new_url)
                            print(f"Updated remote URL with token authentication")
                            return
        print("Remote URL already has authentication or is not HTTPS")
    except Exception as e:
        print(f"Could not update remote URL: {e}")
        # Fallback to credential helper
        try:
            os.system(f'git config --local credential.helper "!f() echo username=oauth2; echo password={token}; exit 0; f"')
            print("Set up credential helper as fallback")
        except Exception:
            pass


def push_to_remote(repo: Repo, token: str = None) -> None:
    """Push to remote repository using token if provided."""
    try:
        # Check if any remotes are configured
        if not repo.remotes:
            print("No remote repository configured. Skipping push.")
            return
        
        # Get the first remote (usually 'origin')
        remote = repo.remotes[0]
        
        # Get current branch name
        try:
            current_branch = repo.active_branch.name
        except TypeError:
            # Detached HEAD state
            print("In detached HEAD state. Skipping push.")
            return
        
        print(f"Pushing to remote '{remote.name}'...")
        
        # Setup authentication if token is available
        if token:
            setup_git_auth(repo, token)
        
        # Try to push
        push_result = remote.push()
        
        # Check push results
        for result in push_result:
            if result.flags & result.ERROR:
                print(f"Push failed: {result.summary}", file=sys.stderr)
                if "403" in result.summary or "401" in result.summary:
                    print("Authentication failed. Check your GitHub token.", file=sys.stderr)
                    print("Make sure your token has 'repo' scope for private repos or 'public_repo' for public repos.")
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


def main() -> None:
    # Load token from script directory FIRST
    token = load_git_token()
    
    cwd = Path.cwd()
    try:
        repo = Repo(cwd, search_parent_directories=True)
        print(f"Found existing git repository at {repo.git_dir}")
    except InvalidGitRepositoryError:
        repo = Repo.init(cwd)
        print("Repository initialized.")
        # Suggest adding a remote
        print("\nTip: Add a remote with: git remote add origin <your-repo-url>")
    
    # Check if there are changes to commit
    if not repo.is_dirty(untracked_files=True):
        print("No changes to commit.")
        # Still try to push if there are unpushed commits
        if repo.remotes:
            try:
                # Check if we have commits to push
                current_branch = repo.active_branch
                remote_branch = repo.remotes[0].refs[current_branch.name]
                if repo.git.rev_list(f"{remote_branch}..{current_branch}"):
                    print("Found unpushed commits. Pushing...")
                    push_to_remote(repo, token)
                else:
                    print("Remote is up to date.")
            except Exception as e:
                print(f"Push check failed: {e}")
        return
    
    # Add and commit changes
    print("\nChanges detected. Adding all files...")
    repo.git.add("--all")
    
    commit_message = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        commit = repo.index.commit(commit_message)
        print(f'Committed with message: "{commit_message}"')
        print(f"Commit hash: {commit.hexsha[:7]}")
    except Exception as e:
        print(f"Commit failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Push to remote
    push_to_remote(repo, token)


if __name__ == "__main__":
    main()
