#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

import requests


def get_repos(username: str) -> None:
    url = f"https://api.github.com/users/{username}/repos"
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 404:
            print(f"Error: User '{username}' not found.")
            sys.exit(1)
        response.raise_for_status()
        repos = response.json()
        if not repos:
            print(f"No public repositories found for user '{username}'.")
            return []
        return repos
    except requests.RequestException as e:
        print(f"Error fetching repos: {e}")
        sys.exit(1)


def main() -> None:
    user = sys.argv[1]
    repos = get_repos(user)
    print(f"Repositories of '{username}':")
    for repo in repos:
        print(f"- {repo['name']}")
    with Path(f"{username}.txt").open("w", encoding="utf-8") as f:
        for repo in repos:
            f.write(f"- {repo['name']}")


if __name__ == "__main__":
    main()
