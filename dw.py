#!/data/data/com.termux/files/usr/bin/python


import argparse
import os
import shutil
import sys
import time


def tail_file(fname, n=10):
    try:
        with open(fname, "r") as f:
            lines = f.readlines()
            return lines[-n:] if lines else []
    except (IOError, OSError) as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return []


def get_all_files(folder):
    files = {}
    try:
        for root, dirs, filenames in os.walk(folder):
            for fname in filenames:
                path = os.path.join(root, fname)
                try:
                    files[path] = os.stat(path).st_mtime
                except (IOError, OSError):
                    pass
    except (IOError, OSError) as e:
        print(f"Error scanning folder: {e}", file=sys.stderr)
    return files


def copy_file(src, dst_folder: (str | None)) -> bool:
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
    if not os.path.isdir(folder):
        print(f"Error: Folder '{folder}' not found", file=sys.stderr)
        sys.exit(1)
    copy_dest = None
    if copy_enabled:
        copy_dest = os.path.expanduser("~/tmp/tmp")
        print(f"Copy mode enabled. Destination: {copy_dest}\n")
    file_mtimes = get_all_files(folder)
    print(f"Watching folder '{folder}' recursively...")
    print(f"Tracking {len(file_mtimes)} files\n")
    print("(Press Ctrl+C to exit)\n")
    try:
        while True:
            current_files = get_all_files(folder)
            for path, current_mtime in current_files.items():
                last_mtime = file_mtimes.get(path)
                if last_mtime is None or current_mtime > last_mtime:
                    file_mtimes[path] = current_mtime
                    if last_mtime is not None:
                        rel_path = os.path.relpath(path, folder)
                        event = "CREATED" if last_mtime is None else "MODIFIED"
                        print(f"[{event}] {rel_path}")
                        if copy_enabled:
                            copy_file(path, copy_dest)
                        lines = tail_file(path, n=10)
                        tail_text = "".join(lines)
                        if "boostraped 100%" in tail_text:
                            print(f"\n✓ Bootstrap complete detected! Exiting...\n")
                            sys.exit(0)
            deleted = set(file_mtimes.keys()) - set(current_files.keys())
            for path in deleted:
                rel_path = os.path.relpath(path, folder)
                print(f"[DELETED] {rel_path}")
                del file_mtimes[path]
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nWatcher stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
