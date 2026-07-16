#!/data/data/com.termux/files/usr/bin/env python

import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from os import scandir as os_scandir
from pathlib import Path
from typing import Callable, Dict, List, Set, Tuple

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

ATTRIBUTES = {
    "bold": 1,
    "dark": 2,
    "italic": 3,
    "underline": 4,
    "blink": 5,
    "reverse": 7,
    "concealed": 8,
    "strike": 9,
}

HIGHLIGHTS = {
    "on_black": 40,
    "on_grey": 40,
    "on_red": 41,
    "on_green": 42,
    "on_yellow": 43,
    "on_blue": 44,
    "on_magenta": 45,
    "on_cyan": 46,
    "on_light_grey": 47,
    "on_dark_grey": 100,
    "on_light_red": 101,
    "on_light_green": 102,
    "on_light_yellow": 103,
    "on_light_blue": 104,
    "on_light_magenta": 105,
    "on_light_cyan": 106,
    "on_white": 107,
}

COLORS = {
    "black": 30,
    "grey": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "light_grey": 37,
    "dark_grey": 90,
    "light_red": 91,
    "light_green": 92,
    "light_yellow": 93,
    "light_blue": 94,
    "light_magenta": 95,
    "light_cyan": 96,
    "white": 97,
}

RESET = "\x1b[0m"


def can_colorize(*, no_color=None, force_color=None):
    if no_color is not None and no_color:
        return False
    if force_color is not None and force_color:
        return True
    if os.environ.get("ANSI_COLORS_DISABLED"):
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(sys.stdout, "fileno"):
        return False
    try:
        return os.isatty(sys.stdout.fileno())
    except OSError:
        return sys.stdout.isatty()


def colored(text, color=None, on_color=None, attrs=None, *, no_color=None, force_color=None):
    result = str(text)
    if not can_colorize(no_color=no_color, force_color=force_color):
        return result
    fmt_str = "\x1b[%dm%s"
    rgb_fore_fmt_str = "\x1b[38;2;%d;%d;%dm%s"
    rgb_back_fmt_str = "\x1b[48;2;%d;%d;%dm%s"
    if color is not None:
        if isinstance(color, str):
            result = fmt_str % (COLORS[color], result)
        elif isinstance(color, tuple):
            result = rgb_fore_fmt_str % (color[0], color[1], color[2], result)
    if on_color is not None:
        if isinstance(on_color, str):
            result = fmt_str % (HIGHLIGHTS[on_color], result)
        elif isinstance(on_color, tuple):
            result = rgb_back_fmt_str % (on_color[0], on_color[1], on_color[2], result)
    if attrs is not None:
        for attr in attrs:
            result = fmt_str % (ATTRIBUTES[attr], result)
    result += RESET
    return result


def cprint(text, color=None, on_color=None, attrs=None, *, no_color=None, force_color=None, **kwargs):
    print(colored(text, color, on_color, attrs, no_color=no_color, force_color=force_color), **kwargs)


def is_python_file(path: str | Path) -> bool:
    from ast import parse as ast_parse

    path = Path(path)
    if is_binary(path):
        return False
    if not path.stat().st_size:
        return False
    if path.is_file() and path.suffix == ".py":
        return True
    if not path.suffix:
        content = path.read_text(encoding="utf-8")
        if not content:
            return False
        if content.startswith("#!") and "python" in content[:100]:
            return True
        try:
            _ = ast_parse(content)
            return True
        except:
            return False
    return False


def is_binary(path: Path | str) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


def get_pyfiles(path: str | Path) -> list[Path]:
    path = Path(path)
    if path.is_file():
        if path.suffix == ".py":
            return [path]
        if not path.suffix and not path.name.startswith(".") and is_python_file(path):
            return [path]
        return []

    if not path.is_dir():
        return []

    pyfiles = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        p = Path(entry.path)
                        if p.suffix == ".py":
                            pyfiles.append(p)
                        elif not p.suffix and not p.name.startswith(".") and is_python_file(p):
                            pyfiles.append(p)
        except (PermissionError, OSError):
            continue

    return sorted(pyfiles)


"""
Refactor Python files from os.path to pathlib using regex transformations.
Warning: This approach is simpler but less safe than AST-based refactoring.
"""


class TransformationType(Enum):
    SIMPLE_REPLACE = "simple"
    FUNCTION_CALL = "function"
    JOIN_OPERATOR = "join"
    CONTEXT_DEPENDENT = "context"


@dataclass
class Transformation:
    pattern: str
    replacement: Callable[[re.Match], str]
    type: TransformationType
    requires_import: bool = True
    description: str = ""


class PathlibRefactorer:
    def __init__(self) -> None:
        self.transformations: List[Transformation] = []
        self._setup_transformations()
        self.used_transformations: Set[str] = set()

    def _setup_transformations(self) -> None:
        simple_replacements = {
            "\\bos\\.getcwd\\s*\\(\\s*\\)": "Path.cwd()",
            "\\bos\\.path\\.abspath\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).resolve()",
            "\\bos\\.path\\.realpath\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).resolve()",
            "\\bos\\.path\\.basename\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).name",
            "\\bos\\.path\\.dirname\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).parent",
            "\\bos\\.path\\.exists\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).exists()",
            "\\bos\\.path\\.isdir\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).is_dir()",
            "\\bos\\.path\\.isfile\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).is_file()",
            "\\bos\\.path\\.getmtime\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).stat().st_mtime",
            "\\bos\\.path\\.getsize\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).stat().st_size",
            "\\bos\\.path\\.expanduser\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).expanduser()",
            "\\bos\\.path\\.expandvars\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).expandvars()",
        }
        for pattern, replacement in simple_replacements.items():
            self.transformations.append(
                Transformation(
                    pattern=pattern,
                    replacement=lambda m, r=replacement: re.sub(r"\\\\(\\d+)", lambda x: m.group(int(x.group(1))), r),
                    type=TransformationType.SIMPLE_REPLACE,
                    description=f"Replace {pattern}",
                )
            )
        self.transformations.append(
            Transformation(
                pattern="\\bos\\.path\\.join\\s*\\(\\s*([^)]+)\\s*\\)",
                replacement=self._transform_join,
                type=TransformationType.JOIN_OPERATOR,
                description="Convert os.path.join to Path / operator",
            )
        )
        self.transformations.append(
            Transformation(
                pattern="\\bos\\.path\\.split\\s*\\(\\s*([^)]+)\\s*\\)",
                replacement=lambda m: f"(str(Path({m.group(1)}).parent), Path({m.group(1)}).name)",
                type=TransformationType.FUNCTION_CALL,
                description="Convert os.path.split to tuple of parent/name",
            )
        )
        self.transformations.append(
            Transformation(
                pattern="\\bos\\.path\\.relpath\\s*\\(\\s*([^,]+)(?:,\\s*([^)]+))?\\s*\\)",
                replacement=lambda m: (
                    f"Path({m.group(1)}).resolve().relative_to(Path({m.group(2) if m.group(2) else '.'}).resolve())"
                ),
                type=TransformationType.FUNCTION_CALL,
                description="Convert os.path.relpath to relative_to",
            )
        )
        file_ops = {
            "\\bos\\.remove\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).unlink()",
            "\\bos\\.unlink\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).unlink()",
            "\\bos\\.rmdir\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).rmdir()",
            "\\bos\\.mkdir\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).mkdir(parents=False, exist_ok=False)",
            "\\bos\\.stat\\s*\\(\\s*([^)]+)\\s*\\)": "Path(\\1).stat()",
        }
        for pattern, replacement in file_ops.items():
            self.transformations.append(
                Transformation(
                    pattern=pattern,
                    replacement=lambda m, r=replacement: re.sub(r"\\\\(\\d+)", lambda x: m.group(int(x.group(1))), r),
                    type=TransformationType.SIMPLE_REPLACE,
                    description=f"Replace {pattern}",
                )
            )
        self.transformations.append(
            Transformation(
                pattern="\\bos\\.makedirs\\s*\\(\\s*([^,]+)(?:,\\s*([^)]+))?\\s*\\)",
                replacement=self._transform_makedirs,
                type=TransformationType.CONTEXT_DEPENDENT,
                description="Convert os.makedirs to mkdir(parents=True)",
            )
        )
        self.transformations.append(
            Transformation(
                pattern="\\bos\\.rename\\s*\\(\\s*([^,]+)\\s*,\\s*([^)]+)\\s*\\)",
                replacement=lambda m: f"Path({m.group(1)}).rename({m.group(2)})",
                type=TransformationType.FUNCTION_CALL,
                description="Convert os.rename to Path.rename",
            )
        )
        self.transformations.append(
            Transformation(
                pattern="\\bos\\.replace\\s*\\(\\s*([^,]+)\\s*,\\s*([^)]+)\\s*\\)",
                replacement=lambda m: f"Path({m.group(1)}).replace({m.group(2)})",
                type=TransformationType.FUNCTION_CALL,
                description="Convert os.replace to Path.replace",
            )
        )
        self.transformations.append(
            Transformation(
                pattern="\\bos\\.listdir\\s*\\(\\s*([^)]*)\\s*\\)",
                replacement=lambda m: f"list(Path({m.group(1) if m.group(1) else '.'}).iterdir())",
                type=TransformationType.FUNCTION_CALL,
                description="Convert os.listdir to Path.iterdir()",
            )
        )
        self.transformations.append(
            Transformation(
                pattern="\\bos\\.walk\\s*\\(\\s*([^)]+)\\s*\\)",
                replacement=self._transform_walk,
                type=TransformationType.CONTEXT_DEPENDENT,
                description="Convert os.walk to Path.rglob (limited support)",
            )
        )

    def _transform_join(self, match: re.Match) -> str:
        args = [arg.strip() for arg in match.group(1).split(",") if arg.strip()]
        if not args:
            return "Path()"
        if len(args) == 1:
            return f"Path({args[0]})"
        return " / ".join([f"Path({args[0]})", *args[1:]])

    def _transform_makedirs(self, match: re.Match) -> str:
        path_arg = match.group(1)
        rest_args = match.group(2) if match.group(2) else ""
        if "exist_ok" in rest_args:
            return f"Path({path_arg}).mkdir(parents=True, {rest_args})"
        else:
            return f"Path({path_arg}).mkdir(parents=True, exist_ok=True)"

    def _transform_walk(self, match: re.Match) -> str:
        path_arg = match.group(1)
        return f"((str(p), [d.name for d in p.iterdir() if d.is_dir()], [f.name for f in p.iterdir() if f.is_file()]) for p in Path({path_arg}).rglob('*') if p.is_dir())"

    def apply_transformations(self, source: str) -> Tuple[str, Set[str]]:
        result = source
        applied = set()
        for trans in self.transformations:
            try:
                new_result = re.sub(trans.pattern, trans.replacement, result)
                if new_result != result:
                    applied.add(trans.description)
                    result = new_result
            except Exception as e:
                cprint(f"  ⚠️ Transformation failed: {trans.description} - {e}", "yellow")
        return result, applied

    def add_pathlib_import(self, source: str) -> str:
        if "from pathlib import Path" in source or "import pathlib" in source:
            return source
        lines = source.splitlines(keepends=True)
        insert_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                insert_idx = i + 1
            elif stripped and not stripped.startswith("#"):
                break
        lines.insert(insert_idx, "from pathlib import Path\n")
        return "".join(lines)

    def refactor_file(self, file_path: Path, dry_run: bool = False, create_backup: bool = True) -> Dict:
        result = {
            "path": file_path,
            "success": False,
            "changed": False,
            "transformations_applied": set(),
            "error": None,
            "backup_path": None,
        }
        try:
            original = file_path.read_text(encoding="utf-8")
            refactored, applied = self.apply_transformations(original)
            if applied:
                refactored = self.add_pathlib_import(refactored)
                try:
                    compile(refactored, file_path.name, "exec")
                    result["success"] = True
                    result["changed"] = True
                    result["transformations_applied"] = applied
                    if not dry_run:
                        if create_backup:
                            backup = file_path.with_suffix(file_path.suffix + ".bak")
                            backup.write_text(original, encoding="utf-8")
                            result["backup_path"] = backup
                        file_path.write_text(refactored, encoding="utf-8")
                except SyntaxError as e:
                    result["error"] = f"Syntax error after refactoring: {e}"
                    result["success"] = False
            else:
                result["success"] = True
                result["changed"] = False
        except Exception as e:
            result["error"] = str(e)
            result["success"] = False
        return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Refactor Python files from os/path to pathlib")
    parser.add_argument("paths", nargs="*", help="Files or directories to process")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Preview changes without writing")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()
    if args.paths:
        files = []
        for path_str in args.paths:
            p = Path(path_str)
            if p.is_file() and p.suffix == ".py":
                files.append(p)
            elif p.is_dir():
                files.extend(get_pyfiles(p))
    else:
        files = get_pyfiles(Path.cwd())
    if not files:
        cprint("No Python files found to process.", "yellow")
        return 0
    cprint(f"\n📁 Found {len(files)} Python files to process", "cyan")
    if args.dry_run:
        cprint("🔍 DRY RUN MODE - No files will be modified\n", "yellow")
    refactorer = PathlibRefactorer()
    results = []
    for file_path in files:
        if args.verbose:
            cprint(f"\nProcessing: {file_path.name}", "white")
        result = refactorer.refactor_file(file_path, dry_run=args.dry_run, create_backup=not args.no_backup)
        results.append(result)
        if result["error"]:
            cprint(f"  ❌ Error: {result['error']}", "red")
        elif result["changed"]:
            cprint(f"  ✅ Refactored: {file_path.name}", "green")
            if args.verbose:
                for trans in result["transformations_applied"]:
                    cprint(f"     • {trans}", "cyan", attrs=["dark"])
            if result["backup_path"]:
                cprint(f"     📦 Backup: {result['backup_path'].name}", "white", attrs=["dark"])
        elif args.verbose:
            cprint(f"  ⏭️  No changes needed", "white", attrs=["dark"])
    changed = [r for r in results if r["changed"]]
    errors = [r for r in results if r["error"]]
    cprint("\n" + "=" * 50, "cyan")
    cprint("📊 SUMMARY", "cyan", attrs=["bold"])
    cprint(f"  Total files: {len(files)}", "white")
    cprint(f"  Modified: {len(changed)}", "green" if changed else "white")
    cprint(f"  Errors: {len(errors)}", "red" if errors else "white")
    if args.dry_run and changed:
        cprint("\n⚠️  This was a dry run. Run without --dry-run to apply changes.", "yellow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
