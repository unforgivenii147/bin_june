#!/data/data/com.termux/files/usr/bin/env python
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from dh import is_valid_archive

TARGET_FILES = {"METADATA", "PKGINFO", "PKG-INFO"}
PREFIX = "Requires-Dist:"
LOG_FILE = Path("/sdcard/reqz.txt")
removed_lines_accumulator = []


def clean_text(text: str) -> tuple[str, list[str]]:
    """Remove lines starting with PREFIX from text."""
    lines = text.splitlines()
    cleaned = []
    removed = []

    for line in lines:
        if line.startswith(PREFIX):
            removed.append(line)
        else:
            cleaned.append(line)

    final_text = "\n".join(cleaned)
    if text.endswith("\n"):
        final_text += "\n"

    return final_text, removed


def clean_file(path: Path) -> None:
    """Clean a single file by removing Requires-Dist lines."""
    try:
        original = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return

    cleaned, removed = clean_text(original)
    if removed:
        removed_lines_accumulator.extend(removed)
        path.write_text(cleaned, encoding="utf-8")


def process_zip(path: Path) -> None:
    """Process a zip file (wheel) and clean target files."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        with zipfile.ZipFile(path, "r") as zin, zipfile.ZipFile(tmp_path, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                base = Path(item.filename).name

                if base in TARGET_FILES:
                    try:
                        text = data.decode("utf-8", errors="ignore")
                        cleaned, removed = clean_text(text)
                        if removed:
                            removed_lines_accumulator.extend(removed)
                        data = cleaned.encode("utf-8")
                    except Exception:
                        pass

                zout.writestr(item, data)

        shutil.move(str(tmp_path), str(path))
    finally:
        tmp_path.unlink(missing_ok=True)


def process_tar(path: Path) -> None:
    """Process a tar archive and clean target files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_dir = Path(tmp_dir)
        tmp_tar = temp_dir / "temp.tar.gz"

        # Extract archive
        with tarfile.open(path, "r:*") as tar:
            tar.extractall(temp_dir, filter="data")

        # Clean target files
        for target_file in TARGET_FILES:
            for file_path in temp_dir.rglob(target_file):
                if file_path.is_file():
                    clean_file(file_path)

        # Create new archive
        with tarfile.open(tmp_tar, "w:gz") as tar:
            tar.add(temp_dir, arcname="")

        shutil.move(str(tmp_tar), str(path))


def dispatch_archive(path: Path) -> None:
    """Dispatch archive processing based on file type."""
    if not is_valid_archive(str(path)):
        print(f"{path} is not valid archive")
        return

    path_str = str(path).lower()
    if path_str.endswith(".whl"):
        print(f"processing ... {path}")
        process_zip(path)
    elif path_str.endswith((".tar.gz", ".tgz", ".tar")):
        process_tar(path)


def find_files_to_process() -> list[Path]:
    """Find all files that need processing."""
    files_to_process = []
    current_dir = Path.cwd()

    for file_path in current_dir.rglob("*"):
        if not file_path.is_file():
            continue

        file_name = file_path.name
        file_name_lower = file_name.lower()

        # Check if it's a target file
        if file_name in TARGET_FILES or file_name.endswith(".metadata"):
            files_to_process.append(file_path)
        # Check if it's an archive
        elif file_name_lower.endswith((".zip", ".whl", ".tar.gz", ".tgz", ".tar")):
            files_to_process.append(file_path)

    return files_to_process


def main() -> None:
    """Main entry point."""
    files_to_process = find_files_to_process()

    for file_path in files_to_process:
        file_name = file_path.name
        file_name_lower = file_name.lower()

        if file_name in TARGET_FILES or file_name.endswith(".metadata"):
            clean_file(file_path)
        elif file_name_lower.endswith((".zip", ".whl", ".tar.gz", ".tgz", ".tar")):
            dispatch_archive(file_path)

    # Output results
    if removed_lines_accumulator:
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.writelines(line + "\n" for line in removed_lines_accumulator)
            print(f"--- Saved {len(removed_lines_accumulator)} lines to {LOG_FILE} ---")
        except PermissionError:
            pass

        print("\nRemoved Lines:")
        print("-" * 20)
        for line in removed_lines_accumulator:
            print(line)
        print("-" * 20)
    else:
        print("No matching lines were found or removed.")


if __name__ == "__main__":
    main()
