#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from github import Github
from github.GithubException import GithubException, UnknownObjectException
from github.Repository import Repository
from tqdm import tqdm


def get_github_client(token: str | None = None) -> Github:
    return Github(auth=github.Auth.Token(token)) if token else Github()


def parse_repo_url(txt: str) -> tuple[str, str]:
    txt = txt.strip()
    if txt.endswith(".git"):
        txt = txt[:-4]
    if txt.startswith("git@github.com:"):
        txt = txt.replace("git@github.com:", "")
    if txt.startswith(("http://", "https://")):
        txt = txt.split("github.com/", 1)[-1]

    parts = [p for p in txt.split("/") if p]
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    raise ValueError(f"Invalid repository format: '{txt}'. Expected 'owner/repo' or URL.")


def get_repo(repo_url: str, github_client: Github) -> Repository:
    owner, repo_name = parse_repo_url(repo_url)
    full_slug = f"{owner}/{repo_name}"
    print(f"[INFO] Fetching repository metadata: {full_slug}")
    try:
        # Handles both individual users and organizations properly
        repo = github_client.get_repo(full_slug)
        print(f"[INFO] Repository found: {repo.full_name}")
        return repo
    except UnknownObjectException:
        raise ValueError(f"Repository not found or private: {full_slug}")
    except GithubException as e:
        raise Exception(f"GitHub API error ({e.status}): {e.data.get('message', str(e))}")


def get_repo_size(repo: Repository) -> float:
    try:
        size_mb = repo.size / 1024
        print(f"[INFO] Repository size: {size_mb:.2f} MB")
        return size_mb
    except Exception as e:
        print(f"[WARNING] Could not fetch repo size: {e}")
        return 0.0


def clone_repo(clone_url: str, branch: str, shallow: bool = False) -> str:
    # Target directory name from repository URL
    owner, repo_name = parse_repo_url(clone_url)

    cmd = ["git", "clone"]
    if shallow:
        print("[INFO] Shallow cloning enabled (--depth 1)")
        cmd.extend(["--depth", "1"])

    cmd.extend(["--branch", branch, "--progress", clone_url])
    print(f"[INFO] Cloning repository from {clone_url} (branch: {branch})")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,  # Prevent stdout pipe deadlock
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        if process.stderr:
            for line in process.stderr:
                line = line.strip()
                if not line:
                    continue
                if "Receiving objects:" in line or "Resolving deltas:" in line:
                    match = re.search(r"(\d+)%.*?(\d+\.?\d*)\s*([KM]iB)", line)
                    if match:
                        percent, size, unit = match.groups()
                        tqdm.write(f"[PROGRESS] {percent}% ({size} {unit})")
                    else:
                        tqdm.write(f"[PROGRESS] {line}")
                elif "fatal:" in line:
                    raise RuntimeError(line)
                else:
                    tqdm.write(f"[INFO] {line}")

        returncode = process.wait()
        if returncode != 0:
            raise RuntimeError(f"git clone exited with code {returncode}")

        print("[INFO] Clone completed successfully.")
        return repo_name
    except Exception as e:
        raise RuntimeError(f"Clone failed: {e}")


def init_submodules(repo_dir: str) -> None:
    gitmodules_path = Path(repo_dir) / ".gitmodules"
    if not gitmodules_path.exists():
        return

    print(f"\n[INFO] Submodules detected in '{repo_dir}'. Initialize and update? (y/n)")
    if input("> ").strip().lower() != "y":
        return

    try:
        print("[INFO] Initializing and updating submodules...")
        subprocess.run(
            ["git", "submodule", "update", "--init", "--recursive"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        print("[INFO] Submodules updated successfully.")
    except subprocess.CalledProcessError as e:
        print(f"[WARNING] Submodule update failed: {e.stderr.strip()}")


def confirm_large_repo(size_mb: float) -> bool:
    if size_mb > 5.0:
        print(f"[WARNING] Repository size is {size_mb:.2f} MB. Continue download? (y/n)")
        return input("> ").strip().lower() == "y"
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clone GitHub repositories with optional API authentication and submodule handling."
    )
    parser.add_argument("repo_url", help="Repository URL or slug (e.g., owner/repo, https://github.com/owner/repo)")
    parser.add_argument("-s", "--shallow", action="store_true", help="Perform a shallow clone (--depth 1)")
    parser.add_argument("--token", type=str, default=None, help="GitHub Personal Access Token")

    args = parser.parse_args()

    # Import auth explicitly for modern PyGithub versions
    import github.Auth

    github_client = get_github_client(args.token)
    if args.token:
        try:
            user = github_client.get_user().login
            print(f"[INFO] Authenticated as: {user}")
        except GithubException as e:
            print(f"[ERROR] Invalid token or authentication failed: {e}")
            sys.exit(1)

    try:
        repo = get_repo(args.repo_url, github_client)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    size_mb = get_repo_size(repo)
    if not confirm_large_repo(size_mb):
        print("[INFO] Operation aborted by user.")
        sys.exit(0)

    default_branch = repo.default_branch or "main"
    clone_url = repo.clone_url

    try:
        repo_dir = clone_repo(clone_url, default_branch, shallow=args.shallow)
    except Exception as e:
        err_msg = str(e).lower()
        if "fatal:" in err_msg or "not found" in err_msg:
            alt_branch = "master" if default_branch == "main" else "main"
            print(f"[WARNING] Primary branch '{default_branch}' failed. Attempting fallback branch '{alt_branch}'...")
            try:
                repo_dir = clone_repo(clone_url, alt_branch, shallow=args.shallow)
            except Exception as e2:
                print(f"[ERROR] Both primary and fallback branch clones failed: {e2}")
                sys.exit(1)
        else:
            print(f"[ERROR] {e}")
            sys.exit(1)

    init_submodules(repo_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Cancelled by user.")
        sys.exit(1)
