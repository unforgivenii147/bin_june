#!/data/data/com.termux/files/usr/bin/python

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


class GitHubRepoCreator:
    def __init__(self) -> None:
        self.current_dir = Path.cwd()
        self.repo_name = self.current_dir.name
        self.env_file = Path.home() / ".env"
        self.github_token = self._load_github_token()
        self.github_username = self._get_github_username()

    def _load_github_token(self) -> str:
        print(f"🔑 Loading GitHub token from {self.env_file}")
        if self.env_file.exists():
            load_dotenv(self.env_file)
            token = os.getenv("GITHUB_TOKEN")
            if token:
                print("✅ GitHub token loaded successfully")
                return token
            print("❌ GITHUB_TOKEN not found in .env file")
            print("Please add: GITHUB_TOKEN=your_token_here")
            sys.exit(1)
        else:
            print(f"❌ .env file not found at {self.env_file}")
            print("Please create ~/.env with: GITHUB_TOKEN=your_token_here")
            sys.exit(1)

    def _get_github_username(self) -> str:
        success, username, _ = self._run_cmd(["git", "config", "--global", "user.name"])
        if success and username:
            return username
        print("👤 Attempting to get username from GitHub API...")
        cmd = [
            "curl",
            "-s",
            "-H",
            f"Authorization: token {self.github_token}",
            "-H",
            "Accept: application/vnd.github.v3+json",
            "https://api.github.com/user",
        ]
        success, output, _error = self._run_cmd(cmd)
        if success and output:
            try:
                user_data = json.loads(output)
                username = user_data.get("login")
                if username:
                    self._run_cmd(["git", "config", "--global", "user.name", username])
                    print(f"✅ Username found: {username}")
                    return username
            except json.JSONDecodeError:
                pass
        print("❌ Could not determine GitHub username")
        print("Please set it manually: git config --global user.name 'your_username'")
        sys.exit(1)

    def _run_cmd(self, cmd: list, cwd: Path | None = None) -> tuple[bool, str, str]:
        try:
            result = subprocess.run(cmd, cwd=cwd or self.current_dir, capture_output=True, text=True)
            print(result.stdout)
            if result.returncode:
                print(result.stderr)
            return (result.returncode == 0, result.stdout.strip(), result.stderr.strip())
        except Exception as e:
            return (False, "", str(e))

    def _check_prerequisites(self):
        print("\n🔍 Checking prerequisites...")
        if not self._run_cmd(["git", "--version"])[0]:
            print("❌ Git is not installed")
            sys.exit(1)
        if not self._run_cmd(["curl", "--version"])[0]:
            print("❌ curl is not installed")
            sys.exit(1)
        try:
            print("✅ python-dotenv is installed")
        except ImportError:
            print("❌ python-dotenv is not installed")
            print("Install it: pip install python-dotenv")
            sys.exit(1)
        print("✅ All prerequisites satisfied")

    def _initialize_git(self):
        print(f"\n📁 Initializing git repository: {self.repo_name}")
        success, _, _ = self._run_cmd(["git", "rev-parse", "--git-dir"])
        if success:
            print("⚠️  Already a git repository")
            response = input("Reinitialize? (y/N): ").lower()
            if response != "y":
                print("Continuing with existing repository...")
                return
            import shutil

            shutil.rmtree(self.current_dir / ".git", ignore_errors=True)
        success, _, stderr = self._run_cmd(["git", "init"])
        if not success:
            print(f"❌ Failed to initialize git: {stderr}")
            sys.exit(1)
        success, _, stderr = self._run_cmd(["git", "checkout", "-b", "main"])
        if not success:
            print(f"❌ Failed to create main branch: {stderr}")
            sys.exit(1)
        print("✅ Git repository initialized")

    def _setup_gitignore(self):
        home_gitignore = Path.home() / ".gitignore"
        local_gitignore = self.current_dir / ".gitignore"
        if home_gitignore.exists() and (not local_gitignore.exists()):
            print("\n📄 Copying .gitignore from home directory")
            try:
                import shutil

                shutil.copy2(home_gitignore, local_gitignore)
                print("✅ .gitignore copied")
            except Exception as e:
                print(f"⚠️  Could not copy .gitignore: {e}")

    def _check_repo_exists(self) -> bool:
        cmd = [
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "-H",
            f"Authorization: token {self.github_token}",
            f"https://api.github.com/repos/{self.github_username}/{self.repo_name}",
        ]
        success, status_code, _ = self._run_cmd(cmd)
        return bool(success and status_code == "200")

    def _create_github_repo(self) -> bool:
        print(f"\n🌐 Creating GitHub repository: {self.github_username}/{self.repo_name}")
        if self._check_repo_exists():
            print("⚠️  Repository already exists on GitHub")
            response = input("Push to existing repo? (y/N): ").lower()
            return response == "y"
        api_url = "https://api.github.com/user/repos"
        data = {
            "name": self.repo_name,
            "private": False,
            "auto_init": False,
            "description": f"Repository created from {self.repo_name} on {datetime.now().strftime('%Y-%m-%d')}",
        }
        import tempfile

        with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_file = f.name
        try:
            cmd = [
                "curl",
                "-s",
                "-X",
                "POST",
                "-H",
                f"Authorization: token {self.github_token}",
                "-H",
                "Accept: application/vnd.github.v3+json",
                api_url,
                "-d",
                f"@{temp_file}",
            ]
            success, stdout, stderr = self._run_cmd(cmd)
            Path(temp_file).unlink()
            if not success:
                print(f"❌ Failed to create repository: {stderr}")
                try:
                    error_data = json.loads(stdout)
                    if "message" in error_data:
                        print(f"Error message: {error_data['message']}")
                except:
                    pass
                sys.exit(1)
            try:
                response_data = json.loads(stdout)
                clone_url = response_data.get("clone_url", "")
                print("✅ Repository created successfully")
                if clone_url:
                    print(f"   URL: {clone_url}")
                return True
            except json.JSONDecodeError:
                print("✅ Repository created (response parsing failed)")
                return True
        except Exception as e:
            print(f"❌ Error creating repository: {e}")
            sys.exit(1)

    def _setup_remote(self):
        print("\n🔗 Configuring remote...")
        remote_url = f"https://github.com/{self.github_username}/{self.repo_name}.git"
        success, remotes, _ = self._run_cmd(["git", "remote"])
        if "origin" in remotes.split("\n"):
            success, _, stderr = self._run_cmd(["git", "remote", "set-url", "origin", remote_url])
            if success:
                print("✅ Remote origin updated")
            else:
                print(f"⚠️  Could not update remote: {stderr}")
        else:
            success, _, stderr = self._run_cmd(["git", "remote", "add", "origin", remote_url])
            if success:
                print("✅ Remote origin added")
            else:
                print(f"⚠️  Could not add remote: {stderr}")

    def _commit_changes(self):
        print("\n💾 Committing changes...")
        success, _, stderr = self._run_cmd(["git", "add", "-A"])
        if not success:
            print(f"❌ Failed to add files: {stderr}")
            sys.exit(1)
        success, _, _ = self._run_cmd(["git", "diff", "--cached", "--quiet"])
        if success:
            print("ℹ️  No changes to commit")
            return False
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        success, _, stderr = self._run_cmd(["git", "commit", "-m", f"Initial commit - {timestamp}"])
        if not success:
            print(f"❌ Failed to commit: {stderr}")
            sys.exit(1)
        print("✅ Changes committed")
        return True

    def _push_to_github(self):
        print("\n🚀 Pushing to GitHub...")
        auth_remote_url = (
            f"https://{self.github_username}:{self.github_token}@github.com/{self.github_username}/{self.repo_name}.git"
        )
        self._run_cmd(["git", "remote", "set-url", "origin", auth_remote_url])
        success, _, stderr = self._run_cmd(["git", "push", "-u", "origin", "main"])
        clean_url = f"https://github.com/{self.github_username}/{self.repo_name}.git"
        self._run_cmd(["git", "remote", "set-url", "origin", clean_url])
        if not success:
            print(f"❌ Failed to push: {stderr}")
            print("\nTroubleshooting tips:")
            print("1. Check if your token has 'repo' scope")
            print("2. Verify repository exists on GitHub")
            print("3. Try pulling first: git pull origin main --allow-unrelated-histories")
            sys.exit(1)
        print("✅ Successfully pushed to GitHub")

    def run(self):
        print("=" * 60)
        print("🚀 GITHUB REPOSITORY CREATOR")
        print("=" * 60)
        print(f"📂 Directory: {self.current_dir}")
        print(f"📦 Repo name: {self.repo_name}")
        print(f"👤 Username:  {self.github_username}")
        print(f"🔑 Token source: {self.env_file}")
        print("=" * 60)
        self._check_prerequisites()
        self._initialize_git()
        self._setup_gitignore()
        if self._create_github_repo():
            self._setup_remote()
            self._commit_changes()
            self._push_to_github()
            print("\n" + "=" * 60)
            print("✅ SUCCESS! Repository is live on GitHub")
            print(f"📍 https://github.com/{self.github_username}/{self.repo_name}")
            print("=" * 60)
        else:
            print("\n⚠️  Operation cancelled")


def main():
    try:
        creator = GitHubRepoCreator()
        creator.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
