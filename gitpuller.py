#!/usr/bin/env python3
"""
Script to run git pull on all git repositories in current directory and subdirectories.
Requires gitpython library: pip install gitpython
"""

from pathlib import Path

from git import GitCommandError, Repo


def find_git_repos(root_path: Path) -> list[Path]:
    """Recursively find all git repositories."""
    git_repos = []

    for item in root_path.iterdir():
        if not item.is_dir():
            continue

        # Check if this directory is a git repo
        if (item / ".git").exists():
            git_repos.append(item)
        else:
            # Recursively search subdirectories
            git_repos.extend(find_git_repos(item))

    return git_repos


def git_pull_all() -> None:
    """Run git pull on all git repositories in current directory and subdirectories."""
    cwd = Path.cwd()

    print(f"🔍 Scanning for git repositories in: {cwd}")
    repos = find_git_repos(cwd)

    if not repos:
        print("No git repositories found")
        return

    print(f"Found {len(repos)} git repository(ies)\n")

    pulled_repos = []
    failed_repos = []

    for repo_path in repos:
        print(f"📁 Repository: {repo_path.relative_to(cwd)}")

        try:
            repo = Repo(repo_path)

            # Get current branch
            current_branch = repo.active_branch.name
            print(f"   Branch: {current_branch}")

            # Check for remotes
            if not repo.remotes:
                failed_repos.append((repo_path, "No remote configured"))
                print(f"   ❌ No remote configured")
                continue

            remote_name = repo.remotes[0].name

            # Perform git pull
            pull_result = repo.remotes[remote_name].pull()

            # Check results - correct flags for FetchInfo
            success = False
            for info in pull_result:
                # Common flags: INFO, ERROR, REJECTED, FAST_FORWARD, etc.
                if hasattr(info, "flags"):
                    if info.flags & info.ERROR:
                        failed_repos.append((repo_path, str(info.note)))
                        print(f"   ❌ Failed: {info.note}")
                    else:
                        success = True
                        # Check if it was actually updated
                        if hasattr(info, "commit") and info.commit:
                            print(f"   ✅ Pulled successfully: {info.commit}")
                        else:
                            print(f"   ℹ️  Already up to date")
                else:
                    # Fallback for older gitpython versions
                    success = True
                    print(f"   ✅ Pull completed")

            if success:
                pulled_repos.append(repo_path)

        except GitCommandError as e:
            failed_repos.append((repo_path, str(e)))
            print(f"   ❌ Git error: {e}")
        except Exception as e:
            failed_repos.append((repo_path, f"Unexpected error: {str(e)}"))
            print(f"   ❌ Error: {e}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if pulled_repos:
        print(f"\n✅ Successfully pulled ({len(pulled_repos)} repos):")
        for repo_path in pulled_repos:
            print(f"   - {repo_path.relative_to(cwd)}")

    if failed_repos:
        print(f"\n❌ Failed ({len(failed_repos)} repos):")
        for repo_path, error in failed_repos:
            print(f"   - {repo_path.relative_to(cwd)}: {error}")


if __name__ == "__main__":
    try:
        git_pull_all()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
