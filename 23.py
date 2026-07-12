#!/data/data/com.termux/files/usr/bin/env python


import subprocess
import sys
from multiprocessing import Lock, Pool
from pathlib import Path

from fastwalk import walk_files

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


print_lock = Lock()


def is_python_file(path: Path) -> bool:
    if path.suffix == ".py":
        return True
    if path.suffix == "":
        try:
            with Path(path).open("rb") as f:
                head = f.read(64)
                if b"python" in head and b"#!" in head:
                    return True
        except Exception:
            return False
    return False


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding="utf-8")
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def process_file(file_path) -> None:
    print(f"[OK] {file_path.name}")
    path = Path(path)
    check_cmd = ["ruff", "check", "--fix", "--unsafe-fixes", "--line-length", "120", "--quiet", str(file_path)]
    rc_check, out_check, err_check = run_command(check_cmd)
    format_cmd = [
        "ruff",
        "format",
        "--config",
        "/data/data/com.termux/files/home/.config/ruff/ruff.toml",
        str(file_path),
    ]
    rc_fmt, _out_fmt, err_fmt = run_command(format_cmd)
    output = []
    if rc_check != 0 or err_check.strip():
        output.append(f"--- Issues fixing {path.name} ---")
        if err_check.strip():
            output.append(err_check.strip())
        if out_check.strip():
            output.append(out_check.strip())
    if rc_fmt != 0 or err_fmt.strip():
        output.append(f"--- Issues formatting {file_path.name} ---")
        if err_fmt.strip():
            output.append(err_fmt.strip())
    if output:
        with print_lock:
            print("\n".join(output))
            sys.stdout.flush()


def get_all_files(cwd: Path):
    py_files = []
    for pth in walk_files(cwd):
        path = Path(pth)
        if path.is_file() and is_python_file(path):
            py_files.append(path)
    return py_files


def main() -> None:
    try:
        subprocess.run(["ruff", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Error: 'ruff' is not installed or not in PATH.")
        print("Please run: pip install ruff")
        sys.exit(1)
    cwd = Path.cwd()
    files = get_all_files(cwd)
    if not files:
        print("no file found.")
        return
    pool = Pool(8)
    for f in files:
        pool.apply_async(process_file, (f,))
    pool.close()
    pool.join()


if __name__ == "__main__":
    main()
