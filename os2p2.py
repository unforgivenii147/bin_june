#!/data/data/com.termux/files/usr/bin/python
"""
Refactor Python files from os.path to pathlib using regex transformations.
Warning: This approach is simpler but less safe than AST-based refactoring.
"""

import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from dh import cprint, get_pyfiles


class TransformationType(Enum):
    """Type of transformation to apply."""

    SIMPLE_REPLACE = "simple"
    FUNCTION_CALL = "function"
    JOIN_OPERATOR = "join"
    CONTEXT_DEPENDENT = "context"


@dataclass
class Transformation:
    """Represents a single transformation rule."""

    pattern: str
    replacement: Callable[[re.Match], str]
    type: TransformationType
    requires_import: bool = True
    description: str = ""


class PathlibRefactorer:
    """Main refactoring engine using regex patterns."""

    def __init__(self) -> None:
        self.transformations: List[Transformation] = []
        self._setup_transformations()
        self.used_transformations: Set[str] = set()

    def _setup_transformations(self) -> None:
        """Define all transformation rules."""

        # Simple direct replacements
        simple_replacements = {
            r"\bos\.getcwd\s*\(\s*\)": "Path.cwd()",
            r"\bos\.path\.abspath\s*\(\s*([^)]+)\s*\)": "Path(\\1).resolve()",
            r"\bos\.path\.realpath\s*\(\s*([^)]+)\s*\)": "Path(\\1).resolve()",
            r"\bos\.path\.basename\s*\(\s*([^)]+)\s*\)": "Path(\\1).name",
            r"\bos\.path\.dirname\s*\(\s*([^)]+)\s*\)": "Path(\\1).parent",
            r"\bos\.path\.exists\s*\(\s*([^)]+)\s*\)": "Path(\\1).exists()",
            r"\bos\.path\.isdir\s*\(\s*([^)]+)\s*\)": "Path(\\1).is_dir()",
            r"\bos\.path\.isfile\s*\(\s*([^)]+)\s*\)": "Path(\\1).is_file()",
            r"\bos\.path\.getmtime\s*\(\s*([^)]+)\s*\)": "Path(\\1).stat().st_mtime",
            r"\bos\.path\.getsize\s*\(\s*([^)]+)\s*\)": "Path(\\1).stat().st_size",
            r"\bos\.path\.expanduser\s*\(\s*([^)]+)\s*\)": "Path(\\1).expanduser()",
            r"\bos\.path\.expandvars\s*\(\s*([^)]+)\s*\)": "Path(\\1).expandvars()",
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

        # os.path.join transformation (special handling)
        self.transformations.append(
            Transformation(
                pattern=r"\bos\.path\.join\s*\(\s*([^)]+)\s*\)",
                replacement=self._transform_join,
                type=TransformationType.JOIN_OPERATOR,
                description="Convert os.path.join to Path / operator",
            )
        )

        # os.path.split transformation
        self.transformations.append(
            Transformation(
                pattern=r"\bos\.path\.split\s*\(\s*([^)]+)\s*\)",
                replacement=lambda m: f"(str(Path({m.group(1)}).parent), Path({m.group(1)}).name)",
                type=TransformationType.FUNCTION_CALL,
                description="Convert os.path.split to tuple of parent/name",
            )
        )

        # os.path.relpath transformation
        self.transformations.append(
            Transformation(
                pattern=r"\bos\.path\.relpath\s*\(\s*([^,]+)(?:,\s*([^)]+))?\s*\)",
                replacement=lambda m: (
                    f"Path({m.group(1)}).resolve().relative_to(Path({m.group(2) if m.group(2) else '.'}).resolve())"
                ),
                type=TransformationType.FUNCTION_CALL,
                description="Convert os.path.relpath to relative_to",
            )
        )

        # File operations
        file_ops = {
            r"\bos\.remove\s*\(\s*([^)]+)\s*\)": "Path(\\1).unlink()",
            r"\bos\.unlink\s*\(\s*([^)]+)\s*\)": "Path(\\1).unlink()",
            r"\bos\.rmdir\s*\(\s*([^)]+)\s*\)": "Path(\\1).rmdir()",
            r"\bos\.mkdir\s*\(\s*([^)]+)\s*\)": "Path(\\1).mkdir(parents=False, exist_ok=False)",
            r"\bos\.stat\s*\(\s*([^)]+)\s*\)": "Path(\\1).stat()",
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

        # os.makedirs with parameter handling
        self.transformations.append(
            Transformation(
                pattern=r"\bos\.makedirs\s*\(\s*([^,]+)(?:,\s*([^)]+))?\s*\)",
                replacement=self._transform_makedirs,
                type=TransformationType.CONTEXT_DEPENDENT,
                description="Convert os.makedirs to mkdir(parents=True)",
            )
        )

        # os.rename and os.replace
        self.transformations.append(
            Transformation(
                pattern=r"\bos\.rename\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)",
                replacement=lambda m: f"Path({m.group(1)}).rename({m.group(2)})",
                type=TransformationType.FUNCTION_CALL,
                description="Convert os.rename to Path.rename",
            )
        )

        self.transformations.append(
            Transformation(
                pattern=r"\bos\.replace\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\)",
                replacement=lambda m: f"Path({m.group(1)}).replace({m.group(2)})",
                type=TransformationType.FUNCTION_CALL,
                description="Convert os.replace to Path.replace",
            )
        )

        # os.listdir transformation
        self.transformations.append(
            Transformation(
                pattern=r"\bos\.listdir\s*\(\s*([^)]*)\s*\)",
                replacement=lambda m: f"list(Path({m.group(1) if m.group(1) else '.'}).iterdir())",
                type=TransformationType.FUNCTION_CALL,
                description="Convert os.listdir to Path.iterdir()",
            )
        )

        # os.walk (complex transformation)
        self.transformations.append(
            Transformation(
                pattern=r"\bos\.walk\s*\(\s*([^)]+)\s*\)",
                replacement=self._transform_walk,
                type=TransformationType.CONTEXT_DEPENDENT,
                description="Convert os.walk to Path.rglob (limited support)",
            )
        )

    def _transform_join(self, match: re.Match) -> str:
        """Transform os.path.join arguments to Path division operator."""
        args = [arg.strip() for arg in match.group(1).split(",") if arg.strip()]
        if not args:
            return "Path()"
        if len(args) == 1:
            return f"Path({args[0]})"
        return " / ".join([f"Path({args[0]})", *args[1:]])

    def _transform_makedirs(self, match: re.Match) -> str:
        """Transform os.makedirs with proper exist_ok handling."""
        path_arg = match.group(1)
        rest_args = match.group(2) if match.group(2) else ""

        if "exist_ok" in rest_args:
            return f"Path({path_arg}).mkdir(parents=True, {rest_args})"
        else:
            return f"Path({path_arg}).mkdir(parents=True, exist_ok=True)"

    def _transform_walk(self, match: re.Match) -> str:
        """Transform os.walk to a pathlib-based generator expression."""
        path_arg = match.group(1)
        # This is a simplified transformation - os.walk is complex
        return (
            f"((str(p), [d.name for d in p.iterdir() if d.is_dir()], "
            f"[f.name for f in p.iterdir() if f.is_file()]) "
            f"for p in Path({path_arg}).rglob('*') if p.is_dir())"
        )

    def apply_transformations(self, source: str) -> Tuple[str, Set[str]]:
        """Apply all transformations to source code."""
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
        """Add 'from pathlib import Path' if needed."""
        if "from pathlib import Path" in source or "import pathlib" in source:
            return source

        lines = source.splitlines(keepends=True)

        # Find insertion point after existing imports
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
        """Refactor a single file and return results."""
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

            # Apply transformations
            refactored, applied = self.apply_transformations(original)

            # Add import if transformations were applied
            if applied:
                refactored = self.add_pathlib_import(refactored)

                # Verify syntax
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
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Refactor Python files from os/path to pathlib")
    parser.add_argument("paths", nargs="*", help="Files or directories to process")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Preview changes without writing")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")

    args = parser.parse_args()

    # Collect files
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

    # Process files
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

    # Summary
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
