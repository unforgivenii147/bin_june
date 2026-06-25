#!/data/data/com.termux/files/usr/bin/python
"""
Script to detect potentially missing standard library imports in Python files.
Recursively scans directories and reports stdlib names that are used but not imported.
"""

import ast
import os
import sys
import importlib
import keyword
from pathlib import Path
from collections import defaultdict
from typing import Set, Dict, List, Tuple


# Standard library modules (Python 3.x)
STDLIB_MODULES = {
    "abc",
    "aifc",
    "argparse",
    "array",
    "ast",
    "asynchat",
    "asyncio",
    "asyncore",
    "atexit",
    "audioop",
    "base64",
    "bdb",
    "binascii",
    "binhex",
    "bisect",
    "builtins",
    "bz2",
    "calendar",
    "cgi",
    "cgitb",
    "chunk",
    "cmath",
    "cmd",
    "code",
    "codecs",
    "codeop",
    "collections",
    "colorsys",
    "compileall",
    "concurrent",
    "configparser",
    "contextlib",
    "contextvars",
    "copy",
    "copyreg",
    "cProfile",
    "crypt",
    "csv",
    "ctypes",
    "curses",
    "dataclasses",
    "datetime",
    "dbm",
    "decimal",
    "difflib",
    "dis",
    "distutils",
    "doctest",
    "email",
    "encodings",
    "enum",
    "errno",
    "faulthandler",
    "fcntl",
    "filecmp",
    "fileinput",
    "fnmatch",
    "formatter",
    "fractions",
    "ftplib",
    "functools",
    "gc",
    "getopt",
    "getpass",
    "gettext",
    "glob",
    "graphlib",
    "grp",
    "gzip",
    "hashlib",
    "heapq",
    "hmac",
    "html",
    "http",
    "idlelib",
    "imaplib",
    "imghdr",
    "imp",
    "importlib",
    "inspect",
    "io",
    "ipaddress",
    "itertools",
    "json",
    "keyword",
    "lib2to3",
    "linecache",
    "locale",
    "logging",
    "lzma",
    "mailbox",
    "mailcap",
    "marshal",
    "math",
    "mimetypes",
    "mmap",
    "modulefinder",
    "multiprocessing",
    "netrc",
    "nis",
    "nntplib",
    "numbers",
    "operator",
    "os",
    "ossaudiodev",
    "parser",
    "pathlib",
    "pdb",
    "pickle",
    "pickletools",
    "pipes",
    "pkgutil",
    "platform",
    "plistlib",
    "poplib",
    "posix",
    "pprint",
    "profile",
    "pstats",
    "pty",
    "pwd",
    "py_compile",
    "pyclbr",
    "pydoc",
    "queue",
    "quopri",
    "random",
    "re",
    "readline",
    "reprlib",
    "resource",
    "rlcompleter",
    "runpy",
    "sched",
    "secrets",
    "select",
    "selectors",
    "shelve",
    "shlex",
    "shutil",
    "signal",
    "site",
    "smtpd",
    "smtplib",
    "sndhdr",
    "socket",
    "socketserver",
    "sqlite3",
    "ssl",
    "stat",
    "statistics",
    "string",
    "stringprep",
    "struct",
    "subprocess",
    "sunau",
    "symtable",
    "sys",
    "sysconfig",
    "syslog",
    "tabnanny",
    "tarfile",
    "telnetlib",
    "tempfile",
    "termios",
    "test",
    "textwrap",
    "threading",
    "time",
    "timeit",
    "tkinter",
    "token",
    "tokenize",
    "trace",
    "traceback",
    "tracemalloc",
    "tty",
    "turtle",
    "turtledemo",
    "types",
    "typing",
    "unicodedata",
    "unittest",
    "urllib",
    "uu",
    "uuid",
    "venv",
    "warnings",
    "wave",
    "weakref",
    "webbrowser",
    "winreg",
    "winsound",
    "wsgiref",
    "xdrlib",
    "xml",
    "xmlrpc",
    "zipapp",
    "zipfile",
    "zipimport",
    "zlib",
    # Common submodules that are frequently imported
    "collections.abc",
    "collections.defaultdict",
    "collections.OrderedDict",
    "os.path",
    "datetime.datetime",
    "datetime.date",
    "datetime.time",
    "datetime.timedelta",
    "json.dumps",
    "json.loads",
    "sys.argv",
    "sys.path",
    "sys.stdin",
    "sys.stdout",
    "sys.stderr",
}


def get_stdlib_names() -> Dict[str, Set[str]]:
    """
    Build a mapping of common stdlib modules to their commonly used names/attributes.
    This helps detect when someone uses e.g., 'defaultdict' without importing it.
    """
    stdlib_names = {
        "os": {
            "path",
            "environ",
            "getenv",
            "listdir",
            "walk",
            "remove",
            "rename",
            "mkdir",
            "makedirs",
            "chdir",
            "getcwd",
            "sep",
            "linesep",
        },
        "sys": {
            "argv",
            "path",
            "stdin",
            "stdout",
            "stderr",
            "exit",
            "version",
            "platform",
            "executable",
            "modules",
        },
        "math": {
            "sqrt",
            "ceil",
            "floor",
            "sin",
            "cos",
            "tan",
            "pi",
            "e",
            "log",
            "log10",
            "exp",
            "pow",
            "fabs",
            "factorial",
        },
        "random": {
            "random",
            "randint",
            "choice",
            "shuffle",
            "sample",
            "uniform",
            "seed",
            "randrange",
        },
        "datetime": {"datetime", "date", "time", "timedelta", "timezone"},
        "json": {"dumps", "loads", "dump", "load"},
        "collections": {"defaultdict", "OrderedDict", "Counter", "deque", "namedtuple"},
        "itertools": {
            "chain",
            "cycle",
            "repeat",
            "count",
            "islice",
            "groupby",
            "combinations",
            "permutations",
            "product",
        },
        "functools": {"reduce", "partial", "lru_cache", "wraps", "cache"},
        "pathlib": {"Path", "PurePath", "PurePosixPath", "PureWindowsPath"},
        "re": {"match", "search", "findall", "sub", "compile", "split", "escape"},
        "argparse": {"ArgumentParser", "Namespace"},
        "logging": {
            "debug",
            "info",
            "warning",
            "error",
            "critical",
            "getLogger",
            "basicConfig",
        },
        "statistics": {"mean", "median", "mode", "stdev", "variance"},
        "typing": {
            "List",
            "Dict",
            "Set",
            "Tuple",
            "Optional",
            "Union",
            "Any",
            "Callable",
            "Iterator",
        },
        "decimal": {"Decimal"},
        "fractions": {"Fraction"},
        "hashlib": {"md5", "sha1", "sha256", "sha512"},
        "subprocess": {"run", "Popen", "call", "check_output"},
        "shutil": {"copy", "copy2", "move", "rmtree", "make_archive"},
        "tempfile": {"NamedTemporaryFile", "TemporaryFile", "mkdtemp"},
        "glob": {"glob"},
        "time": {
            "time",
            "sleep",
            "ctime",
            "localtime",
            "gmtime",
            "strftime",
            "strptime",
        },
    }

    # Add module names themselves
    for module in STDLIB_MODULES:
        if "." not in module:  # Only top-level modules
            if module not in stdlib_names:
                stdlib_names[module] = set()

    return stdlib_names


class ImportChecker(ast.NodeVisitor):
    """AST visitor that collects imports and used names."""

    def __init__(self, stdlib_names: Dict[str, Set[str]]):
        self.stdlib_names = stdlib_names
        self.imports = {}  # name -> module mapping
        self.used_names = set()  # all used names
        self.import_nodes = []  # all import statements for analysis

    def visit_Import(self, node):
        """Handle 'import module' statements."""
        for alias in node.names:
            module_name = alias.name
            local_name = alias.asname if alias.asname else module_name.split(".")[0]
            self.imports[local_name] = module_name
        self.import_nodes.append(node)

    def visit_ImportFrom(self, node):
        """Handle 'from module import name' statements."""
        module = node.module or ""
        for alias in node.names:
            name = alias.name
            local_name = alias.asname if alias.asname else name
            full_name = f"{module}.{name}" if module else name
            self.imports[local_name] = full_name
        self.import_nodes.append(node)

    def visit_Name(self, node):
        """Record all name usage."""
        if isinstance(node.ctx, (ast.Load, ast.Del)):
            self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        """Record attribute access like os.path."""
        # Build full attribute chain
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            full_attr = ".".join(reversed(parts))
            self.used_names.add(full_attr)
        self.generic_visit(node)


def find_missing_imports(filepath: str, stdlib_names: Dict[str, Set[str]]) -> List[Tuple[str, str]]:
    """
    Analyze a Python file and find potentially missing stdlib imports.
    Returns list of (name, suggested_import) tuples.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return []

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}", file=sys.stderr)
        return []

    # Collect imports and used names
    checker = ImportChecker(stdlib_names)
    checker.visit(tree)

    missing = []
    builtin_names = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set()
    keywords = set(keyword.kwlist)

    # Filter to only consider stdlib names
    for name in checker.used_names:
        # Skip if already imported
        if name in checker.imports:
            continue
        # Skip builtins and keywords
        if name in builtin_names or name in keywords:
            continue
        # Skip special names
        if name.startswith("_"):
            continue

        # Check if this name is a stdlib module or attribute
        if name in stdlib_names:
            # It's a top-level module that's not imported
            missing.append((name, f"import {name}"))
        else:
            # Check if it's a known attribute of a stdlib module
            for module, attrs in stdlib_names.items():
                if name in attrs:
                    if module not in checker.imports:
                        missing.append((name, f"from {module} import {name}"))
                    break

    return missing


def scan_directory(root_dir: str, exclude_dirs: Set[str] = None) -> Dict[str, List[Tuple[str, str]]]:
    """
    Recursively scan directory for Python files and check for missing imports.

    Args:
        root_dir: Root directory to scan
        exclude_dirs: Set of directory names to exclude

    Returns:
        Dictionary mapping file paths to list of (name, import_statement) tuples
    """
    if exclude_dirs is None:
        exclude_dirs = {
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "env",
            ".env",
            "build",
            "dist",
            "egg-info",
            ".tox",
            ".eggs",
        }

    stdlib_names = get_stdlib_names()
    results = {}

    root_path = Path(root_dir)
    if not root_path.exists():
        print(f"Error: Directory '{root_dir}' does not exist.", file=sys.stderr)
        return results

    python_files = list(root_path.rglob("*.py"))

    # Filter out excluded directories
    python_files = [f for f in python_files if not any(excl in f.parts for excl in exclude_dirs)]

    print(f"Scanning {len(python_files)} Python files in {root_dir}...")

    for filepath in python_files:
        missing = find_missing_imports(str(filepath), stdlib_names)
        if missing:
            results[str(filepath)] = missing

    return results


def print_results(results: Dict[str, List[Tuple[str, str]]], show_all: bool = False):
    """Print the analysis results in a readable format."""
    if not results:
        print("\n✅ No missing stdlib imports detected!")
        return

    total_files = len(results)
    total_missing = sum(len(missing) for missing in results.values())

    print(f"\n{'=' * 70}")
    print(f" Found {total_missing} potentially missing import(s) in {total_files} file(s)")
    print(f"{'=' * 70}\n")

    for filepath, missing in sorted(results.items()):
        rel_path = os.path.relpath(filepath)
        print(f"📄 {rel_path}")
        print(f"   {'─' * 60}")
        for name, suggestion in missing:
            print(f"   ⚠️  '{name}' used but not imported")
            print(f"   💡 Suggested: {suggestion}")
        print()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Detect potentially missing standard library imports in Python files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s .                        # Scan current directory recursively
  %(prog)s src/                     # Scan src directory
  %(prog)s . --exclude tests        # Exclude tests directory
  %(prog)s . --exclude tests,docs   # Exclude multiple directories
  %(prog)s . --show-all             # Show all files including those without issues
        """,
    )

    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Root directory to scan (default: current directory)",
    )

    parser.add_argument(
        "--exclude",
        "-e",
        default="",
        help="Comma-separated list of directories to exclude",
    )

    parser.add_argument(
        "--show-all",
        "-a",
        action="store_true",
        help="Show all files even if no missing imports detected",
    )

    args = parser.parse_args()

    # Parse exclude directories
    exclude_dirs = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".env",
        "build",
        "dist",
        "egg-info",
        ".tox",
        ".eggs",
    }
    if args.exclude:
        exclude_dirs.update(d.strip() for d in args.exclude.split(","))

    # Scan directory
    print(f"🔍 Checking for missing stdlib imports in: {args.directory}")
    results = scan_directory(args.directory, exclude_dirs)

    # Print results
    print_results(results)

    # Optionally show all files
    if args.show_all:
        print(f"\n{'=' * 70}")
        print(" All scanned files:")
        print(f"{'=' * 70}")
        root_path = Path(args.directory)
        for filepath in sorted(root_path.rglob("*.py")):
            if not any(excl in filepath.parts for excl in exclude_dirs):
                rel_path = os.path.relpath(filepath)
                status = "❌" if str(filepath) in results else "✅"
                print(f"  {status} {rel_path}")

    # Return exit code
    return 1 if results else 0


if __name__ == "__main__":
    sys.exit(main())
