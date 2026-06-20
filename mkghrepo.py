#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path

import requests


def load_env_file(env_path):
    """Load environment variables from ~/.env file"""
    env_vars = {}
    try:
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
        return env_vars
    except FileNotFoundError:
        print(f"Error: {env_path} not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading {env_path}: {e}")
        sys.exit(1)


def create_github_repo(token, repo_name, description, public=True):
    """Create a GitHub repository using the API"""
    url = "https://api.github.com/user/repos"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {
        "name": repo_name,
        "description": description,
        "public": public,
        "auto_init": True,  # Initialize with README
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 201:
        repo_info = response.json()
        print(f"✅ Repository created successfully!")
        print(f"📁 Name: {repo_info['name']}")
        print(f"🔗 URL: {repo_info['html_url']}")
        print(f"📝 Clone URL: {repo_info['clone_url']}")
        return repo_info
    else:
        print(f"❌ Failed to create repository: {response.status_code}")
        print(f"Error: {response.json().get('message', 'Unknown error')}")
        return None


def main():
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python create_repo.py <repo_name>")
        print("Example: python create_repo.py my-new-project")
        sys.exit(1)

    repo_name = sys.argv[1]

    # Get README description (with default if not provided)
    readme_description = "created with python"
    if len(sys.argv) >= 3:
        readme_description = sys.argv[2]

    # Load environment variables from ~/.env
    env_path = Path.home() / ".env"
    env_vars = load_env_file(env_path)

    # Get GitHub token
    token = env_vars.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN not found in ~/.env")
        print("Please add: GITHUB_TOKEN=your_github_token_here")
        sys.exit(1)

    # Create the repository
    result = create_github_repo(token=token, repo_name=repo_name, description=readme_description, public=True)

    if result:
        print(f"\n✨ Repository ready at: {result['html_url']}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
