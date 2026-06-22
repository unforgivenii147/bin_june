#!/data/data/com.termux/files/usr/bin/python
"""
Create a GitHub repo from the current directory and push,
or commit+push changes if a repo already exists.

Requirements:
    pip install pygit2 PyGithub python-dotenv

~/.env must contain:
    GITHUB_TOKEN=your_token_here
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pygit2
from dotenv import load_dotenv
from github import Github, GithubException

# ── Config ────────────────────────────────────────────────────────────────────

GITHUB_USERNAME = "unforgivenii147"
ENV_FILE = Path.home() / ".env"
REPO_DIR = Path.cwd()


# ── Helpers ───────────────────────────────────────────────────────────────────


def load_token() -> str:
    """Load GITHUB_TOKEN from ~/.env via python-dotenv."""
    if not ENV_FILE.is_file():
        sys.exit(f"[error] ~/.env not found at {ENV_FILE}")

    load_dotenv(dotenv_path=ENV_FILE)
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        sys.exit("[error] GITHUB_TOKEN not set in ~/.env")

    return token


def get_or_create_github_repo(gh: Github, repo_name: str):
    """Return the remote GitHub repo, creating it if it doesn't exist."""
    user = gh.get_user()
    try:
        remote_repo = user.get_repo(repo_name)
        print(f"[info] Found existing GitHub repo: {remote_repo.full_name}")
    except GithubException as exc:
        if exc.status != 404:
            sys.exit(f"[error] GitHub API error: {exc}")
        print(f"[info] Creating new GitHub repo: {GITHUB_USERNAME}/{repo_name}")
        remote_repo = user.create_repo(
            repo_name,
            private=False,
            auto_init=False,
        )
        print(f"[ok] Created: {remote_repo.html_url}")
    return remote_repo


def make_signature() -> pygit2.Signature:
    """Build a pygit2 commit signature using the current time."""
    now = datetime.now(tz=timezone.utc)
    return pygit2.Signature(
        name=GITHUB_USERNAME,
        email=f"{GITHUB_USERNAME}@users.noreply.github.com",
        time=int(now.timestamp()),
        offset=0,
    )


def stage_all(repo: pygit2.Repository) -> bool:
    """
    Stage every change (new, modified, deleted) in the working tree.
    Returns True if there is anything to commit.
    """
    index = repo.index
    index.read()

    status = repo.status()
    if not status:
        print("[info] Nothing to stage — working tree is clean.")
        return False

    for filepath, flags in status.items():
        deleted = flags & (pygit2.GIT_STATUS_WT_DELETED | pygit2.GIT_STATUS_INDEX_DELETED)
        if deleted:
            try:
                index.remove(filepath)
            except KeyError:
                pass  # already absent from index
        else:
            index.add(filepath)

    index.write()
    return True


def commit_all(repo: pygit2.Repository, message: str) -> pygit2.Oid:
    """Create a commit of whatever is currently staged."""
    sig = make_signature()
    tree_oid = repo.index.write_tree()

    parents = []
    try:
        head_commit = repo.head.target
        parents = [head_commit]
    except pygit2.GitError:
        pass  # initial commit — no parent

    commit_oid = repo.create_commit(
        "refs/heads/main",
        sig,
        sig,
        message,
        tree_oid,
        parents,
    )
    print(f"[ok] Committed: {message} ({str(commit_oid)[:7]})")
    return commit_oid


def ensure_remote(repo: pygit2.Repository, remote_url: str) -> pygit2.Remote:
    """Return the 'origin' remote, creating or updating it as needed."""
    try:
        remote = repo.remotes["origin"]
        if remote.url != remote_url:
            repo.remotes.set_url("origin", remote_url)
            print(f"[info] Updated remote URL to {remote_url}")
        else:
            print(f"[info] Remote 'origin' already set: {remote_url}")
    except KeyError:
        remote = repo.remotes.create("origin", remote_url)
        print(f"[ok] Added remote 'origin': {remote_url}")
    return remote


def push_to_remote(repo: pygit2.Repository, token: str) -> None:
    """Push refs/heads/main to origin using token-based auth."""
    remote = repo.remotes["origin"]

    callbacks = pygit2.RemoteCallbacks(credentials=pygit2.UserpassCredentials(token, "x-oauth-basic"))

    refspec = "refs/heads/main:refs/heads/main"
    remote.push([refspec], callbacks=callbacks)
    print("[ok] Pushed to origin/main.")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    token = load_token()
    gh = Github(token)

    repo_name = REPO_DIR.name
    print(f"[info] Working directory : {REPO_DIR}")
    print(f"[info] Repo name         : {repo_name}")

    # ── 1. Initialise local git repo if needed ────────────────────────────────
    git_dir = REPO_DIR / ".git"
    is_new_local_repo = not git_dir.exists()

    if is_new_local_repo:
        print("[info] No .git found — initialising new local repo.")
        repo = pygit2.init_repository(str(REPO_DIR), initial_head="main")
    else:
        print("[info] Existing local git repo detected.")
        repo = pygit2.Repository(str(REPO_DIR))

    # ── 2. Stage & commit ─────────────────────────────────────────────────────
    has_changes = stage_all(repo)

    if has_changes:
        if is_new_local_repo:
            msg = "Initial commit"
        else:
            msg = f"Update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        commit_all(repo, msg)
    else:
        # Nothing staged — but we still want to push if there's a remote
        try:
            repo.head  # raises if no commits at all
        except pygit2.GitError:
            print("[warn] Repo has no commits and nothing to stage. Exiting.")
            return

    # ── 3. Create / fetch the GitHub remote repo ──────────────────────────────
    remote_repo = get_or_create_github_repo(gh, repo_name)
    remote_url = remote_repo.clone_url  # https://github.com/user/repo.git

    # ── 4. Set remote 'origin' ────────────────────────────────────────────────
    has_origin = "origin" in [r.name for r in repo.remotes]

    if not has_origin:
        ensure_remote(repo, remote_url)
    else:
        ensure_remote(repo, remote_url)  # updates URL if it drifted

    # ── 5. Push ───────────────────────────────────────────────────────────────
    push_to_remote(repo, token)
    print(f"\n[done] {remote_repo.html_url}")


if __name__ == "__main__":
    main()
