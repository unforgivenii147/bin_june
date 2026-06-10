#!/data/data/com.termux/files/usr/bin/python

import argparse
import os
import subprocess
import sys
from pathlib import Path

try:
    from tree_sitter import Language, Parser
except ImportError:
    print("Error: tree-sitter not installed. Install with: pip install tree-sitter")
    sys.exit(1)


class BashCommentRemover:
    def __init__(self) -> None:
        self.parser = self._setup_parser()
        if not self.parser:
            print("Error: Failed to setup tree-sitter bash grammar")
            sys.exit(1)

    def _setup_parser(self) -> Parser | None:
        try:
            try:
                from tree_sitter_bash import language

                bash_language = Language(language())
            except ImportError:
                print("Tree-sitter bash grammar not found. Attempting to install...")
                import subprocess
                import tempfile

                with tempfile.TemporaryDirectory() as tmpdir:
                    subprocess.run(
                        ["npm", "install", "tree-sitter-cli", "tree-sitter-bash"],
                        cwd=tmpdir,
                        capture_output=True,
                        check=False,
                    )
                    build_result = subprocess.run(
                        ["npx", "tree-sitter", "build", "node_modules/tree-sitter-bash"],
                        cwd=tmpdir,
                        capture_output=True,
                        text=True,
                    )
                    if build_result.returncode != 0:
                        print(f"Failed to build bash grammar: {build_result.stderr}")
                        return None
                    so_file = Path(tmpdir) / "tree-sitter-bash.so"
                    if so_file.exists():
                        bash_language = Language(str(so_file), "bash")
                    else:
                        print("Could not find built grammar file")
                        return None
            parser = Parser()
            parser.set_language(bash_language)
            return parser
        except Exception as e:
            print(f"Error setting up parser: {e}")
            return None

    def remove_comments(self, content: str) -> tuple[str, bool]:
        try:
            tree = self.parser.parse(bytes(content, "utf8"))
            root_node = tree.root_node
            comments_to_remove = []

            def collect_comments(node):
                if node.type == "comment":
                    comments_to_remove.append(node)
                for child in node.children:
                    collect_comments(child)

            collect_comments(root_node)
            if not comments_to_remove:
                return (content, False)
            lines = content.splitlines(True)
            modified_lines = lines.copy()
            comments_to_remove.sort(key=lambda n: n.start_point[0], reverse=True)
            for comment in comments_to_remove:
                start_line, start_col = comment.start_point
                end_line, end_col = comment.end_point
                if start_line == end_line:
                    line = modified_lines[start_line]
                    modified_lines[start_line] = line[:start_col] + line[end_col:]
                else:
                    modified_lines[start_line] = modified_lines[start_line][:start_col]
                    for line_num in range(start_line + 1, end_line):
                        modified_lines[end_line] = modified_lines[end_line][end_col:]
            modified_content = "".join(modified_lines)
            import re

            modified_content = re.sub("\\n\\s*\\n\\s*\\n", "\\n\\n", modified_content)
            return (modified_content, True)
        except Exception as e:
            print(f"Error processing content: {e}")
            return (content, False)

    def validate_syntax(self, content: str) -> bool:
        try:
            tree = self.parser.parse(bytes(content, "utf8"))
            if tree.root_node.has_error:
                return False
        except:
            pass
        try:
            result = subprocess.run(["shfmt", "-f"], input=content, text=True, capture_output=True, check=False)
            if result.returncode != 0:
                result = subprocess.run(["bash", "-n"], input=content, text=True, capture_output=True, check=False)
                return result.returncode == 0
            return True
        except FileNotFoundError:
            try:
                tree = self.parser.parse(bytes(content, "utf8"))
                return not tree.root_node.has_error
            except:
                return False

    def process_file(self, filepath: Path, dry_run: bool = False) -> tuple[bool, int, int]:
        path = Path(path)
        try:
            original_content = Path(filepath).read_text(encoding="utf-8")
            original_size = len(original_content.encode("utf-8"))
            if (
                filepath.suffix not in {".sh", ".bash"}
                and (not original_content.startswith("#!/bin/bash"))
                and (not original_content.startswith("#!/usr/bin/env bash"))
            ):
                return (True, original_size, original_size)
            modified_content, was_modified = self.remove_comments(original_content)
            if not was_modified:
                return (True, original_size, original_size)
            if not self.validate_syntax(modified_content):
                print(f"  ⚠️  Syntax error detected in {filepath}, skipping")
                return (False, original_size, original_size)
            new_size = len(modified_content.encode("utf-8"))
            if not dry_run:
                Path(filepath).write_text(modified_content, encoding="utf-8")
                print(f"  ✓ Processed: {filepath} ({original_size} -> {new_size} bytes)")
            else:
                print(f"  ✓ Would process: {filepath} ({original_size} -> {new_size} bytes)")
            return (True, original_size, new_size)
        except Exception as e:
            print(f"  ✗ Error processing {filepath}: {e}")
            return (False, 0, 0)

    def process_path(self, path: Path, recursive: bool = False, dry_run: bool = False) -> tuple[int, int, int]:
        success_count = 0
        total_original = 0
        total_new = 0
        if path.is_file():
            success, orig, new = self.process_file(path, dry_run)
            if success:
                success_count += 1
                total_original += orig
                total_new += new
        elif path.is_dir() and recursive:
            bash_files = []
            for root, _, files in os.walk(path):
                for file in files:
                    filepath = Path(root) / file
                    if filepath.suffix in {".sh", ".bash"}:
                        bash_files.append(filepath)
                    else:
                        try:
                            with Path(filepath).open(encoding="utf-8") as f:
                                first_line = f.readline()
                                if first_line.startswith(("#!/bin/bash", "#!/usr/bin/env bash")):
                                    bash_files.append(filepath)
                        except:
                            continue
            for filepath in bash_files:
                success, orig, new = self.process_file(filepath, dry_run)
                if success:
                    success_count += 1
                    total_original += orig
                    total_new += new
        elif path.is_dir() and (not recursive):
            print(f"Error: {path} is a directory. Use --recursive to process directories.")
        return (success_count, total_original, total_new)


def main():
    parser = argparse.ArgumentParser(description="Remove comments from bash files using tree-sitter")
    parser.add_argument(
        "files", nargs="*", help="Files to process. If none given, process current directory recursively"
    )
    parser.add_argument("-r", "--recursive", action="store_true", help="Process directories recursively")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--no-validate", action="store_true", help="Skip syntax validation (not recommended)")
    args = parser.parse_args()
    remover = BashCommentRemover()
    paths_to_process = []
    if args.files:
        for file_arg in args.files:
            path = Path(file_arg)
            if not path.exists():
                print(f"Warning: {path} does not exist, skipping")
                continue
            paths_to_process.append(path)
    else:
        paths_to_process.append(Path.cwd())
        args.recursive = True
    total_success = 0
    total_original = 0
    total_new = 0
    for path in paths_to_process:
        if path.is_file() or (path.is_dir() and args.recursive):
            print(f"\nProcessing: {path}")
            success, orig, new = remover.process_path(path, args.recursive, args.dry_run)
            total_success += success
            total_original += orig
            total_new += new
    if total_success > 0:
        print(f"\n{'=' * 50}")
        print("Summary:")
        print(f"  Files processed successfully: {total_success}")
        print(f"  Original total size: {total_original} bytes ({total_original / 1024:.2f} KB)")
        print(f"  New total size: {total_new} bytes ({total_new / 1024:.2f} KB)")
        print(f"  Size reduction: {total_original - total_new} bytes ({(total_original - total_new) / 1024:.2f} KB)")
        print(f"  Reduction percentage: {(total_original - total_new) / total_original * 100:.1f}%")
    else:
        print("\nNo files were processed successfully.")


if __name__ == "__main__":
    main()
