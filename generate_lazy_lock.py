#!/data/data/com.termux/files/home/.local/bin/python
"""
Generate lazy-lock.json for lazy.nvim plugin manager.
Scans plugins in ~/.local/share/nvim/lazy and creates a lock file
with current commit hashes.
"""

import json
import os
import subprocess
from pathlib import Path


def get_git_commit(repo_path):
    """Get the current commit hash and branch for a git repository."""
    try:
        # Get commit hash
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_path, stderr=subprocess.DEVNULL, text=True
        ).strip()

        # Get branch name
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path, stderr=subprocess.DEVNULL, text=True
        ).strip()

        return commit, branch
    except subprocess.CalledProcessError:
        return None, None


def generate_lazy_lock():
    """Generate lazy-lock.json from current plugin states."""
    # Paths
    lazy_dir = Path.home() / ".local" / "share" / "nvim" / "lazy"
    lock_file = Path.home() / ".config" / "nvim" / "lazy-lock.json"

    # Check if lazy directory exists
    if not lazy_dir.exists():
        print(f"Error: Lazy directory not found at {lazy_dir}")
        return False

    # Ensure config directory exists
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    # Dictionary to store plugin information
    plugins_lock = {}

    # Iterate through plugin directories
    for plugin_dir in sorted(lazy_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue

        plugin_name = plugin_dir.name

        # Check if it's a git repository
        git_dir = plugin_dir / ".git"
        if not git_dir.exists():
            print(f"Skipping {plugin_name}: Not a git repository")
            continue

        # Get commit and branch
        commit, branch = get_git_commit(plugin_dir)

        if commit and branch:
            plugins_lock[plugin_name] = {"branch": branch, "commit": commit}
            print(f"✓ {plugin_name}: {commit[:8]} ({branch})")
        else:
            print(f"✗ {plugin_name}: Failed to get git information")

    # Write to lock file
    try:
        with open(lock_file, "w") as f:
            json.dump(plugins_lock, f, indent=2)
            f.write("\n")  # Add trailing newline

        print(f"\n✓ Successfully wrote lock file to {lock_file}")
        print(f"  Total plugins: {len(plugins_lock)}")
        return True

    except IOError as e:
        print(f"Error writing lock file: {e}")
        return False


def main():
    """Main function."""
    print("Generating lazy-lock.json for Neovim plugins...")
    print(f"Scanning: {Path.home() / '.local' / 'share' / 'nvim' / 'lazy'}")
    print(f"Output: {Path.home() / '.config' / 'nvim' / 'lazy-lock.json'}")
    print("-" * 50)

    success = generate_lazy_lock()

    if success:
        print("\nDone! You can now use this lock file with lazy.nvim.")
    else:
        print("\nFailed to generate lock file.")
        exit(1)


if __name__ == "__main__":
    main()
