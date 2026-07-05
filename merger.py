#!/data/data/com.termux/files/usr/bin/python


from pathlib import Path
from dh import get_nobinary, get_random_filename

EXCLUDE_DIRS = {".git", "__pycache__", ".idea", ".vscode", "node_modules", ".env", "venv"}
DEFAULT_OUTPUT_LEN = 8


def read_file(path: Path):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (IOError, OSError, UnicodeDecodeError):
        return None


def merge_files():
    cwd = Path.cwd()
    output_file = cwd / f"{get_random_filename()}.txt"
    files = sorted(get_nobinary(cwd))
    try:
        with output_file.open("w", encoding="utf-8") as fo:
            for i, file_path in enumerate(files):
                if str(file_path).startswith("."):
                    continue
                content = read_file(file_path)
                if content is None:
                    continue
                fo.write(f"\n# {file_path.name}\n")
                fo.write(content)
        print(f"\n✅ Merged {len(files)} files into: {output_file}")
        return output_file
    except IOError as e:
        print(f"Error writing output file: {e}")
        return None


if __name__ == "__main__":
    merge_files()
