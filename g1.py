#!/usr/bin/env python3
"""
Git repository cloner with support for shallow clones and branch selection.
Uses only Python libraries (no subprocess) with dotenv support for tokens.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from typing import Optional, Tuple, Dict, Any
from dotenv import load_dotenv

# Try to import git libraries
try:
    import git
    from git.repo import Repo
    from git.exc import GitCommandError, InvalidGitRepositoryError
except ImportError:
    print("Error: gitpython library not installed. Run: pip install gitpython python-dotenv")
    sys.exit(1)

# Try to import requests for API calls
try:
    import requests
except ImportError:
    print("Warning: requests library not installed. Size checking will be disabled.")
    print("Install with: pip install requests")
    requests = None

load_dotenv()


def parse_repo_input(repo_input: str) -> Tuple[str, Optional[str], Optional[str]]:

    # Check if it's a full URL
    if repo_input.startswith(("http://", "https://", "git@", "ssh://")):
        parsed = urlparse(repo_input)
        # Extract provider and path
        provider = parsed.netloc
        # Remove .git suffix if present
        path = parsed.path.rstrip(".git")
        # Remove leading slash
        if path.startswith("/"):
            path = path[1:]
        return repo_input, provider, path

    # Check if it's a provider-specific short format (e.g., gitlab.com:user/repo)
    if ":" in repo_input and not repo_input.startswith("git@"):
        parts = repo_input.split(":", 1)
        if "." in parts[0]:  # Has domain
            provider = parts[0]
            repo_path = parts[1]
            return f"https://{provider}/{repo_path}.git", provider, repo_path

    # Handle format like "user/repo" or "group/user/repo"
    if "/" in repo_input:
        # Assume github.com as default
        return f"https://github.com/{repo_input}.git", "github.com", repo_input

    raise ValueError(f"Unrecognized repository format: {repo_input}")


def get_authenticated_url(repo_url: str) -> str:

    parsed = urlparse(repo_url)

    # Check if we need authentication (private repo)
    if parsed.netloc == "github.com":
        token = os.getenv("GITHUB_TOKEN")
        if token:
            print("✓ Using GitHub token for authentication")
            # Insert token into URL: https://token@github.com/user/repo.git
            return urlunparse(
                (parsed.scheme, f"{token}@{parsed.netloc}", parsed.path, parsed.params, parsed.query, parsed.fragment)
            )

    elif parsed.netloc == "gitlab.com":
        token = os.getenv("GITLAB_TOKEN")
        if token:
            print("✓ Using GitLab token for authentication")
            return urlunparse(
                (
                    parsed.scheme,
                    f"oauth2:{token}@{parsed.netloc}",
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )

    elif "bitbucket" in parsed.netloc:
        token = os.getenv("BITBUCKET_TOKEN")
        if token:
            print("✓ Using Bitbucket token for authentication")
            return urlunparse(
                (parsed.scheme, f"{token}@{parsed.netloc}", parsed.path, parsed.params, parsed.query, parsed.fragment)
            )

    return repo_url


def format_size(size_bytes: int) -> str:

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def get_github_repo_size(owner: str, repo: str, token: Optional[str] = None) -> Optional[int]:

    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
        headers["Accept"] = "application/vnd.github.v3+json"

    url = f"https://api.github.com/repos/{owner}/{repo}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # GitHub API returns size in KB
            size_kb = data.get("size", 0)
            size_bytes = size_kb * 1024
            return size_bytes
        elif response.status_code == 404:
            print(f"⚠ Repository not found on GitHub: {owner}/{repo}")
            return None
        elif response.status_code == 403:
            print(f"⚠ API rate limit exceeded. Consider setting GITHUB_TOKEN in .env")
            return None
        else:
            print(f"⚠ Could not fetch repo size (HTTP {response.status_code})")
            return None
    except Exception as e:
        print(f"⚠ Error fetching GitHub repo size: {e}")
        return None


def get_gitlab_repo_size(project_path: str, token: Optional[str] = None) -> Optional[int]:

    headers = {}
    if token:
        headers["PRIVATE-TOKEN"] = token

    # URL encode the project path
    import urllib.parse

    encoded_path = urllib.parse.quote(project_path, safe="")
    url = f"https://gitlab.com/api/v4/projects/{encoded_path}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # GitLab returns size in bytes
            size_bytes = data.get("repository_size", 0)
            # Also check for storage size
            if size_bytes == 0:
                size_bytes = data.get("statistics", {}).get("repository_size", 0)
            return size_bytes
        elif response.status_code == 404:
            print(f"⚠ Project not found on GitLab: {project_path}")
            return None
        else:
            print(f"⚠ Could not fetch repo size (HTTP {response.status_code})")
            return None
    except Exception as e:
        print(f"⚠ Error fetching GitLab repo size: {e}")
        return None


def get_bitbucket_repo_size(workspace: str, repo_slug: str, token: Optional[str] = None) -> Optional[int]:

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Bitbucket doesn't directly provide size, estimate from clone URL or use size field if available
            size_bytes = data.get("size", 0)
            if size_bytes == 0:
                # Fallback: estimate from UUID or return None
                return None
            return size_bytes
        else:
            print(f"⚠ Could not fetch repo size (HTTP {response.status_code})")
            return None
    except Exception as e:
        print(f"⚠ Error fetching Bitbucket repo size: {e}")
        return None


def get_repo_size(provider: str, repo_path: str) -> Optional[int]:

    if not requests:
        print("⚠ Size checking disabled (requests library not installed)")
        return None

    print(f"\n📊 Checking repository size...")

    if provider == "github.com":
        # Parse owner/repo from path
        parts = repo_path.split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            token = os.getenv("GITHUB_TOKEN")
            size = get_github_repo_size(owner, repo, token)
            if size is not None:
                print(f"   Repository size: {format_size(size)}")
            return size

    elif provider == "gitlab.com":
        token = os.getenv("GITLAB_TOKEN")
        size = get_gitlab_repo_size(repo_path, token)
        if size is not None:
            print(f"   Repository size: {format_size(size)}")
        return size

    elif "bitbucket" in provider:
        # Parse workspace/repo_slug from path
        parts = repo_path.split("/")
        if len(parts) >= 2:
            workspace, repo_slug = parts[0], parts[1]
            token = os.getenv("BITBUCKET_TOKEN")
            size = get_bitbucket_repo_size(workspace, repo_slug, token)
            if size is not None:
                print(f"   Repository size: {format_size(size)}")
            return size

    else:
        print(f"⚠ Size checking not supported for provider: {provider}")

    return None


def confirm_clone(size_bytes: Optional[int], threshold_gb: float = 10) -> bool:

    if size_bytes is None:
        return True  # No size info, proceed

    threshold_bytes = threshold_gb * 1024 * 1024 * 1024

    if size_bytes > threshold_bytes:
        print(f"\n⚠⚠⚠  WARNING: Repository is LARGE ({format_size(size_bytes)})  ⚠⚠⚠")
        print(f"   Cloning a repository this size may take significant time and disk space.")
        print(f"   Consider using shallow clone (--depth 1) which is already enabled.")

        while True:
            response = input(f"\n   Continue with clone? (y/N): ").lower().strip()
            if response in ["y", "yes"]:
                print("   Continuing with clone...")
                return True
            elif response in ["n", "no", ""]:
                print("   Clone cancelled by user.")
                return False
            else:
                print("   Please answer 'y' or 'n'")
    else:
        if size_bytes > 100 * 1024 * 1024:  # Show info for repos > 100MB
            print(f"   Note: Repository size is {format_size(size_bytes)}")

    return True


def determine_branch(repo: Repo, target_branch: str) -> Optional[str]:

    try:
        # Try to find the branch in remote references
        remote_refs = repo.remote().refs

        # Check for target branch (master or main)
        branch_ref = None
        for ref in remote_refs:
            if ref.name.endswith(f"/{target_branch}"):
                branch_ref = ref
                break

        if branch_ref:
            print(f"✓ Found branch: {target_branch}")
            return target_branch

        # If target branch not found and it was 'master', try 'main'
        if target_branch == "master":
            print(f"⚠ Branch 'master' not found, trying 'main'...")
            for ref in remote_refs:
                if ref.name.endswith("/main"):
                    print(f"✓ Found branch: main")
                    return "main"

        # If no branch found, get default branch
        print(f"⚠ Branch '{target_branch}' not found, using default branch")
        return None

    except Exception as e:
        print(f"⚠ Could not determine branches: {e}")
        return None


def clone_repository(repo_url: str, target_dir: str, branch: str = "master", depth: int = 1):

    target_path = Path(target_dir)

    # Prepare URL with authentication
    auth_url = get_authenticated_url(repo_url)

    print(f"\n📦 Cloning repository:")
    print(f"   URL: {repo_url}")
    print(f"   Target: {target_path.absolute()}")
    print(f"   Branch: {branch} (will fallback to 'main' if needed)")
    if depth:
        print(f"   Depth: {depth} (shallow clone)")
        print(f"   Single branch: Yes")
    else:
        print(f"   Depth: Full history")

    # Check if directory exists
    if target_path.exists():
        if target_path.is_dir() and any(target_path.iterdir()):
            raise FileExistsError(f"Target directory '{target_dir}' already exists and is not empty")
        elif target_path.is_file():
            raise FileExistsError(f"Target path '{target_dir}' exists and is a file")

    # Attempt to clone
    try:
        print("\n🔄 Fetching repository information...")

        # First, try to get remote info to check branches (without cloning)
        temp_repo = None
        actual_branch = branch

        try:
            # Create a temporary in-memory repo to inspect remote
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                temp_repo = Repo.init(tmpdir)
                origin = temp_repo.create_remote("origin", auth_url)
                origin.fetch(depth=1)

                # Determine actual branch
                actual_branch = determine_branch(temp_repo, branch)
                if actual_branch is None and branch == "master":
                    actual_branch = "main"  # Final fallback
                elif actual_branch is None:
                    actual_branch = branch

        except Exception as e:
            print(f"⚠ Could not inspect remote: {e}")
            actual_branch = branch

        # Perform the actual clone
        if depth:
            print(f"\n🚀 Cloning with --depth {depth} --single-branch --branch {actual_branch}...")
            repo = Repo.clone_from(
                auth_url, target_dir, depth=depth, single_branch=True, branch=actual_branch, no_single_branch=False
            )
        else:
            print(f"\n🚀 Cloning full repository --branch {actual_branch}...")
            repo = Repo.clone_from(auth_url, target_dir, branch=actual_branch)

        # Verify clone
        if repo.bare:
            raise Exception("Clone resulted in bare repository")

        # Get clone info
        active_branch = repo.active_branch
        commit = repo.head.commit

        print("\n✅ Clone successful!")
        print(f"   Repository: {repo.remotes.origin.url}")
        print(f"   Branch: {active_branch.name}")
        print(f"   Commit: {commit.hexsha[:8]} ({commit.author}: {commit.message.splitlines()[0][:50]})")
        print(f"   Location: {target_path.absolute()}")

        # Show file count (approximately)
        file_count = sum(1 for _ in target_path.rglob("*") if _.is_file())
        print(f"   Files: ~{file_count}")

        return repo

    except GitCommandError as e:
        print(f"\n❌ Git error: {e}")
        if "Authentication failed" in str(e):
            print("   Hint: Check your token in .env file or use a public repository")
        elif "not found" in str(e):
            print(f"   Hint: Repository or branch '{actual_branch}' may not exist")
        raise
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


def main():

    import argparse

    parser = argparse.ArgumentParser(description="Clone git repositories with shallow clone and branch selection")
    parser.add_argument("repo", help="Repository URL or user/repo (assumes GitHub)")
    parser.add_argument("directory", nargs="?", default=".", help="Target directory (default: current directory)")
    parser.add_argument(
        "--branch", "-b", default="master", help="Branch to clone (default: master, falls back to main)"
    )
    parser.add_argument("--depth", "-d", type=int, default=1, help="Shallow clone depth (default: 1)")
    parser.add_argument("--no-shallow", action="store_true", help="Disable shallow clone (full history)")
    parser.add_argument("--skip-size-check", action="store_true", help="Skip repository size check")
    parser.add_argument(
        "--size-threshold", type=float, default=10, help="Size threshold in GB for confirmation prompt (default: 10)"
    )

    args = parser.parse_args()

    # Adjust depth if shallow clone disabled
    depth = None if args.no_shallow else args.depth

    try:
        # Parse the repository input
        repo_url, provider, repo_path = parse_repo_input(args.repo)
        if provider:
            print(f"🔍 Detected provider: {provider}")

        print(f"📋 Repository URL: {repo_url}")

        # Check repository size (unless skipped)
        if not args.skip_size_check and depth:  # Only check size for shallow clones
            repo_size = get_repo_size(provider, repo_path)
            if not confirm_clone(repo_size, args.size_threshold):
                sys.exit(0)
        elif not args.skip_size_check and not depth:
            print("ℹ️  Full clone requested - size check skipped (would be inaccurate)")

        # Clone the repository
        clone_repository(repo_url=repo_url, target_dir=args.directory, branch=args.branch, depth=depth)

    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Failed to clone repository: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
