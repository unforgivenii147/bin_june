#!/data/data/com.termux/files/usr/bin/env python
"""
Termux script creator - Creates executable scripts from clipboard content.
Archives existing files to ~/isaac/may/scripts/ instead of overwriting.
"""

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


TERMUX_SHEBANGS = {
    "python": "#!/data/data/com.termux/files/usr/bin/env python",
    "bash": "#!/data/data/com.termux/files/usr/bin/env bash",
    "sh": "#!/data/data/com.termux/files/usr/bin/env sh",
    "rust": "#!/data/data/com.termux/files/usr/bin/env rust-script",
}

EXTENSION_MAP = {
    ".py": "python",
    ".sh": "bash",
    ".bash": "bash",
    ".rs": "rust",
}

SCRIPT_DIRS = {Path.home() / "bin", Path.home() / "bashbin", Path.home() / ".cargo" / "bin"}
ARCHIVE_DIR = Path.home() / "isaac" / "may" / "scripts"


def get_clipboard_content() -> str:
    try:
        result = subprocess.run(["termux-clipboard-get"], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Failed to read clipboard: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: termux-clipboard-get not found", file=sys.stderr)
        sys.exit(1)


def get_language_from_extension(filename: str) -> str:
    """Determine language based on file extension."""
    path = Path(filename)
    ext = path.suffix.lower()
    return EXTENSION_MAP.get(ext, "bash")  # Default to bash if unknown extension


def replace_shebang(content: str, lang: str) -> str:
    lines = content.splitlines()
    if lines and lines[0].startswith("#!"):
        lines.pop(0)
    lines.insert(0, TERMUX_SHEBANGS[lang])
    result = "\n".join(lines)
    return result if result.endswith("\n") else result + "\n"


def archive_existing_file(file_path: Path) -> None:
    if not file_path.exists():
        return
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
    archive_path = ARCHIVE_DIR / archive_name
    counter = 1
    while archive_path.exists():
        archive_name = f"{file_path.stem}_{timestamp}_{counter}{file_path.suffix}"
        archive_path = ARCHIVE_DIR / archive_name
        counter += 1
    try:
        shutil.move(str(file_path), str(archive_path))
        print(f"📦 Archived existing file to: {archive_path}")
    except OSError as e:
        print(f"❌ Failed to archive file: {e}", file=sys.stderr)
        sys.exit(1)


def create_symlink(script_path: Path) -> None:
    # Don't create symlinks for .rs files
    if script_path.suffix.lower() == ".rs":
        return

    symlink_path = script_path.parent / script_path.stem
    if symlink_path.exists() and symlink_path.is_symlink():
        try:
            symlink_path.unlink()
        except OSError as e:
            print(f"  ⚠️  Failed to remove old symlink: {e}", file=sys.stderr)
    if not symlink_path.exists():
        try:
            symlink_path.symlink_to(script_path)
            print(f"  → Created symlink: {symlink_path.name}")
        except OSError as e:
            print(f"  ⚠️  Failed to create symlink: {e}", file=sys.stderr)


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <filename>", file=sys.stderr)
        sys.exit(1)

    filename = sys.argv[1]
    output_path = Path(filename)
    cwd = Path.cwd()

    # Check if we're in a bin directory
    is_script_dir = cwd in SCRIPT_DIRS or cwd.name == "bin"

    # Archive existing file if it exists
    if output_path.exists():
        archive_existing_file(output_path)

    # Get clipboard content
    content = get_clipboard_content()

    if not content.strip():
        # Empty clipboard
        print("⚠️  Clipboard is empty, creating empty file")
        if is_script_dir:
            lang = get_language_from_extension(filename)
            content = TERMUX_SHEBANGS[lang] + "\n\n"
        else:
            content = "\n"
    elif is_script_dir:
        # Determine language from file extension
        lang = get_language_from_extension(filename)
        content = replace_shebang(content, lang)
        print(f"✓ Added {lang} shebang")

    # Write the file
    try:
        output_path.write_text(content)
        print(f"✓ Created: {output_path}")
    except OSError as e:
        print(f"Error writing file: {e}", file=sys.stderr)
        sys.exit(1)

    # Make executable if in a bin directory
    if is_script_dir:
        output_path.chmod(0o755)  # rwxr-xr-x
        print(f"✓ Made executable: {output_path}")
        create_symlink(output_path)


if __name__ == "__main__":
    main()
