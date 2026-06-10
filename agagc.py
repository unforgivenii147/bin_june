#!/data/data/com.termux/files/usr/bin/python
"""Commit all files in current directory to a local git repository.
Initializes a new repository if not already inside one.
Automatically pushes to remote if configured.
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import requests

from git import Repo, InvalidGitRepositoryError


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Commit and push all files to git repository")
    parser.add_argument(
        "-c", "--create", action="store_true", help="Create remote repository on GitHub if it doesn't exist"
    )
    return parser.parse_args()


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
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GIT_TOKEN")

    if token:
        print("GitHub token found")
        # Mask token for security in output
        masked_token = token[:4] + "..." + token[-4:] if len(token) > 8 else "***"
        print(f"Using token: {masked_token}")
    else:
        print("No GitHub token found in .env file")

    return token


def get_github_username(token: str) -> str | None:
    """Get GitHub username using the token."""
    try:
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        response = requests.get("https://api.github.com/user", headers=headers)
        if response.status_code == 200:
            return response.json()["login"]
        else:
            print(f"Failed to get GitHub username: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error getting GitHub username: {e}")
        return None


def create_github_repo(token: str, repo_name: str, private: bool = False) -> bool:
    """Create a new repository on GitHub."""
    try:
        username = get_github_username(token)
        if not username:
            return False

        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

        data = {
            "name": repo_name,
            "private": private,
            "auto_init": False,
            "description": f"Created automatically on {datetime.now().strftime('%Y-%m-%d')}",
        }

        response = requests.post("https://api.github.com/user/repos", headers=headers, json=data)

        if response.status_code == 201:
            print(f"✅ Successfully created repository: {username}/{repo_name}")
            return True
        elif response.status_code == 422:
            print(f"Repository '{repo_name}' already exists on GitHub")
            return True  # Repository exists, that's fine
        else:
            print(f"Failed to create repository: {response.status_code}")
            print(f"Response: {response.json().get('message', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"Error creating repository: {e}")
        return False


def get_remote_url_from_local(repo: Repo) -> tuple[str, str] | None:
    """Extract GitHub username and repo name from existing remote URL."""
    try:
        for remote in repo.remotes:
            for url in remote.urls:
                if "github.com" in url:
                    # Handle different URL formats
                    if url.startswith("https://github.com/"):
                        path = url.replace("https://github.com/", "")
                        parts = path.rstrip("/").split("/")
                        if len(parts) >= 2:
                            return parts[0], parts[1].replace(".git", "")
                    elif url.startswith("git@github.com:"):
                        path = url.replace("git@github.com:", "")
                        parts = path.rstrip("/").split("/")
                        if len(parts) >= 2:
                            return parts[0], parts[1].replace(".git", "")
        return None
    except Exception:
        return None


def setup_remote_repo(repo: Repo, token: str, create_if_missing: bool) -> bool:
    """Setup remote repository, optionally creating it on GitHub."""

    # Check if remote already exists
    if repo.remotes:
        print(f"Remote already configured: {repo.remotes[0].urls[0]}")
        return True

    # Get the repository name from current directory
    repo_name = Path.cwd().name

    # Ask user for repository name (with current dir name as default)
    print(f"\nNo remote repository configured.")
    if create_if_missing:
        print(f"Will attempt to create ' {repo_name}' on GitHub...")

        # Ask if user wants private or public repo
        private_input = input("Create as private repository? (y/n) [n]: ").lower()
        is_private = private_input == "y"

        if create_github_repo(token, repo_name, is_private):
            username = get_github_username(token)
            if username:
                remote_url = f"https://github.com/{username}/{repo_name}.git"
                print(f"Adding remote: {remote_url}")
                repo.create_remote("origin", remote_url)
                return True
    else:
        print("To create a remote repository automatically, use the --create flag")
        print(f"Or manually add a remote: git remote add origin <your-repo-url>")

    return False


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
                        # Preserve the username/repo part
                        new_url = url.replace("https://", f"https://oauth2:{token}@")
                        if new_url != url:
                            remote.set_url(new_url)
                            print(f"✅ Updated remote URL with token authentication")
                            return
        print("Remote URL already has authentication or is not HTTPS")
    except Exception as e:
        print(f"Could not update remote URL: {e}")
        # Fallback to credential helper
        try:
            os.system(
                f'git config --local credential.helper "!f() echo username=oauth2; echo password={token}; exit 0; f"'
            )
            print("Set up credential helper as fallback")
        except Exception:
            pass


def push_to_remote(repo: Repo, token: str = None) -> None:
    """Push to remote repository using token if provided."""
    try:
        # Check if any remotes are configured
        if not repo.remotes:
            print("❌ No remote repository configured. Skipping push.")
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

        print(f"\nPushing to remote '{remote.name}'...")

        # Setup authentication if token is available
        if token:
            setup_git_auth(repo, token)

        # Set upstream for first push
        try:
            # Try to push with upstream setting
            push_result = remote.push(refspec=f"{current_branch}:{current_branch}", set_upstream=True)
        except Exception:
            # Fallback to regular push
            push_result = remote.push()

        # Check push results
        success = False
        for result in push_result:
            if result.flags & result.ERROR:
                print(f"❌ Push failed: {result.summary}", file=sys.stderr)
                if "403" in result.summary or "401" in result.summary:
                    print("Authentication failed. Check your GitHub token.", file=sys.stderr)
                    print("Make sure your token has 'repo' scope for private repos or 'public_repo' for public repos.")
                return
            elif result.flags & result.UP_TO_DATE:
                print("✅ Remote is already up to date.")
                success = True
            elif result.flags & result.FAST_FORWARD:
                print(f"✅ Successfully pushed to {remote.name}/{current_branch}")
                success = True
            else:
                print(f"Push result: {result.summary}")
                success = True

        if success:
            print("\n🎉 All done! Changes are now on GitHub.")

    except Exception as e:
        print(f"❌ Push failed: {e}", file=sys.stderr)
        print("Commit was successful, but push failed. You can push manually later.")


def main() -> None:
    # Parse command line arguments
    args = parse_arguments()

    # Load token from script directory
    token = load_git_token()

    if args.create and not token:
        print("❌ Cannot create repository: No GitHub token found.", file=sys.stderr)
        print("Please set GITHUB_TOKEN in ~/bin/.env", file=sys.stderr)
        sys.exit(1)

    cwd = Path.cwd()
    try:
        repo = Repo(cwd, search_parent_directories=True)
        print(f"Found existing git repository at {repo.git_dir}")

        # Try to setup remote if missing and create flag is True
        if args.create and not repo.remotes:
            if not setup_remote_repo(repo, token, True):
                print("❌ Failed to setup remote repository", file=sys.stderr)
                sys.exit(1)

    except InvalidGitRepositoryError:
        repo = Repo.init(cwd)
        print("✅ Repository initialized.")

        # Setup remote if create flag is True
        if args.create:
            if setup_remote_repo(repo, token, True):
                print("✅ Remote repository configured")
            else:
                print("❌ Failed to setup remote repository", file=sys.stderr)
                sys.exit(1)
        else:
            print("\nTip: Use --create flag to automatically create a GitHub repository")
            print(f"Tip: Or manually add a remote with: git remote add origin <your-repo-url>")

    # Check if there are changes to commit
    if not repo.is_dirty(untracked_files=True):
        print("\n📝 No changes to commit.")
        # Still try to push if there are unpushed commits
        if repo.remotes:
            try:
                # Check if we have commits to push
                current_branch = repo.active_branch
                remote_refs = repo.remotes[0].refs
                if current_branch.name in remote_refs:
                    remote_branch = remote_refs[current_branch.name]
                    if repo.git.rev_list(f"{remote_branch}..{current_branch}"):
                        print("Found unpushed commits. Pushing...")
                        push_to_remote(repo, token)
                    else:
                        print("✅ Remote is up to date.")
                else:
                    print("Remote branch doesn't exist. Pushing...")
                    push_to_remote(repo, token)
            except Exception as e:
                print(f"Push check failed: {e}")
        return

    # Add and commit changes
    print("\n📦 Changes detected. Adding all files...")
    repo.git.add("--all")

    commit_message = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        commit = repo.index.commit(commit_message)
        print(f'✅ Committed with message: "{commit_message}"')
        print(f"Commit hash: {commit.hexsha[:7]}")
    except Exception as e:
        print(f"❌ Commit failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Push to remote
    push_to_remote(repo, token)


if __name__ == "__main__":
    main()
