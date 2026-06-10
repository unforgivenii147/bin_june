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
import re

from git import Repo, InvalidGitRepositoryError


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Commit and push all files to git repository")
    parser.add_argument(
        "-c", "--create", action="store_true", help="Create remote repository on GitHub if it doesn't exist"
    )
    parser.add_argument("-r", "--remote-name", default="origin", help="Remote name to use (default: origin)")
    return parser.parse_args()


def load_git_token() -> str | None:
    """Load GitHub token from .env file in the script's directory."""
    # Get the directory where this script is located
    home_dir = Path.home()
    env_path = home_dir / ".env"

    # Also check home directory
    home_env = Path.home() / ".env"

    env_file = None
    if env_path.exists():
        env_file = env_path
    elif home_env.exists():
        env_file = home_env

    if env_file:
        load_dotenv(env_file)
        print(f"Loaded environment from {env_file}")
    else:
        print(f"No .env file found")
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


def create_github_repo(token: str, repo_name: str, description: str = "", private: bool = False) -> str:
    """Create a new repository on GitHub."""
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    data = {
        "name": repo_name,
        "description": description or f"Created automatically on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "private": private,
        "auto_init": False,  # Don't auto_init to avoid conflicts with existing files
    }

    response = requests.post("https://api.github.com/user/repos", json=data, headers=headers)

    if response.status_code == 201:
        repo_url = response.json()["html_url"]
        clone_url = response.json()["clone_url"]
        print(f"✅ Repository created: {repo_url}")
        return clone_url
    elif response.status_code == 422:
        # Repository already exists
        print(f"ℹ️ Repository '{repo_name}' already exists on GitHub")
        # Try to get the clone URL for existing repo
        username = get_github_username(token)
        if username:
            return f"https://github.com/{username}/{repo_name}.git"
        raise Exception("Repository already exists and couldn't determine URL")
    else:
        error_msg = response.json().get("message", "Unknown error")
        raise Exception(f"GitHub API error ({response.status_code}): {error_msg}")


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


def get_current_dir_name() -> str:
    """Get current directory name, cleaning it for use as repo name."""
    dir_name = Path.cwd().name
    # Remove invalid characters for GitHub repo names
    dir_name = re.sub(r"[^\w\-\.]", "-", dir_name)
    # Convert to lowercase (GitHub convention)
    return dir_name.lower()


def clean_remote_config(repo: Repo):
    """Remove invalid remote configurations."""
    try:
        for remote in repo.remotes:
            # Skip if remote has no URLs or invalid URL
            try:
                urls = list(remote.urls)
                if not urls:
                    print(f"⚠️ Remote '{remote.name}' has no URLs, removing...")
                    repo.delete_remote(remote)
                elif "set-url" in remote.name or remote.name == "set-url":
                    print(f"⚠️ Removing invalid remote '{remote.name}'...")
                    repo.delete_remote(remote)
            except Exception:
                print(f"⚠️ Removing problematic remote '{remote.name}'...")
                repo.delete_remote(remote)
    except Exception as e:
        print(f"Note: Could not clean remotes: {e}")


def setup_remote_repo(repo: Repo, token: str, remote_name: str, create_if_missing: bool) -> bool:
    """Setup remote repository, optionally creating it on GitHub."""

    # Clean any invalid remotes first
    clean_remote_config(repo)

    # Check if the desired remote already exists and has valid URL
    existing_remote = None
    try:
        if remote_name in [r.name for r in repo.remotes]:
            existing_remote = repo.remote(remote_name)
            # Check if URL is valid
            try:
                list(existing_remote.urls)
                print(f"Remote '{remote_name}' already configured: {existing_remote.url}")
                return True
            except Exception:
                print(f"⚠️ Remote '{remote_name}' has invalid URL, removing...")
                repo.delete_remote(existing_remote)
                existing_remote = None
    except Exception:
        pass

    # Get the repository name from current directory
    repo_name = get_current_dir_name()
    print(f"📁 Using directory name as repo name: {repo_name}")

    if not create_if_missing:
        print("\n⚠️ No remote repository configured.")
        print(f"Tip: Use --create flag to automatically create a GitHub repository")
        print(f"   Example: python {sys.argv[0]} --create")
        print(f"   Or manually add a remote: git remote add {remote_name} <your-repo-url>")
        return False

    # Create repository on GitHub
    print(f"\n🚀 Creating GitHub repository: {repo_name}")

    # Ask if user wants private or public repo
    private_input = input("Create as private repository? (y/n) [n]: ").lower()
    is_private = private_input == "y"

    try:
        # Optional: Ask for description
        description = input("Repository description (optional, press Enter to skip): ").strip()

        clone_url = create_github_repo(token, repo_name, description, is_private)
        print(f"Adding remote '{remote_name}': {clone_url}")
        repo.create_remote(remote_name, clone_url)
        return True
    except Exception as e:
        print(f"❌ Failed to create repository: {e}")
        return False


def setup_git_auth(repo: Repo, token: str = None) -> None:
    """Configure git authentication using token."""
    if not token:
        return

    try:
        # Update remote URL with token for authentication
        for remote in repo.remotes:
            for url in remote.urls:
                if "github.com" in url:
                    # Check if URL already has authentication
                    if "@github.com" in url:
                        print("Remote URL already has authentication")
                        return
                    elif url.startswith("https://"):
                        # Insert token for authentication
                        new_url = url.replace("https://", f"https://oauth2:{token}@")
                        remote.set_url(new_url)
                        print(f"✅ Updated remote URL with token authentication")
                        return
                    elif url.startswith("git@github.com:"):
                        print("Using SSH authentication (no token needed)")
                        return
    except Exception as e:
        print(f"Could not update remote URL: {e}")


def push_to_remote(repo: Repo, remote_name: str, token: str = None) -> None:
    """Push to remote repository using token if provided."""
    try:
        # Check if remote exists
        if remote_name not in [r.name for r in repo.remotes]:
            print(f"❌ Remote '{remote_name}' not configured. Skipping push.")
            return

        remote = repo.remote(remote_name)

        # Get current branch name
        try:
            current_branch = repo.active_branch.name
        except TypeError:
            # Detached HEAD state
            print("In detached HEAD state. Skipping push.")
            return

        print(f"\n📤 Pushing to remote '{remote_name}'...")

        # Setup authentication if token is available
        if token:
            setup_git_auth(repo, token)

        # Push to remote with upstream setting
        try:
            # Try to push and set upstream
            push_result = remote.push(refspec=f"{current_branch}:{current_branch}", set_upstream=True)
        except Exception as e:
            if "no upstream branch" in str(e):
                print(f"Setting upstream and pushing...")
                # Set upstream and push
                repo.git.push("--set-upstream", remote_name, current_branch)
                push_result = []
            else:
                raise e

        # Check push results
        success = False
        if push_result:
            for result in push_result:
                if hasattr(result, "flags") and result.flags & result.ERROR:
                    print(f"❌ Push failed: {result.summary}", file=sys.stderr)
                    if "403" in result.summary or "401" in result.summary:
                        print("🔐 Authentication failed. Check your GitHub token.", file=sys.stderr)
                    return
                elif hasattr(result, "flags") and result.flags & result.UP_TO_DATE:
                    print("✅ Remote is already up to date.")
                    success = True
                elif hasattr(result, "flags") and result.flags & result.FAST_FORWARD:
                    print(f"✅ Successfully pushed to {remote_name}/{current_branch}")
                    success = True
                else:
                    print(f"✅ Push successful")
                    success = True
        else:
            # If we used git push command directly
            success = True
            print(f"✅ Successfully pushed to {remote_name}/{current_branch}")

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
        print("Please set GITHUB_TOKEN in ~/bin/.env or ~/.env", file=sys.stderr)
        sys.exit(1)

    cwd = Path.cwd()
    repo = None

    try:
        repo = Repo(cwd, search_parent_directories=True)
        print(f"Found existing git repository at {repo.git_dir}")

        # Clean any invalid remote configurations
        clean_remote_config(repo)

    except InvalidGitRepositoryError:
        repo = Repo.init(cwd)
        print("✅ Repository initialized.")

    # Setup remote if needed
    if not repo.remotes or args.create:
        if setup_remote_repo(repo, token, args.remote_name, args.create):
            print("✅ Remote repository configured")
        elif not args.create:
            # No remote and not creating, continue without pushing
            pass

    # Check if there are changes to commit
    if not repo.is_dirty(untracked_files=True):
        print("\n📝 No changes to commit.")
        # Still try to push if there are unpushed commits
        if repo.remotes:
            try:
                # Get current branch
                current_branch = repo.active_branch

                # Check if remote branch exists
                remote_name = args.remote_name
                if remote_name in [r.name for r in repo.remotes]:
                    remote = repo.remote(remote_name)
                    try:
                        # Try to see if remote branch exists
                        remote_ref = f"refs/remotes/{remote_name}/{current_branch.name}"
                        if remote_ref in repo.refs:
                            # Check for unpushed commits
                            remote_commit = repo.refs[remote_ref].commit
                            if current_branch.commit != remote_commit:
                                print("Found unpushed commits. Pushing...")
                                push_to_remote(repo, remote_name, token)
                            else:
                                print("✅ Remote is up to date.")
                        else:
                            print("Remote branch doesn't exist. Pushing...")
                            push_to_remote(repo, remote_name, token)
                    except Exception as e:
                        print(f"Remote exists but check failed: {e}")
                        push_to_remote(repo, remote_name, token)
                else:
                    print(f"Remote '{remote_name}' not found.")
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
    if repo.remotes and args.remote_name in [r.name for r in repo.remotes]:
        push_to_remote(repo, args.remote_name, token)
    elif repo.remotes:
        print(f"\n⚠️ Remote '{args.remote_name}' not found. Available remotes: {[r.name for r in repo.remotes]}")
        print("Changes committed locally only.")
    else:
        print("\n⚠️ No remote configured. Changes committed locally only.")
        if args.create:
            print("Use --create flag to create and push to GitHub.")


if __name__ == "__main__":
    main()
