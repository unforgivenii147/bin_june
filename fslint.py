#!/data/data/com.termux/files/usr/bin/env python
"""
fslint.py — FSLint reimplemented as a Python CLI tool.

Checks:
  --findup   Duplicate files (content hash)
  --findnl   Name lint (bad characters, mixed case, leading/trailing spaces)
  --findu8   Filenames not valid UTF-8
  --findbl   Bad symlinks (dangling, self-referential, or cyclic)
  --findem   Empty directories
  --findid   Files owned by non-existent UIDs/GIDs
  --findns   Non-stripped ELF binaries
  --findsn   Same-name files shadowed across PATH entries
  --findtf   Temporary / junk files
  --findwd   World-writable files and directories
  --findrs   Redundant whitespace in filenames
  --all      Run every check (default when no check flag is given)

Usage examples:
  python fslint.py --findem /home/user
  python fslint.py --findup --findtf /tmp
  python fslint.py --all /var/www
  python fslint.py --findsn          # scans $PATH, no path arg needed
"""

from __future__ import annotations

import argparse
import grp
import hashlib
import os
import pwd
import re
import stat
import struct
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Generator, Iterator

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GREEN = "\033[32m"
GREY = "\033[90m"


def _c(color: str, text: str) -> str:
    """Wrap *text* in ANSI color if stdout is a tty."""
    if sys.stdout.isatty():
        return f"{color}{text}{RESET}"
    return text


def header(title: str) -> None:
    width = 70
    print("\n" + _c(BOLD + CYAN, "━" * width))
    print(_c(BOLD + CYAN, f"  {title}"))
    print(_c(BOLD + CYAN, "━" * width))


def found(path: str | Path, note: str = "") -> None:
    note_str = f"  {_c(GREY, note)}" if note else ""
    print(f"  {_c(YELLOW, str(path))}{note_str}")


def ok(msg: str) -> None:
    print(_c(GREEN, f"  ✔  {msg}"))


def warn(msg: str) -> None:
    print(_c(RED, f"  ✘  {msg}"), file=sys.stderr)


# ---------------------------------------------------------------------------
# Generic filesystem walker
# ---------------------------------------------------------------------------


def walk(
    roots: list[Path],
    *,
    follow_symlinks: bool = False,
    yield_dirs: bool = True,
    yield_files: bool = True,
) -> Generator[Path, None, None]:
    """
    Yield every file/directory under each root.
    Never crosses symlinks unless follow_symlinks=True.
    """
    for root in roots:
        root = root.resolve() if follow_symlinks else root
        for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks, onerror=_walk_err):
            dp = Path(dirpath)
            if yield_dirs:
                yield dp
            if yield_files:
                for fn in filenames:
                    yield dp / fn
            # also yield symlinks that os.walk puts in filenames
            # (they are files from walk's perspective)


def _walk_err(exc: OSError) -> None:
    warn(f"walk error: {exc}")


# ---------------------------------------------------------------------------
# 1. findup — duplicate files
# ---------------------------------------------------------------------------

CHUNK = 65_536  # 64 KiB read chunks


def _file_hash(path: Path) -> str | None:
    """SHA-256 of file contents; None on read error."""
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            while chunk := fh.read(CHUNK):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def findup(roots: list[Path]) -> int:
    """Find duplicate files by content hash."""
    header("findup — Duplicate Files")

    # Group by (size, hash)
    size_map: dict[int, list[Path]] = defaultdict(list)
    for p in walk(roots, yield_dirs=False):
        if p.is_symlink():
            continue
        try:
            size_map[p.stat().st_size].append(p)
        except OSError:
            pass

    groups: dict[str, list[Path]] = defaultdict(list)
    for size, paths in size_map.items():
        if size == 0 or len(paths) < 2:
            continue  # unique by size already
        for p in paths:
            h = _file_hash(p)
            if h:
                groups[h].append(p)

    total = 0
    for digest, paths in sorted(groups.items()):
        if len(paths) < 2:
            continue
        size = paths[0].stat().st_size
        print(f"\n  {_c(BOLD, 'Hash:')} {digest[:16]}…  {_c(GREY, f'({size:,} bytes × {len(paths)})')}")
        for p in paths:
            found(p)
        total += len(paths) - 1  # originals don't count as waste

    if total == 0:
        ok("No duplicate files found.")
    else:
        print(f"\n  {_c(RED, f'{total} redundant copy/copies found.')}")
    return total


# ---------------------------------------------------------------------------
# 2. findnl — name lint
# ---------------------------------------------------------------------------

# Characters that are legal but commonly problematic
_NL_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("leading whitespace", re.compile(r"^\s")),
    ("trailing whitespace", re.compile(r"\s$")),
    ("consecutive spaces", re.compile(r"  ")),
    ("control character", re.compile(r"[\x00-\x1f\x7f]")),
    ("shell-special character", re.compile(r"[;`$!&|<>\\]")),
    ("mixed case (CamelCase)", re.compile(r"(?<=[a-z])(?=[A-Z])")),
    ("starts with hyphen", re.compile(r"^-")),
    ("trailing dot", re.compile(r"\.$")),
]


def findnl(roots: list[Path]) -> int:
    """Lint filenames for problematic characters and patterns."""
    header("findnl — Name Lint")
    total = 0
    for p in walk(roots):
        name = p.name
        if not name:
            continue
        issues = [label for label, rx in _NL_RULES if rx.search(name)]
        if issues:
            found(p, " | ".join(issues))
            total += 1
    if total == 0:
        ok("All filenames look clean.")
    return total


# ---------------------------------------------------------------------------
# 3. findu8 — non-UTF-8 filenames
# ---------------------------------------------------------------------------


def findu8(roots: list[Path]) -> int:
    """Find filenames that are not valid UTF-8."""
    header("findu8 — Non-UTF-8 Filenames")
    total = 0
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, onerror=_walk_err):
            all_names = dirnames + filenames
            for raw in all_names:
                # os.walk returns str via surrogateescape on Linux
                try:
                    raw.encode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    found(Path(dirpath) / raw, "not valid UTF-8")
                    total += 1
    if total == 0:
        ok("All filenames are valid UTF-8.")
    return total


# ---------------------------------------------------------------------------
# 4. findbl — bad symlinks
# ---------------------------------------------------------------------------


def _symlink_is_cyclic(path: Path, visited: set[Path] | None = None) -> bool:
    """Detect self-referential or cyclic symlink chains."""
    if visited is None:
        visited = set()
    try:
        real = path.resolve(strict=False)
    except OSError:
        return False
    if real in visited:
        return True
    visited.add(real)
    if real.is_symlink():
        return _symlink_is_cyclic(real, visited)
    return False


def findbl(roots: list[Path]) -> int:
    """Find bad (dangling, cyclic) symlinks."""
    header("findbl — Bad Symlinks")
    total = 0
    for p in walk(roots, yield_files=True, yield_dirs=True):
        if not p.is_symlink():
            continue
        target = Path(os.readlink(p))
        if not target.is_absolute():
            target = p.parent / target

        if _symlink_is_cyclic(p):
            found(p, f"cyclic → {os.readlink(p)}")
            total += 1
        elif not target.exists():
            found(p, f"dangling → {os.readlink(p)}")
            total += 1

    if total == 0:
        ok("No bad symlinks found.")
    return total


# ---------------------------------------------------------------------------
# 5. findem — empty directories
# ---------------------------------------------------------------------------


def findem(roots: list[Path]) -> int:
    """Find empty directories (recursively, innermost first)."""
    header("findem — Empty Directories")
    total = 0
    # Collect all dirs, sort deepest first so nested empties surface correctly
    all_dirs: list[Path] = []
    for p in walk(roots, yield_files=False, yield_dirs=True):
        all_dirs.append(p)

    all_dirs.sort(key=lambda p: len(p.parts), reverse=True)

    reported: set[Path] = set()
    for d in all_dirs:
        if d in reported:
            continue
        try:
            entries = list(d.iterdir())
        except PermissionError:
            continue
        if len(entries) == 0:
            found(d)
            reported.add(d)
            total += 1

    if total == 0:
        ok("No empty directories found.")
    return total


# ---------------------------------------------------------------------------
# 6. findid — bad uid/gid
# ---------------------------------------------------------------------------


def _valid_uids() -> set[int]:
    return {entry.pw_uid for entry in pwd.getpwall()}


def _valid_gids() -> set[int]:
    return {entry.gr_gid for entry in grp.getgrall()}


def findid(roots: list[Path]) -> int:
    """Find files owned by non-existent UIDs or GIDs."""
    header("findid — Bad UID/GID Ownership")
    valid_uids = _valid_uids()
    valid_gids = _valid_gids()
    total = 0
    for p in walk(roots):
        try:
            st = p.lstat()
        except OSError:
            continue
        issues = []
        if st.st_uid not in valid_uids:
            issues.append(f"unknown uid={st.st_uid}")
        if st.st_gid not in valid_gids:
            issues.append(f"unknown gid={st.st_gid}")
        if issues:
            found(p, " | ".join(issues))
            total += 1
    if total == 0:
        ok("All files have valid UID/GID.")
    return total


# ---------------------------------------------------------------------------
# 7. findns — non-stripped binaries
# ---------------------------------------------------------------------------

ELF_MAGIC = b"\x7fELF"


def _is_elf(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(4) == ELF_MAGIC
    except OSError:
        return False


def _has_debug_symbols(path: Path) -> bool:
    """
    Return True if the ELF binary still has a symbol table.
    We check for the presence of a .symtab or .debug_info section
    using 'readelf' if available, otherwise fall back to a raw header check.
    """
    # Try readelf first (most reliable)
    try:
        result = subprocess.run(
            ["readelf", "--sections", "--wide", str(path)], capture_output=True, text=True, timeout=10
        )
        output = result.stdout
        return ".symtab" in output or ".debug_info" in output
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: scan raw bytes for section name strings
    try:
        data = path.read_bytes()
        return b".symtab" in data or b".debug_info" in data
    except OSError:
        return False


def findns(roots: list[Path]) -> int:
    """Find non-stripped ELF binaries that still contain debug symbols."""
    header("findns — Non-Stripped Binaries")
    total = 0
    for p in walk(roots, yield_dirs=False):
        if p.is_symlink():
            continue
        if not _is_elf(p):
            continue
        if _has_debug_symbols(p):
            try:
                size_kb = p.stat().st_size // 1024
            except OSError:
                size_kb = 0
            found(p, f"{size_kb:,} KB, has debug symbols")
            total += 1
    if total == 0:
        ok("No non-stripped binaries found.")
    return total


# ---------------------------------------------------------------------------
# 8. findsn — same-name files in PATH (shadowed executables)
# ---------------------------------------------------------------------------


def findsn(_roots: list[Path] | None = None) -> int:
    """
    Find executables that appear in multiple PATH directories.
    The first entry shadows the rest — flag all shadows.
    """
    header("findsn — Shadowed PATH Executables")
    path_env = os.environ.get("PATH", "")
    path_dirs = [Path(d) for d in path_env.split(os.pathsep) if d]

    seen: dict[str, list[Path]] = defaultdict(list)
    for d in path_dirs:
        if not d.is_dir():
            continue
        try:
            for entry in d.iterdir():
                if entry.is_file() and os.access(entry, os.X_OK):
                    seen[entry.name].append(entry)
        except PermissionError:
            pass

    total = 0
    for name, paths in sorted(seen.items()):
        if len(paths) < 2:
            continue
        print(f"\n  {_c(BOLD, name)}")
        for i, p in enumerate(paths):
            label = "active" if i == 0 else "shadowed"
            color = GREEN if i == 0 else RED
            print(f"    {_c(color, label):<20} {p}")
        total += len(paths) - 1

    if total == 0:
        ok("No shadowed PATH executables found.")
    return total


# ---------------------------------------------------------------------------
# 9. findtf — temporary / junk files
# ---------------------------------------------------------------------------

_TF_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"~$"),  # editor backups
    re.compile(r"^#.*#$"),  # Emacs auto-save
    re.compile(r"\.bak$", re.I),
    re.compile(r"\.tmp$", re.I),
    re.compile(r"\.temp$", re.I),
    re.compile(r"\.swp$", re.I),  # Vim swap
    re.compile(r"\.swo$", re.I),
    re.compile(r"^\.DS_Store$"),  # macOS metadata
    re.compile(r"^Thumbs\.db$", re.I),  # Windows thumbnails
    re.compile(r"^desktop\.ini$", re.I),
    re.compile(r"\.orig$", re.I),
    re.compile(r"\.rej$", re.I),  # patch reject files
    re.compile(r"core\.\d+$"),  # core dumps
    re.compile(r"^core$"),
    re.compile(r"\.log$", re.I),
    re.compile(r"\.pid$", re.I),
    re.compile(r"__pycache__"),
    re.compile(r"\.pyc$"),
    re.compile(r"\.pyo$"),
    re.compile(r"node_modules"),
    re.compile(r"\.class$"),  # Java bytecode
    re.compile(r"\.o$"),  # object files
    re.compile(r"\.a$"),  # static libs (often junk in src)
]


def findtf(roots: list[Path]) -> int:
    """Find temporary and junk files."""
    header("findtf — Temporary / Junk Files")
    total = 0
    for p in walk(roots):
        name = p.name
        for rx in _TF_PATTERNS:
            if rx.search(name):
                found(p, f"matches pattern: {rx.pattern!r}")
                total += 1
                break  # one match per path is enough
    if total == 0:
        ok("No temporary files found.")
    return total


# ---------------------------------------------------------------------------
# 10. findwd — world-writable files/directories
# ---------------------------------------------------------------------------


def findwd(roots: list[Path]) -> int:
    """Find world-writable files and directories (potential security risk)."""
    header("findwd — World-Writable Items")
    total = 0
    for p in walk(roots):
        try:
            mode = p.lstat().st_mode
        except OSError:
            continue
        if mode & stat.S_IWOTH:
            kind = "dir" if stat.S_ISDIR(mode) else "file"
            perms = oct(stat.S_IMODE(mode))
            found(p, f"{kind}, mode={perms}")
            total += 1
    if total == 0:
        ok("No world-writable items found.")
    return total


# ---------------------------------------------------------------------------
# 11. findrs — redundant whitespace in filenames
# ---------------------------------------------------------------------------

_RS_RE = re.compile(r"  |^\s|\s$|\t")  # double space, leading/trailing, tabs


def findrs(roots: list[Path]) -> int:
    """Find filenames with redundant whitespace."""
    header("findrs — Redundant Whitespace in Filenames")
    total = 0
    for p in walk(roots):
        if _RS_RE.search(p.name):
            visible = repr(p.name)
            found(p, f"name repr: {visible}")
            total += 1
    if total == 0:
        ok("No redundant whitespace in filenames found.")
    return total


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

ALL_CHECKS: dict[str, tuple[str, callable]] = {
    "findup": ("Duplicate files", findup),
    "findnl": ("Name lint", findnl),
    "findu8": ("Non-UTF-8 filenames", findu8),
    "findbl": ("Bad symlinks", findbl),
    "findem": ("Empty directories", findem),
    "findid": ("Bad UID/GID ownership", findid),
    "findns": ("Non-stripped binaries", findns),
    "findsn": ("Shadowed PATH executables", findsn),
    "findtf": ("Temporary / junk files", findtf),
    "findwd": ("World-writable items", findwd),
    "findrs": ("Redundant whitespace names", findrs),
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fslint",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path.cwd()],
        metavar="PATH",
        help="Directory/directories to scan (default: current directory)",
    )
    p.add_argument(
        "--all",
        "-a",
        action="store_true",
        dest="run_all",
        help="Run all checks (default when no check flag is given)",
    )
    p.add_argument(
        "--summary",
        "-s",
        action="store_true",
        help="Print a one-line summary table at the end",
    )

    group = p.add_argument_group("checks")
    for flag, (desc, _fn) in ALL_CHECKS.items():
        group.add_argument(
            f"--{flag}",
            action="store_true",
            default=False,
            help=desc,
        )

    return p


def print_summary(results: dict[str, int]) -> None:
    """Print a compact summary table of all check results."""
    width = 42
    print("\n" + _c(BOLD, "┌" + "─" * width + "┐"))
    print(_c(BOLD, f"│{'SUMMARY':^{width}}│"))
    print(_c(BOLD, "├" + "─" * 28 + "┬" + "─" * (width - 29) + "┤"))
    for flag, count in results.items():
        desc = ALL_CHECKS[flag][0]
        color = RED if count > 0 else GREEN
        count_str = _c(color, str(count).rjust(6))
        print(f"│ {_c(BOLD, flag):<18} {desc:<22} │ {count_str} │")
    print(_c(BOLD, "└" + "─" * 28 + "┴" + "─" * (width - 29) + "┘"))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Validate paths
    roots: list[Path] = []
    for p in args.paths:
        if not p.exists():
            warn(f"Path does not exist: {p}")
            continue
        if not p.is_dir():
            warn(f"Not a directory: {p}")
            continue
        roots.append(p.resolve())

    if not roots:
        # findsn doesn't need a path; allow it to run anyway
        if not args.findsn:
            warn("No valid paths to scan.")
            return 1
        roots = [Path.cwd()]

    # Determine which checks to run
    requested = [flag for flag in ALL_CHECKS if getattr(args, flag, False)]
    if args.run_all or not requested:
        requested = list(ALL_CHECKS.keys())

    print(_c(BOLD + CYAN, "\nFSLint — Filesystem Lint Tool"))
    print(_c(GREY, f"Scanning: {', '.join(str(r) for r in roots)}"))
    print(_c(GREY, f"Checks:   {', '.join(requested)}"))

    results: dict[str, int] = {}
    exit_code = 0

    for flag in requested:
        _desc, fn = ALL_CHECKS[flag]
        try:
            # findsn ignores roots (uses $PATH instead)
            count = fn(roots) if flag != "findsn" else fn()
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
            return 130
        except Exception as exc:
            warn(f"{flag} failed: {exc}")
            count = -1
        results[flag] = count
        if count > 0:
            exit_code = 1

    if args.summary or len(requested) > 1:
        print_summary(results)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
