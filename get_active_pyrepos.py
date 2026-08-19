#!/data/data/com.termux/files/home/.local/bin/python
"""
Fetch GitHub Python repositories by recent activity and save metadata as JSON.
"""

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from github import Github, GithubException


def load_github_client() -> Github:
    load_dotenv(Path.home() / ".env")
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN not found in ~/.env")
    return Github(token)


def get_time_window(days: int) -> str:
    cutoff = datetime.utcnow() - timedelta(days=days)
    return cutoff.strftime("%Y-%m-%d")


def fetch_repo_metadata(repo) -> dict:
    return {
        "repo_url": repo.html_url,
        "repo_size": repo.size,
        "topics": repo.topics or [],
        "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
        "stars": repo.stargazers_count,
    }


def search_repos(period: str) -> list[dict]:
    g = load_github_client()
    days_map = {"d": 1, "w": 7, "m": 30, "y": 365}
    days = days_map.get(period, 7)
    cutoff_date = get_time_window(days)
    query = f"language:python pushed:>={cutoff_date} sort:stars"
    repos = g.search_repositories(query=query, per_page=100)
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for i, repo in enumerate(repos):
            if i >= 100:
                break
            future = executor.submit(fetch_repo_metadata, repo)
            futures[future] = repo.name
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except GithubException as e:
                print(f"Error fetching {futures[future]}: {e}")
    return results


def save_results(data: list[dict], period: str) -> None:
    timestamp = datetime.utcnow().isoformat().replace(":", "-")
    output_file = Path.cwd() / f"github_repos_{period}_{timestamp}.json"
    with output_file.open("w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(data)} repos to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Fetch active GitHub Python repos by time period")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-d", "--day", action="store_true", help="Last 24 hours")
    group.add_argument("-w", "--week", action="store_true", help="Last 7 days")
    group.add_argument("-m", "--month", action="store_true", help="Last 30 days")
    group.add_argument("-y", "--year", action="store_true", help="Last 365 days")
    args = parser.parse_args()
    period_map = {
        "day": "d",
        "week": "w",
        "month": "m",
        "year": "y",
    }
    period_key = next(k for k, v in vars(args).items() if v and k in period_map)
    period = period_map[period_key]
    print(f"Fetching repos from last {period_key}...")
    repos = search_repos(period)
    save_results(repos, period_key)


if __name__ == "__main__":
    main()
