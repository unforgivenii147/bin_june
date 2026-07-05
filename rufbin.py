#!/data/data/com.termux/files/usr/bin/python


import subprocess
from pathlib import Path


def is_python_file(file_path: Path):
    try:
        with Path(file_path).open("r", encoding="utf-8", errors="ignore") as f:
            content = f.read(1024)
        if content.startswith("#!") and "python" in content.lower():
            return True
        python_indicators = [
            "def ",
            "class ",
            "import ",
            "from ",
            "async def",
            "if __name__ ==",
            "print(",
            "raise ",
            "try:",
            "except ",
            "__init__",
        ]
        content_lower = content.lower()
        for indicator in python_indicators:
            if indicator in content_lower:
                return True
        return file_path.suffix.lower() == ".py"
    except:
        return False


def format_with_ruff(file_path: Path):
    try:
        result = subprocess.run(
            ["ruff", "format", str(file_path)], check=False, capture_output=True, text=True, timeout=30
        )
        if not result.returncode:
            return True, ""
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Timeout (30s)"
    except FileNotFoundError:
        return False, "ruff not installed or not in PATH"
    except Exception as e:
        return False, str(e)


def main() -> None:
    cwd = Path()
    python_files = [item for item in cwd.iterdir() if item.is_file() and is_python_file(item)]
    if not python_files:
        return
    for _f in python_files:
        pass
    success_count = 0
    error_count = 0
    errors = []
    for file_path in python_files:
        success, error_msg = format_with_ruff(file_path)
        if success:
            success_count += 1
        else:
            error_count += 1
            errors.append(f"{file_path.name}: {error_msg}")
    if errors:
        for _error in errors:
            pass


if __name__ == "__main__":
    main()
