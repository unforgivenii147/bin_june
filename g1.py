#!/data/data/com.termux/files/usr/bin/python
import os
import re
import sys
from pathlib import Path
from github import Github
from github.GithubException import GithubException, UnknownObjectException
from tqdm import tqdm
from dotenv import load_dotenv
import git
from git.exc import GitCommandError, InvalidGitRepositoryError


def load_github_token() -> str | None:
    """Load GitHub token from .env file or environment variable"""
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if token:
        print("[INFO] GitHub token loaded from .env file")
    return token


def get_github_client(token: str | None = None) -> Github:
    if token:
        return Github(token)
    return Github()


def parse_repo_url(txt: str) -> tuple[str, str]:
    txt = txt.strip()
    if txt.endswith(".git"):
        txt = txt[:-4]
    if txt.startswith("git@github.com:"):
        txt = txt.replace("git@github.com:", "")
    if txt.startswith("http://") or txt.startswith("https://"):
        txt = txt.split("github.com/", 1)[-1]
    parts = txt.split("/")
    if len(parts) >= 2:
        return (parts[-2], parts[-1])
    raise ValueError(f"Invalid repository format: {txt}")


def get_repo(repo_url: str, github_client: Github):
    try:
        owner, repo_name = parse_repo_url(repo_url)
        print(f"[INFO] Fetching repository: {owner}/{repo_name}")
        repo = github_client.get_user(owner).get_repo(repo_name)
        _ = repo.size
        print(f"[INFO] Repository found: {repo.full_name}")
        return repo
    except UnknownObjectException:
        raise ValueError(f"Repository not found: {repo_url}")
    except GithubException as e:
        raise Exception(f"GitHub API error: {e.status} {e.data}")


def get_repo_size(repo) -> float:
    try:
        size_kb = repo.size
        size_mb = size_kb / 1024
        print(f"[INFO] Repository size: {size_mb:.2f} MB")
        return size_mb
    except Exception as e:
        print(f"[ERROR] Could not fetch repo size: {e}")
        return 0


def get_default_branch(repo) -> str:
    try:
        default_branch = repo.default_branch
        print(f"[INFO] Default branch: {default_branch}")
        return default_branch
    except Exception as e:
        print(f"[WARNING] Could not determine default branch: {e}")
        return "main"


def build_clone_url(repo) -> str:
    return repo.clone_url


def clone_repo_with_progress(clone_url: str, branch: str, target_dir: str = ".") -> git.Repo:
    """Clone repository with progress tracking"""
    print(f"[INFO] Cloning repository from {clone_url} (branch: {branch})")

    try:
        # Clone with progress callback
        repo = git.Repo.clone_from(
            clone_url, target_dir, branch=branch, depth=1, single_branch=True, progress=GitProgress()
        )
        print("[INFO] Clone completed successfully.")
        return repo
    except GitCommandError as e:
        raise Exception(f"Clone failed: {e}")


class GitProgress(git.RemoteProgress):
    """Custom progress handler for GitPython"""

    def update(self, op_code, cur_count, max_count=None, message=""):
        if max_count:
            percent = (cur_count / max_count) * 100
            if op_code & self.OP_CHECKOUT:
                stage = "Checking out"
            elif op_code & self.OP_CLONE:
                stage = "Cloning"
            else:
                stage = "Transferring"

            # Format size if available
            if max_count > 1024 * 1024:
                size_mb = max_count / (1024 * 1024)
                cur_mb = cur_count / (1024 * 1024)
                tqdm.write(f"[PROGRESS] {stage}: {percent:.1f}% ({cur_mb:.1f}/{size_mb:.1f} MB)")
            elif max_count > 1024:
                size_kb = max_count / 1024
                cur_kb = cur_count / 1024
                tqdm.write(f"[PROGRESS] {stage}: {percent:.1f}% ({cur_kb:.1f}/{size_kb:.1f} KB)")
            else:
                tqdm.write(f"[PROGRESS] {stage}: {percent:.1f}% ({cur_count}/{max_count} objects)")
        elif message:
            tqdm.write(f"[PROGRESS] {message.strip()}")


def init_submodules(repo: git.Repo) -> None:
    """Initialize and update submodules using GitPython"""
    # Check if .gitmodules exists
    gitmodules_path = Path(".gitmodules")
    if not gitmodules_path.exists():
        return

    print("[INFO] Submodules found. Initialize and update? (y/n)")
    if input().lower() != "y":
        return

    try:
        print("[INFO] Initializing and updating submodules...")
        # Initialize submodules
        repo.git.submodule("init")
        # Update submodules recursively
        repo.git.submodule("update", "--init", "--recursive")
        print("[INFO] Submodules updated successfully.")
    except GitCommandError as e:
        raise Exception(f"Submodule update failed: {e}")


def confirm_large_repo(size_mb: float) -> bool:
    if size_mb > 100:
        print(f"[WARNING] Repository size is {size_mb:.2f} MB. Continue? (y/n)")
        return input().lower() == "y"
    return True


def main():
    if len(sys.argv) < 2:
        print("[ERROR] Please provide a repository URL")
        print("Usage: python script.py <repo_url> [--token <token>]")
        return

    repo_url = sys.argv[1].strip()

    # Check for manual token override
    token = None
    if "--token" in sys.argv:
        token_idx = sys.argv.index("--token") + 1
        if token_idx < len(sys.argv):
            token = sys.argv[token_idx]
            print("[INFO] Using token from command line")
    else:
        # Try to load token from .env
        token = load_github_token()

    try:
        github_client = get_github_client(token)
        if token:
            user = github_client.get_user()
            print(f"[INFO] Authenticated as: {user.login}")
        else:
            print("[INFO] No authentication token provided (rate limits may apply)")
    except GithubException as e:
        print(f"[ERROR] Authentication failed: {e}")
        return

    try:
        repo = get_repo(repo_url, github_client)
    except (ValueError, Exception) as e:
        print(f"[ERROR] {e}")
        return

    size_mb = get_repo_size(repo)
    if not confirm_large_repo(size_mb):
        print("[INFO] Aborted by user.")
        return

    default_branch = get_default_branch(repo)
    clone_url = build_clone_url(repo)

    # Try to clone with default branch
    try:
        git_repo = clone_repo_with_progress(clone_url, default_branch)
    except Exception as e:
        if "not found" in str(e).lower() or "does not exist" in str(e).lower():
            alt_branch = "master" if default_branch == "main" else "main"
            print(f"[WARNING] Branch '{default_branch}' failed, trying '{alt_branch}'...")
            try:
                git_repo = clone_repo_with_progress(clone_url, alt_branch)
            except Exception as e2:
                print(f"[ERROR] Clone with both branches failed: {e2}")
                return
        else:
            print(f"[ERROR] {e}")
            return

    # Handle submodules
    try:
        init_submodules(git_repo)
    except Exception as e:
        print(f"[WARNING] Submodule handling failed: {e}")


if __name__ == "__main__":
    main()
