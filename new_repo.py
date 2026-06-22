#!/data/data/com.termux/files/usr/bin/python
from pathlib import Path
import requests
import json
from git import Repo
from dotenv import load_dotenv
import os

# Load environment variables from ~/.env
load_dotenv(os.path.expanduser("~/.env"))

# Configuration
GITHUB_USERNAME = "unforgivenii147"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Get current directory name as repo name
REPO_NAME = Path.cwd().name
BRANCH = "main"


# Step 1: Initialize Git repo locally
def init_git_repo():
    repo = Repo.init(Path.cwd())
    repo.index.add(["*"])
    repo.index.commit("Initial commit")
    return repo


# Step 2: Create a new repository on GitHub
def create_github_repo():
    url = "https://api.github.com/user/repos"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    data = {"name": REPO_NAME, "private": False, "auto_init": False}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code != 201:
        raise Exception(f"Failed to create GitHub repo: {response.json()}")
    return response.json()["ssh_url"]


# Step 3: Add remote and push
def push_to_github(repo, remote_url):
    origin = repo.create_remote("origin", remote_url)
    origin.push(refspec=f"{BRANCH}:{BRANCH}")


# Main
if __name__ == "__main__":
    try:
        repo = init_git_repo()
        remote_url = create_github_repo()
        push_to_github(repo, remote_url)
        print(f"Successfully pushed to GitHub: {remote_url}")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
