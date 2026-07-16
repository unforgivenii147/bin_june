#!/data/data/com.termux/files/usr/bin/env python
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def runcmd(
    cmd: list[str],
    run_silently: bool = False,
    show_output: bool = True,
    timeout: float | None = None,
) -> tuple[int, str, str]:
    from subprocess import DEVNULL as _DEVNULL
    from subprocess import TimeoutExpired as subprocess_TimeoutExpired
    from subprocess import run as subprocess_run
    from sys import stderr as sys_stderr
    from sys import stdout as sys_stdout

    if not cmd:
        msg = "cmd must be a non-empty list (e.g., ['ls', '-l'])"
        raise ValueError(msg)
    try:
        if run_silently:
            result = subprocess_run(cmd, stdout=_DEVNULL, stderr=_DEVNULL, timeout=timeout)
            return result.returncode, "", ""
        result = subprocess_run(cmd, capture_output=True, text=True, timeout=timeout)
        stdout, stderr = result.stdout, result.stderr
        if show_output:
            if stdout:
                sys_stdout.write(stdout)
                sys_stdout.flush()
            if stderr:
                sys_stderr.write(stderr)
                sys_stderr.flush()
        return result.returncode, stdout, stderr
    except FileNotFoundError:
        msg = f"Command not found: '{cmd[0]}'"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 127, "", msg
    except PermissionError:
        msg = f"Permission denied: '{cmd[0]}'"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 126, "", msg
    except subprocess_TimeoutExpired:
        msg = f"Command timed out after {timeout}s: {' '.join(cmd)}"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 124, "", msg
    except Exception as e:
        msg = f"Unexpected error running '{cmd[0]}': {e}"
        if show_output and not run_silently:
            print(msg, file=sys_stderr)
        return 1, "", msg


GITHUB_API_URL = "https://api.github.com/repos"
remained = []
GITHUB_TOKEN = None


def parse_repo_url(url_or_path):
    if "/" in url_or_path and not url_or_path.startswith("http"):
        parts = url_or_path.strip().split("/")
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1]
        return None, None
    try:
        parsed = urlparse(url_or_path.strip())
        if parsed.netloc.lower() in {"github.com", "www.github.com"}:
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) == 2:
                return path_parts[0], path_parts[1]
    except Exception:
        pass
    return None, None


def get_repo_size_mb(user, repo):
    api_endpoint = f"{GITHUB_API_URL}/{user}/{repo}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    try:
        response = requests.get(api_endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        size_bytes = data.get("size")
        if size_bytes is not None:
            size_mb = size_bytes / 1024.0
            return round(size_mb, 2)
        print(f"⚠️ Warning: Could not retrieve size for {user}/{repo} from API.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"❌ API Error: {e.response.status_code} for {user}/{repo}")
        if e.response.status_code == 404:
            print("   Repository not found or access denied.")
        elif e.response.status_code == 403:
            print("   Rate limit exceeded or insufficient permissions.")
        else:
            print(f"   Response: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Network Error: Could not connect to GitHub API: {e}")
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred while fetching size: {e}")
        return None


def clone_repo_shallow(user, repo) -> bool:
    repo_name = f"{user}/{repo}"
    repo_url = f"https://github.com/{repo_name}.git"
    clone_path = os.path.join(Path.cwd(), repo)
    if Path(clone_path).exists():
        return False
    print(f"\n🚀 Cloning {repo_name} (shallow clone)...")
    command = ["git", "clone", repo_url, clone_path]
    try:
        process = runcmd(command, show_output=True)
        print("✅ Successfully cloned repository.")
        print(f"   Cloned into: {clone_path}")
        return True
    except FileNotFoundError:
        print("❌ Error: 'git' command not found. Please ensure Git is installed and in your PATH.")
        return False
    except Exception as e:
        print(f"❌ An unexpected error occurred during cloning: {e}")
        return False


def process_repo(url: str) -> None:
    global remained
    user, repo = parse_repo_url(url)
    if not user or not repo:
        print(f"❌ Invalid GitHub repository format: '{repo_input}'")
        sys.exit(1)
    print(f"🔍 Analyzing repository: {user}/{repo}")
    repo_size = get_repo_size_mb(user, repo)
    if repo_size is not None and repo_size <= 100:
        print(f"ℹ️ size: {repo_size} MB")
        if clone_repo_shallow(user, repo):
            print("\n🎉 Done!")
            return
        print("\nScript finished with errors during cloning.")
        return
    remained.append(url)


"""
    if repo_size is not None and repo_size > 2.0:
        cprint(f"ℹ️ size: {repo_size} MB", "cyan")
        confirm = input(f"clone '{user}/{repo}'? (y/N): ").strip().lower()
        if confirm == "y" or confirm == "yes":
            if clone_repo_shallow(user, repo):
                print("
🎉 Done!")
                return
            else:
                print("
Script finished with errors during cloning.")
                return
        else:
            print("Aborted cloning.")
    else:
        print("
Could not proceed with cloning due to previous errors.")
        return
    return
"""
if __name__ == "__main__":
    repo_file = Path("repos.txt")
    content = repo_file.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=False)
    i = 0
    ll = len(lines)
    for line in lines:
        print(f"{i}/{ll}")
        i += 1
        process_repo(line)
    Path("remained").write_text("\n".join(remained), encoding="utf-8")
