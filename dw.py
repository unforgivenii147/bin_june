#!/data/data/com.termux/files/usr/bin/python
import sys
import os
import time
import shutil
import argparse


def tail_file(fname, n=10):
    """Read file and return last n lines."""
    try:
        with open(fname, "r") as f:
            lines = f.readlines()
            return lines[-n:] if lines else []
    except (IOError, OSError) as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return []


def get_all_files(folder):
    """Recursively get all files in folder tree."""
    files = {}
    try:
        for root, dirs, filenames in os.walk(folder):
            for fname in filenames:
                fpath = os.path.join(root, fname)
                try:
                    files[fpath] = os.stat(fpath).st_mtime
                except (IOError, OSError):
                    pass
    except (IOError, OSError) as e:
        print(f"Error scanning folder: {e}", file=sys.stderr)

    return files


def copy_file(src, dst_folder: str | None) -> bool:
    """Copy file to destination folder, preserving relative structure."""
    try:
        os.makedirs(dst_folder, exist_ok=True)
        shutil.copy2(src, dst_folder)
        return True
    except (IOError, OSError) as e:
        print(f"Error copying file: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Recursively watch folder for file changes")
    parser.add_argument("folder", help="Folder to watch")
    parser.add_argument("-c", "--copy", action="store_true", help="Copy changed files to ~/tmp/tmp")

    args = parser.parse_args()
    folder = args.folder
    copy_enabled = args.copy

    # Validate folder exists
    if not os.path.isdir(folder):
        print(f"Error: Folder '{folder}' not found", file=sys.stderr)
        sys.exit(1)

    copy_dest = None
    if copy_enabled:
        copy_dest = os.path.expanduser("~/tmp/tmp")
        print(f"Copy mode enabled. Destination: {copy_dest}\n")

    # Initialize: get all current files and their mtimes
    file_mtimes = get_all_files(folder)
    print(f"Watching folder '{folder}' recursively...")
    print(f"Tracking {len(file_mtimes)} files\n")
    print("(Press Ctrl+C to exit)\n")

    try:
        while True:
            # Get current state of all files
            current_files = get_all_files(folder)

            # Check for new or modified files
            for fpath, current_mtime in current_files.items():
                last_mtime = file_mtimes.get(fpath)

                # New file or modified file
                if last_mtime is None or current_mtime > last_mtime:
                    file_mtimes[fpath] = current_mtime

                    # Only report changes (not initial scan)
                    if last_mtime is not None:
                        rel_path = os.path.relpath(fpath, folder)
                        event = "CREATED" if last_mtime is None else "MODIFIED"
                        print(f"[{event}] {rel_path}")

                        # Copy file if enabled
                        if copy_enabled:
                            copy_file(fpath, copy_dest)

                        # Check for bootstrap completion
                        lines = tail_file(fpath, n=10)
                        tail_text = "".join(lines)
                        if "boostraped 100%" in tail_text:
                            print(f"\n✓ Bootstrap complete detected! Exiting...\n")
                            sys.exit(0)

            # Detect deleted files
            deleted = set(file_mtimes.keys()) - set(current_files.keys())
            for fpath in deleted:
                rel_path = os.path.relpath(fpath, folder)
                print(f"[DELETED] {rel_path}")
                del file_mtimes[fpath]

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nWatcher stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
