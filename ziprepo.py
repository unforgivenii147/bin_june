#!/data/data/com.termux/files/usr/bin/python


import argparse
import os
import sys
from dotenv import load_dotenv
from github import Github

load_dotenv()


def download_repo_zip(username, repo, branch="main", output_name=None):
    g = Github(os.getenv("GITHUB_TOKEN"))
    repo_obj = g.get_repo(f"{username}/{repo}")
    zip_data = repo_obj.get_zipball(branch)
    size_mb = len(zip_data) / (1024 * 1024)
    print(f"📦 Download size: {size_mb:.2f} MB ({len(zip_data):,} bytes)")
    if output_name is None:
        output_name = f"{repo}-{branch}.zip"
    with open(output_name, "wb") as f:
        f.write(zip_data)
    print(f"✅ Downloaded: {output_name}")
    return output_name


def main():
    parser = argparse.ArgumentParser(description="Download a GitHub repository as ZIP")
    parser.add_argument("repo", help='Repository in format "username/repo"')
    parser.add_argument("--branch", "-b", default="main", help="Branch name (default: main)")
    parser.add_argument("--output", "-o", help="Output filename")
    args = parser.parse_args()
    try:
        username, repo = args.repo.split("/")
    except ValueError:
        print("❌ Error: Repository must be in format 'username/repo'")
        sys.exit(1)
    download_repo_zip(username, repo, args.branch, args.output)


if __name__ == "__main__":
    main()
