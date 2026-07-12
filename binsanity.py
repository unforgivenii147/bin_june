#!/data/data/com.termux/files/usr/bin/env python


from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def get_filez(root_dir: (str | Path)):
    from os import walk as os_walk

    visited_dirs: set[Path] = set()
    root_dir = Path(root_dir)
    if root_dir.is_dir():
        for dirpath, dirnames, filenames in os_walk(root_dir, topdown=True):
            base_path = Path(dirpath)
            for dirname in list(dirnames):
                full_path = base_path / dirname
                resolved_path = full_path.resolve()
                if should_skip(full_path) or resolved_path in visited_dirs:
                    dirnames.remove(dirname)
                visited_dirs.add(resolved_path)
            for filename in filenames:
                filepath = Path(dirpath) / filename
                if not should_skip(filepath):
                    yield filepath
    else:
        yield root_dir


def should_skip(path: (str | Path)) -> bool:
    path = Path(path)
    return bool(path.is_symlink() or not SKIP_DIRS.isdisjoint(path.parts))


"""
Binary File Analyzer - Finds executables in current directory that fail to run
Uses concurrent.futures for parallel processing
Outputs results to ~/tmp/err
"""

import concurrent.futures
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from binaryornot import is_binary


def is_executable(filepath: Path) -> bool:
    return filepath.is_file() and filepath.stat().st_mode & 0o111 != 0


def is_elf(filepath: Path) -> bool:
    if not is_binary(str(filepath)):
        return False
    try:
        header = filepath.read_bytes()[:4]
        if header[:4] == b"\x7fELF":
            return True
        if header[:2] == b"#!":
            return False
    except (IOError, OSError):
        pass
    return False


def get_binary_files(directory: Path) -> List[Path]:
    """Get all executable binary files in a directory"""
    binaries = []
    try:
        for path in get_filez(directory):
            if ".git" in path.parts or path.is_symlink():
                continue
            if path.is_file() and is_executable(path) and is_elf(path):
                binaries.append(path)
    except PermissionError:
        pass
    return binaries


def test_executable(filepath: Path) -> Tuple[Path, Optional[str]]:
    test_args = ["--help", "-h", "--version", "-v", "--info"]
    for test_arg in test_args:
        try:
            result = subprocess.run([str(filepath), test_arg], capture_output=True, text=True, timeout=2)
            if result.stderr:
                error_lower = result.stderr.lower()
                if any(
                    pattern in error_lower
                    for pattern in [
                        "error while loading shared libraries",
                        "cannot open shared object file",
                        "no such file",
                        "not found",
                        "failed to load",
                    ]
                ):
                    return filepath, result.stderr.strip()[:200]
            if result.returncode == 0:
                return filepath, None
        except subprocess.TimeoutExpired:
            return filepath, None
        except FileNotFoundError:
            return filepath, "File not found"
        except PermissionError:
            return filepath, "Permission denied"
        except OSError as e:
            if "exec format error" in str(e):
                return filepath, "Exec format error (wrong architecture)"
            return filepath, str(e)
    try:
        result = subprocess.run([str(filepath)], capture_output=True, text=True, timeout=1)
        if result.stderr:
            error_lower = result.stderr.lower()
            if any(
                pattern in error_lower
                for pattern in [
                    "error while loading shared libraries",
                    "cannot open shared object file",
                    "no such file",
                ]
            ):
                return filepath, result.stderr.strip()[:200]
        return filepath, None
    except subprocess.TimeoutExpired:
        return filepath, None
    except Exception as e:
        return filepath, str(e)[:200]


def main() -> None:
    output_dir = Path.home() / "tmp"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "err"
    cwd = Path.cwd()
    binaries = get_binary_files(cwd)
    if not binaries:
        print("No executable binaries found in current directory")
        output_file.write_text("No executable binaries found in current directory\n")
        return
    print(f"Found {len(binaries)} binaries to test")
    print("Testing binaries in parallel...")
    failed_binaries = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        future_to_binary = {executor.submit(test_executable, binary): binary for binary in binaries}
        for i, future in enumerate(concurrent.futures.as_completed(future_to_binary), 1):
            binary = future_to_binary[future]
            try:
                filepath, error_msg = future.result()
                if error_msg:
                    failed_binaries.append((filepath, error_msg))
                    print(f"  [{i}/{len(binaries)}] ❌ {binary.name} - FAILED")
                else:
                    print(f"  [{i}/{len(binaries)}] ✅ {binary.name} - OK")
            except Exception as e:
                failed_binaries.append((binary, f"Test exception: {str(e)[:100]}"))
                print(f"  [{i}/{len(binaries)}] ⚠️ {binary.name} - ERROR")
    out_dir = cwd / "err"
    out_dir.mkdir(exist_ok=True)
    for filepath, _ in failed_binaries:
        new_path = out_dir / filepath.name
        filepath.rename(new_path)
    output_file.write_text(
        f"Binary Analysis Results\n"
        f"Directory: {cwd}\n"
        f"Total binaries tested: {len(binaries)}\n"
        f"Failed binaries: {len(failed_binaries)}\n"
        f"{'=' * 70}\n\n"
        + (
            "\n".join(f"Binary: {filepath}\nError:  {error_msg}\n{'-' * 70}" for filepath, error_msg in failed_binaries)
            if failed_binaries
            else "✓ All binaries tested successfully!\n"
        )
    )
    print("\n" + "=" * 35)
    print(f"Failed: {len(failed_binaries)}")
    print(f"Success: {len(binaries) - len(failed_binaries)}")
    if failed_binaries:
        for filepath, error_msg in failed_binaries:
            print(f"  • {filepath.name}")
            print(f"    → {error_msg[:100]}")
    else:
        print(f"\n✅ All binaries are working correctly!")
        print(f"Report written to: {output_file}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScan interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
