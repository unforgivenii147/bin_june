#!/data/data/com.termux/files/usr/bin/python

"""
Termux script creator - Creates executable scripts from clipboard content.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

# Termux specific shebangs
TERMUX_SHEBANGS = {
    "python": "#!/data/data/com.termux/files/usr/bin/python",
    "bash": "#!/data/data/com.termux/files/usr/bin/bash",
    "sh": "#!/data/data/com.termux/files/usr/bin/sh",
}

# Directories where scripts get auto-symlinked
SCRIPT_DIRS = {Path.home() / "bin", Path.home() / "bashbin"}


def get_clipboard_content() -> str:
    """Retrieve content from Termux clipboard."""
    try:
        result = subprocess.run(
            ["termux-clipboard-get"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Failed to read clipboard: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: termux-clipboard-get not found", file=sys.stderr)
        sys.exit(1)


def detect_language(content: str) -> str:
    """Detect if content is Python or bash/sh."""
    first_line = content.lstrip().split("\n")[0] if content else ""

    # Check for explicit shebang
    if first_line.startswith("#!"):
        if "python" in first_line.lower():
            return "python"
        elif "bash" in first_line.lower() or "sh" in first_line.lower():
            return "bash"

    # Heuristic detection
    python_indicators = ["import ", "from ", "def ", "class ", "if __name__", "print("]
    bash_indicators = ["echo ", "cd ", "export ", "if [", "for ", "while ", "$("]

    preview = content[:500].lower()

    python_score = sum(1 for ind in python_indicators if ind in preview)
    bash_score = sum(1 for ind in bash_indicators if ind in preview)

    return "python" if python_score >= bash_score else "bash"


def replace_shebang(content: str, lang: str) -> str:
    """Replace or add appropriate Termux shebang."""
    lines = content.splitlines()

    # Remove existing shebang if present
    if lines and lines[0].startswith("#!"):
        lines.pop(0)

    # Add Termux shebang
    if lang == "python":
        lines.insert(0, TERMUX_SHEBANGS["python"])
    else:
        lines.insert(0, TERMUX_SHEBANGS["bash"])

    # Ensure trailing newline
    result = "\n".join(lines)
    return result if result.endswith("\n") else result + "\n"


def create_symlink(script_path: Path) -> None:
    """Create symlink without extension in script directories."""
    if script_path.suffix:
        symlink_path = script_path.parent / script_path.stem

        if not symlink_path.exists():
            try:
                symlink_path.symlink_to(script_path)
                print(f"  → Created symlink: {symlink_path.name}")
            except OSError as e:
                print(f"  ⚠️  Failed to create symlink: {e}", file=sys.stderr)


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <filename>", file=sys.stderr)
        print(f"Example: {sys.argv[0]} myscript.py", file=sys.stderr)
        sys.exit(1)

    filename = sys.argv[1]
    output_path = Path(filename)
    cwd = Path.cwd()
    is_script_dir = cwd in SCRIPT_DIRS

    # Get clipboard content
    content = get_clipboard_content()

    if not content.strip():
        print("⚠️  Clipboard is empty, creating empty file")
        content = "\n"
        if is_script_dir:
            content = TERMUX_SHEBANGS["bash"] + "\n\n" + content
    else:
        # Replace shebang if in script directory
        if is_script_dir:
            lang = detect_language(content)
            content = replace_shebang(content, lang)
            print(f"✓ Added {lang} shebang")

    # Write file
    try:
        output_path.write_text(content)
        print(f"✓ Created: {output_path}")
    except OSError as e:
        print(f"Error writing file: {e}", file=sys.stderr)
        sys.exit(1)

    # Set executable permissions and create symlink if in script directory
    if is_script_dir:
        output_path.chmod(0o755)
        print(f"✓ Made executable")
        create_symlink(output_path)


if __name__ == "__main__":
    main()
