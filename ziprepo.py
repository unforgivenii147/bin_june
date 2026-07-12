#!/usr/bin/env python3
"""
ziprepo_optimized_by_gemini.py — Download a GitHub repository as ZIP.
Optimized for Python 3.12 with modern syntax, type hints, and performance improvements.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from github import Github, GithubException

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# Load environment variables
env_path = Path.home() / ".env"
if env_path.exists():
    load_dotenv(env_path)


def download_repo_zip(
    username: str, repo: str, branch: str = "main", output_name: Optional[str] = None
) -> Optional[Path]:
    """Download a GitHub repository as a ZIP file."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        logger.error("❌ Error: GITHUB_TOKEN environment variable not set.")
        return None

    g = Github(token)
    try:
        repo_full_name = f"{username}/{repo}"
        logger.info(f"Connecting to repository: {repo_full_name}...")
        repo_obj = g.get_repo(repo_full_name)

        logger.info(f"Fetching zipball for branch: {branch}...")
        zip_data = repo_obj.get_zipball(branch)

        size_mb = len(zip_data) / (1024 * 1024)
        logger.info(f"📦 Download size: {size_mb:.2f} MB ({len(zip_data):,} bytes)")

        if output_name is None:
            output_name = f"{repo}-{branch}.zip"

        out_path = Path(output_name)
        out_path.write_bytes(zip_data)

        logger.info(f"✅ Successfully downloaded: {out_path.absolute()}")
        return out_path
    except GithubException as e:
        logger.error(f"❌ GitHub Error: {e.data.get('message', str(e))}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a GitHub repository as ZIP archive")
    parser.add_argument("repo", help='Repository in format "username/repo"')
    parser.add_argument("--branch", "-b", default="main", help="Branch name (default: main)")
    parser.add_argument("--output", "-o", help="Output filename")

    args = parser.parse_args()

    if "/" not in args.repo:
        logger.error("❌ Error: Repository must be in format 'username/repo'")
        sys.exit(1)

    username, repo = args.repo.split("/", 1)

    result = download_repo_zip(username, repo, args.branch, args.output)
    if not result:
        sys.exit(1)


if __name__ == "__main__":
    main()
