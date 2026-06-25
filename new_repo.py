#!/data/data/com.termux/files/usr/bin/python
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from git import InvalidGitRepositoryError, Repo

# Load environment variables
load_dotenv(os.path.expanduser("~/.env"))

# Configuration
GITHUB_USERNAME = "unforgivenii147"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = Path.cwd().name
BRANCH = "main"


def get_or_create_repo():
    """Get existing repo or create new one"""
    try:
        repo = Repo(Path.cwd())
        print("Existing git repository found.")
        return repo
    except InvalidGitRepositoryError:
        print("No git repository found. Creating new one...")
        repo = Repo.init(Path.cwd())
        print("Git repository initialized.")
        return repo


def stage_and_commit(repo):
    """Stage all changes and commit"""
    if repo.is_dirty(untracked_files=True):
        repo.index.add(["*"])
        repo.index.commit("Update files")
        print("Changes committed.")
    else:
        print("No changes to commit.")


def get_or_create_remote(repo):
    """Get existing remote or create new one on GitHub"""
    try:
        origin = repo.remote("origin")
        print(f"Remote 'origin' already exists: {origin.url}")
        return origin
    except ValueError:
        print("No remote 'origin' found. Creating GitHub repository...")
        remote_url = create_github_repo()
        origin = repo.create_remote("origin", remote_url)
        print(f"Remote 'origin' created: {remote_url}")
        return origin


def create_github_repo():
    """Create a new repository on GitHub"""
    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {"name": REPO_NAME, "private": False, "auto_init": False}

    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code == 422:
        # Repository might already exist
        print(f"Repository '{REPO_NAME}' may already exist on GitHub.")
        return f"git@github.com:{GITHUB_USERNAME}/{REPO_NAME}.git"
    elif response.status_code != 201:
        raise Exception(f"Failed to create GitHub repo: {response.json()}")

    return response.json()["ssh_url"]


def push_to_github(origin):
    """Push to GitHub"""
    try:
        origin.push(refspec=f"{BRANCH}:{BRANCH}")
        print(f"Successfully pushed to {origin.url}")
    except Exception as e:
        print(f"Push failed: {e}")
        # Try setting upstream branch
        origin.push(refspec=f"{BRANCH}:{BRANCH}", set_upstream=True)


def main():
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN not found in environment variables.")
        exit(1)

    try:
        # Step 1: Get or create local repo
        repo = get_or_create_repo()

        # Step 2: Stage and commit changes
        stage_and_commit(repo)

        # Step 3: Get or create remote
        origin = get_or_create_remote(repo)

        # Step 4: Push to GitHub
        push_to_github(origin)

        print(f"✅ Repository '{REPO_NAME}' is now on GitHub!")

    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
