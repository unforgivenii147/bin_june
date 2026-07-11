#!/data/data/com.termux/files/usr/bin/env python
"""
Change Python shebang in all Python files to Termux path.
If a file has no shebang, add one at the beginning.
Usage: python change_shebang.py
"""

import re
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys
from typing import Optional, Tuple

NEW_SHEBANG = "#!/data/data/com.termux/files/usr/bin/env python"
SHEBANG_PATTERN = re.compile(r"^#!.*python[23]?(?:\.\d+)?(?:[ \t]+.*)?$", re.MULTILINE)
PYTHON_EXTENSIONS = {".py", ".pyw", ".pyx", ".pxd", ".pyi"}
COMMON_PYTHON_NAMES = {
    "setup",
    "setup.py",
    "manage",
    "manage.py",
    "app",
    "app.py",
    "wsgi",
    "wsgi.py",
    "asgi",
    "asgi.py",
    "test",
    "test.py",
    "conftest",
    "conftest.py",
    "requirements",
    "main",
    "main.py",
    "cli",
    "cli.py",
    "run",
    "run.py",
}


def is_symlink(path: Path) -> bool:
    return path.is_symlink()


def is_likely_python_file(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            content = f.read(512)
            if content.startswith(b"#!"):
                first_line = content.split(b"\n")[0] if b"\n" in content else content
                if b"python" in first_line.lower():
                    return True
            text_sample = content.decode("utf-8", errors="ignore")
            python_patterns = [
                "^(from|import)\\s+",
                "^def\\s+\\w+\\s*\\(",
                "^class\\s+\\w+[:\\(]",
                "^if\\s+__name__\\s*==\\s*['\\\"]__main__['\\\"]",
                "^#!.*python",
            ]
            for pattern in python_patterns:
                if re.search(pattern, text_sample, re.MULTILINE):
                    return True
            return False
    except (UnicodeDecodeError, IOError, PermissionError):
        return False


def find_python_files(directory: Path) -> list[Path]:
    python_files = []
    for path in directory.rglob("*"):
        if any((part.startswith(".") and part != "." for part in path.parts)):
            if ".git" in path.parts:
                continue
        if is_symlink(path):
            continue
        if not path.is_file():
            continue
        if path.suffix in PYTHON_EXTENSIONS:
            python_files.append(path)
            continue
        skip_patterns = [
            "\\.(md|txt|rst|json|yaml|yml|toml|ini|cfg|conf|log|lock|gitignore|dockerignore)$",
            "\\.(css|html|js|ts|jsx|tsx|vue|svelte)$",
            "\\.(jpg|jpeg|png|gif|svg|ico|webp)$",
            "\\.(mp4|mp3|avi|mkv|mov)$",
            "\\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$",
            "\\.(zip|tar|gz|rar|7z)$",
            "\\.(so|dll|dylib|exe|o|a|lib)$",
            "\\.(pyc|pyo|pyd)$",
        ]
        if any((re.search(pattern, str(path), re.IGNORECASE) for pattern in skip_patterns)):
            continue
        if path.stem in COMMON_PYTHON_NAMES:
            if is_likely_python_file(path):
                python_files.append(path)
            continue
        if "." not in path.name:
            if is_likely_python_file(path):
                python_files.append(path)
    return python_files


def process_file(path: Path, root_dir: Path) -> Tuple[Path, bool, Optional[str], str, str]:
    rel_path = str(path.relative_to(root_dir))
    if is_symlink(path):
        return (path, False, "Symlink skipped", rel_path, "skipped")
    try:
        content = path.read_text(encoding="utf-8")
        has_shebang = content.startswith("#!")
        if not has_shebang:
            new_content = NEW_SHEBANG + "\n" + content
            path.write_text(new_content, encoding="utf-8")
            return (path, True, None, rel_path, "added")
        first_line = content.split("\n")[0] if "\n" in content else content
        if "python" not in first_line.lower():
            return (path, False, "Not a Python shebang", rel_path, "skipped")
        if first_line.strip() == NEW_SHEBANG:
            return (path, False, "Already correct", rel_path, "unchanged")
        lines = content.split("\n")
        lines[0] = NEW_SHEBANG
        new_content = "\n".join(lines)
        path.write_text(new_content, encoding="utf-8")
        return (path, True, None, rel_path, "updated")
    except Exception as e:
        return (path, False, str(e), rel_path, "error")


def main():
    current_dir = Path.cwd()
    print(f"📁 Scanning directory: {current_dir}")
    print("-" * 50)
    python_files = find_python_files(current_dir)
    if not python_files:
        print("No Python files found.")
        return
    print(f"Found {len(python_files)} Python files to check.")
    print("-" * 50)
    updated_files = []
    added_shebang_files = []
    errors = []
    skipped_count = 0
    already_correct_count = 0
    not_python_count = 0
    with ProcessPoolExecutor() as executor:
        future_to_file = {executor.submit(process_file, path, current_dir): path for path in python_files}
        for future in as_completed(future_to_file):
            path, was_changed, error, rel_path, action_type = future.result()
            if error:
                if "Symlink" in error:
                    skipped_count += 1
                elif "Not a Python shebang" in error:
                    not_python_count += 1
                elif "Already correct" in error:
                    already_correct_count += 1
                else:
                    errors.append((rel_path, error))
            elif was_changed and action_type == "updated":
                updated_files.append((path, rel_path))
            elif was_changed and action_type == "added":
                added_shebang_files.append((path, rel_path))
            else:
                skipped_count += 1
    if updated_files:
        print(f"\n✅ Updated existing shebangs in {len(updated_files)} files:")
        print("-" * 50)
        for path, rel_path in updated_files:
            file_info = rel_path
            if "." not in Path(rel_path).name:
                file_info += " (no extension)"
            print(f"  ✏️  {file_info}")
    if added_shebang_files:
        print(f"\n➕ Added new shebang to {len(added_shebang_files)} files:")
        print("-" * 50)
        for path, rel_path in added_shebang_files:
            file_info = rel_path
            if "." not in Path(rel_path).name:
                file_info += " (no extension)"
            print(f"  ➕ {file_info}")
    if not updated_files and (not added_shebang_files):
        print("\n✅ No files needed updating.")
    print("\n" + "=" * 50)
    print(f"📊 Summary:")
    print(f"  ✏️  Updated existing shebangs: {len(updated_files)} files")
    print(f"  ➕ Added new shebangs: {len(added_shebang_files)} files")
    print(f"  ⏭️  Skipped (symlinks): {skipped_count} files")
    print(f"  ⏭️  Not Python shebang: {not_python_count} files")
    print(f"  ⏭️  Already correct: {already_correct_count} files")
    print(f"  📝 Total processed: {len(python_files)} files")
    if errors:
        print(f"  ❌ Errors: {len(errors)} files")
    if errors:
        print("\n❌ Errors:")
        for rel_path, error in errors:
            print(f"  - {rel_path}: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
