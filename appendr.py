#!/data/data/com.termux/files/home/.local/bin/python
"""
Run type checkers (ty, pyright, pylint) on Python files recursively and append results to files.
"""

import sys
import subprocess
import argparse
from pathlib import Path
from typing import NamedTuple
from dataclasses import dataclass
import logging

from dh import mpf3, get_pyfiles

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class CheckerConfig(NamedTuple):
    """Configuration for a specific checker tool."""

    name: str
    command: list[str]
    ignore_patterns: set[str]


@dataclass
class FileStats:
    """Statistics for a single file check."""

    filepath: Path
    tool: str
    has_errors: bool
    issue_count: int
    added_comments: bool
    error_msg: str = ""

    def __str__(self) -> str:
        relpath = self.filepath.relative_to(Path.cwd())
        status = "✓" if not self.has_errors else "✗"

        if self.error_msg:
            return f"{status} {relpath:50} | {self.tool:8} | ERROR: {self.error_msg}"

        if self.has_errors:
            return f"{status} {relpath:50} | {self.tool:8} | {self.issue_count} issue(s) found, appended"

        return f"{status} {relpath:50} | {self.tool:8} | No issues"


def get_checker_config(checker: str) -> CheckerConfig:
    """Get configuration for the specified checker tool."""
    configs = {
        "ty": CheckerConfig(name="ty", command=["ty", "check"], ignore_patterns={"unresolved-import"}),
        "pyright": CheckerConfig(name="pyright", command=["pyright", "--outputjson"], ignore_patterns=set()),
        "pylint": CheckerConfig(name="pylint", command=["pylint", "--exit-zero"], ignore_patterns=set()),
    }

    if checker not in configs:
        raise ValueError(f"Unknown checker: {checker}. Choose from: {', '.join(configs.keys())}")

    return configs[checker]


def run_checker(filepath: Path, config: CheckerConfig) -> tuple[str, bool]:
    """
    Run a checker tool on a file.

    Returns:
        Tuple of (output, has_issues) where output is the raw checker output
        and has_issues indicates if diagnostic issues were found.
    """
    try:
        cmd = config.command + [str(filepath)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        output = result.stdout + result.stderr
        has_issues = result.returncode != 0 and output.strip()

        return output, has_issues

    except subprocess.TimeoutExpired:
        return f"TIMEOUT: {config.name} took too long", True
    except FileNotFoundError:
        return f"ERROR: {config.name} not found in PATH", True
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {str(e)}", True


def filter_output_for_ty(output: str, ignore_patterns: set[str]) -> str:
    """
    Filter ty output to ignore unresolved-import errors for custom modules.

    Removes entire error blocks matching ignore patterns.
    """
    if not ignore_patterns:
        return output

    lines = output.split("\n")
    filtered_lines = []
    skip_block = False

    for line in lines:
        # Check if line starts an error block with ignored pattern
        if any(f"error[{pattern}]" in line for pattern in ignore_patterns):
            skip_block = True
            continue

        # End of error block (empty line or new error/info)
        if skip_block and (not line.strip() or line.startswith("error[") or line.startswith("info:")):
            skip_block = False

        if not skip_block:
            filtered_lines.append(line)

    filtered_output = "\n".join(filtered_lines).strip()

    # Remove trailing "Found X diagnostic" if all were filtered
    if not any(f"error[{p}]" not in output for p in ignore_patterns):
        lines = filtered_output.split("\n")
        filtered_output = "\n".join(
            line for line in lines if not line.startswith("Found") or "diagnostic" not in line
        ).strip()

    return filtered_output


def append_to_file(filepath: Path, content: str, tool_name: str) -> bool:
    """
    Append checker output to file in commented format.

    Returns True if content was appended, False if file already has comments for this tool.
    """
    if not content.strip():
        return False

    try:
        with open(filepath, "a", encoding="utf-8") as f:
            # Add separator
            f.write(f"\n\n# ============ {tool_name} output ============\n")

            # Comment each line
            for line in content.split("\n"):
                if line.strip():
                    f.write(f"# {line}\n")
                else:
                    f.write("#\n")

        return True

    except Exception as e:
        logger.error(f"Failed to append to {filepath}: {e}")
        return False


def process_file(filepath: Path, checkers: list[str], in_place: bool = True) -> list[FileStats]:
    """
    Process a single Python file with specified checkers.

    Returns list of FileStats for each checker run.
    """
    stats = []

    for checker_name in checkers:
        config = get_checker_config(checker_name)
        output, has_issues = run_checker(filepath, config)

        # Filter output based on checker-specific rules
        if checker_name == "ty":
            output = filter_output_for_ty(output, config.ignore_patterns)
            has_issues = bool(output.strip())

        # Append to file if requested and has issues
        appended = False
        if in_place and has_issues:
            appended = append_to_file(filepath, output, config.name)

        issue_count = output.count("error[") if checker_name == "ty" else 0

        stat = FileStats(
            filepath=filepath,
            tool=checker_name,
            has_errors=has_issues,
            issue_count=issue_count,
            added_comments=appended,
        )
        stats.append(stat)

    return stats


def get_python_files(paths: list[str]) -> list[Path]:
    """
    Collect all Python files from given paths.

    If no paths provided, uses current directory.
    """
    if not paths:
        paths = ["."]

    all_files = []
    for path_str in paths:
        path = Path(path_str).resolve()

        if path.is_file():
            if path.suffix == ".py":
                all_files.append(path)
        elif path.is_dir():
            # Use custom dh.get_pyfiles for consistency
            try:
                all_files.extend(get_pyfiles(path))
            except Exception:
                # Fallback to standard pathlib
                all_files.extend(path.glob("**/*.py"))
        else:
            logger.warning(f"Path does not exist: {path}")

    return sorted(set(all_files))  # Remove duplicates


def main():
    parser = argparse.ArgumentParser(
        description="Run type checkers on Python files recursively and append results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Check current dir with ty
  %(prog)s -g src/                  # Check src/ with pyright
  %(prog)s -a file1.py file2.py     # Check files with all tools
  %(prog)s -t pylint src/ tests/    # Check multiple dirs with pylint
        """,
    )

    parser.add_argument("paths", nargs="*", help="Files or directories to check (default: current directory)")

    parser.add_argument(
        "-t", "--tool", default="ty", choices=["ty", "pyright", "pylint"], help="Checker tool to use (default: ty)"
    )

    parser.add_argument(
        "-g", "--pyright", action="store_const", const="pyright", dest="tool", help="Use pyright instead of ty"
    )

    parser.add_argument(
        "-p", "--pylint", action="store_const", const="pylint", dest="tool", help="Use pylint instead of ty"
    )

    parser.add_argument("-a", "--all", action="store_true", help="Run all tools (ty, pyright, pylint)")

    parser.add_argument("--no-append", action="store_true", help="Don't append output to files, just report")

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Determine which checkers to use
    if args.all:
        checkers = ["ty", "pyright", "pylint"]
    else:
        checkers = [args.tool]

    # Get Python files
    files = get_python_files(args.paths)

    if not files:
        logger.warning("No Python files found")
        sys.exit(0)

    logger.info(f"Found {len(files)} Python file(s)")
    logger.info(f"Running {', '.join(checkers)} on {len(files)} file(s) with 4 workers...\n")

    # Process files in parallel
    process_func = lambda f: process_file(f, checkers, not args.no_append)
    all_stats = mpf3(process_func, files, n_jobs=4)

    # Flatten results
    all_stats = [stat for stats_list in all_stats for stat in stats_list]

    # Print results
    logger.info("\n" + "=" * 120)
    logger.info("RESULTS")
    logger.info("=" * 120)

    for stat in all_stats:
        logger.info(str(stat))

    # Summary statistics
    logger.info("\n" + "=" * 120)
    logger.info("SUMMARY")
    logger.info("=" * 120)

    for checker in checkers:
        checker_stats = [s for s in all_stats if s.tool == checker]
        files_with_issues = sum(1 for s in checker_stats if s.has_errors)
        files_updated = sum(1 for s in checker_stats if s.added_comments)

        logger.info(
            f"{checker:10} | Files: {len(checker_stats):3} | "
            f"With issues: {files_with_issues:3} | Updated: {files_updated:3}"
        )

    logger.info("=" * 120)

    # Exit with error if any issues found
    has_any_issues = any(s.has_errors for s in all_stats)
    sys.exit(1 if has_any_issues else 0)


if __name__ == "__main__":
    main()
