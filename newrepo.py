#!/data/data/com.termux/files/home/.local/bin/python

"""
Create and push a git repository to GitHub from the current directory.
If the repo already exists on GitHub, it will commit and push changes.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Built-in Python .gitignore template
PYTHON_GITIGNORE_TEMPLATE = """\
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Pytest / coverage
.pytest_cache/
.coverage
.coverage.*
htmlcov/
.noserc
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/

# Environments
.venv/
venv/
ENV/
env/
env.bak/
venv.bak/

# Jupyter / IPython
.ipynb_checkpoints

# IDEs & Editors
.vscode/
.idea/
*.swp
*.swo
*~

# Environment variables & local databases
.env
.env.local
*.sqlite3
*.db
"""


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Helper to execute external commands safely without shell invocation."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr.strip() or result.stdout.strip()}")
        sys.exit(1)
    return result


def is_git_repo(repo_path: Path = Path(".")) -> bool:
    """Pure Python check for .git directory existence."""
    git_dir = repo_path / ".git"
    return git_dir.is_dir() or git_dir.is_file()


def ensure_gitignore(repo_path: Path = Path(".")) -> None:
    """Creates a default .gitignore if one does not exist, or appends missing essentials."""
    local_gitignore = repo_path / ".gitignore"

    if not local_gitignore.exists():
        print("Creating default Python .gitignore...")
        local_gitignore.write_text(PYTHON_GITIGNORE_TEMPLATE, encoding="utf-8")
    else:
        print("Local .gitignore already exists. Skipping creation.")


def get_current_branch(repo_path: Path = Path(".")) -> str:
    """Reads current branch directly from .git/HEAD with CLI fallback."""
    head_file = repo_path / ".git" / "HEAD"
    if head_file.is_file():
        try:
            content = head_file.read_text().strip()
            if content.startswith("ref: refs/heads/"):
                return content.replace("ref: refs/heads/", "")
        except OSError:
            pass

    res = run_command(["git", "branch", "--show-current"], check=False)
    branch = res.stdout.strip()
    return branch if branch else "main"


def get_remote_url() -> str | None:
    """Retrieves origin remote URL."""
    res = run_command(["git", "remote", "get-url", "origin"], check=False)
    if res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip()
    return None


def main() -> None:
    cwd = Path.cwd()
    repo_name = cwd.name
    print(f"Repository name: {repo_name}")

    # 1. Ensure .gitignore exists
    ensure_gitignore(cwd)

    # 2. Check or Init Git Repository
    if not is_git_repo(cwd):
        print("Initializing git repository...")
        run_command(["git", "init"])
    else:
        print("Git repository already initialized.")

    # 3. Handle GitHub Remote / Creation
    remote_url = get_remote_url()
    if not remote_url:
        print(f"Creating GitHub repository '{repo_name}'...")
        run_command(["gh", "repo", "create", repo_name, "--public", "--source=.", "--push"], check=False)
        remote_url = get_remote_url()
    else:
        print("Remote 'origin' exists. Fetching...")
        fetch_res = run_command(["git", "fetch", "origin"], check=False)
        if fetch_res.returncode != 0:
            print("Warning: Fetch failed. Check authentication or internet connectivity.")

    # 4. Stage and Commit
    print("Adding all files...")
    run_command(["git", "add", "-A"])

    status = run_command(["git", "status", "--porcelain"], check=False)
    if status.stdout.strip():
        print("Committing changes...")
        run_command(["git", "commit", "-m", "Auto-commit: sync changes"])
    else:
        print("No changes to commit.")

    # 5. Push Changes
    current_branch = get_current_branch(cwd)
    print(f"Pushing branch '{current_branch}' to GitHub...")

    push_result = run_command(["git", "push", "--set-upstream", "origin", current_branch], check=False)

    if push_result.returncode != 0:
        if "remote contains work" in push_result.stderr or "behind" in push_result.stderr:
            print("Remote has newer commits. Pulling changes (rebase)...")
            run_command(["git", "pull", "origin", current_branch, "--rebase"])
            print("Pushing again...")
            run_command(["git", "push", "--set-upstream", "origin", current_branch])
        else:
            print(f"Push failed:\n{push_result.stderr}")
            sys.exit(1)

    # 6. Format Clean Success URL
    clean_url = remote_url
    if clean_url:
        if clean_url.endswith(".git"):
            clean_url = clean_url[:-4]
        if clean_url.startswith("git@github.com:"):
            clean_url = clean_url.replace("git@github.com:", "https://github.com/")

    print(f"\n✅ Success! Repository '{repo_name}' is synced on GitHub.")
    if clean_url:
        print(f"View it at: {clean_url}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)
