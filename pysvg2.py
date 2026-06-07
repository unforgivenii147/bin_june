#!/data/data/com.termux/files/usr/bin/python

import subprocess
import sys
import tempfile
from pathlib import Path

from dh import get_files, mpf3, runcmd


def process_file(path):
    if not path.exists():
        return
    before = path.stat().st_size
    tmp_out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp_out:
            tmp_out_path = tmp_out.name
        runcmd(["svgcleaner", str(path), str(tmp_out_path)], show_output=False)
        after = Path(tmp_out_path).stat().st_size
        size_change = before - after
        if after:
            Path(tmp_out_path).replace(path)
            return (True, path, before, after, size_change)
        return (False, path, before, after, size_change)
    except subprocess.CalledProcessError as e:
        return (False, path, 0, 0, f"Error: {e.stderr.decode('utf-8')}")
    except Exception as e:
        return (False, path, 0, 0, f"Unexpected error: {e}")
    finally:
        if tmp_out_path and Path(tmp_out_path).exists():
            Path(tmp_out_path).unlink()


if __name__ == "__main__":
    cwd = Path.cwd()
    files = get_files(cwd, ext=[".svg"])
    if not files:
        print("No SVG files found.")
        sys.exit(1)
    total_before = 0
    total_after = 0
    total_saved = 0
    results = mpf3(process_file, files)
    for result in results:
        success, f, before, after, size_change = result
        if success:
            print(f"Cleaned: {f}")
            print(f"  Before: {before} bytes, After: {after} bytes, Saved: {size_change} bytes")
            total_before += before
            total_after += after
            total_saved += size_change
    print(f"Total size saved: {total_saved} bytes")
