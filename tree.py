#!/data/data/com.termux/files/home/.local/bin/python
"""
Tree command implementation with color output and size/directory-only flags.
Usage: python tree.py [path] [-L max_depth] [-P pattern] [-I pattern] [-d] [-s]
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from fnmatch import fnmatch
from pathlib import Path
from dh import fsz


class Colors:
    DIR = "\033[94m"
    FILE = "\033[0m"
    SIZE = "\033[90m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def get_tree_structure(
    root_path, max_depth=None, include_pattern=None, exclude_pattern=None, dirs_only=False, current_depth=0
):
    root = Path(root_path).resolve()
    if not root.exists():
        return None
    if max_depth is not None and current_depth > max_depth:
        return None
    try:
        entries = sorted(root.iterdir(), key=lambda x: (not x.is_dir(), x.name))
    except PermissionError:
        return None
    filtered_entries = []
    for entry in entries:
        if include_pattern and not fnmatch(entry.name, include_pattern):
            continue
        if exclude_pattern and fnmatch(entry.name, exclude_pattern):
            continue
        if dirs_only and not entry.is_dir():
            continue
        filtered_entries.append(entry)
    return {"path": root, "is_dir": True, "children": filtered_entries, "depth": current_depth}


def build_tree_parallel(node, max_depth=None, include_pattern=None, exclude_pattern=None, dirs_only=False):
    if node is None or (max_depth is not None and node["depth"] >= max_depth):
        return node
    children = node["children"]
    node["children"] = []

    def process_child(child):
        if child.is_dir():
            subtree = get_tree_structure(
                child, max_depth, include_pattern, exclude_pattern, dirs_only, node["depth"] + 1
            )
            if subtree:
                return build_tree_parallel(subtree, max_depth, include_pattern, exclude_pattern, dirs_only)
        return {
            "path": child,
            "is_dir": child.is_dir(),
            "children": [],
            "depth": node["depth"] + 1,
            "size": child.stat().st_size if not child.is_dir() else 0,
        }

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(process_child, child): child for child in children}
        for future in as_completed(futures):
            result = future.result()
            if result:
                node["children"].append(result)
    node["children"].sort(key=lambda x: (not x["is_dir"], x["path"].name))
    return node


def get_node_display(node, show_size=False):
    name = node["path"].name
    if node["is_dir"]:
        display = f"{Colors.DIR}{Colors.BOLD}{name}/{Colors.RESET}"
    else:
        display = f"{Colors.FILE}{name}{Colors.RESET}"
        if show_size:
            size_str = fsz(node.get("size", 0))
            display += f" {Colors.SIZE}({size_str}){Colors.RESET}"
    return display


def print_tree(node, prefix="", is_last=True, show_counts=True, show_size=False):
    if node is None:
        return 0, 0
    connector = "└── " if is_last else "├── "
    extension = "    " if is_last else "│   "
    if node["depth"] > 0:
        print(f"{prefix}{connector}{get_node_display(node, show_size)}")
    else:
        print(f"{Colors.BOLD}{node['path'].name}/{Colors.RESET}")
    dirs = 0
    files = 0
    children = node.get("children", [])
    for i, child in enumerate(children):
        is_last_child = i == len(children) - 1
        child_prefix = prefix + extension if node["depth"] > 0 else ""
        child_dirs, child_files = print_tree(child, child_prefix, is_last_child, show_counts=False, show_size=show_size)
        if child["is_dir"]:
            dirs += 1 + child_dirs
        else:
            files += 1
        files += child_files
    if node["depth"] == 0 and show_counts and (dirs > 0 or files > 0):
        print(f"\n{dirs} directories, {files} files")
    return dirs, files


def main():
    parser = argparse.ArgumentParser(description="Tree command implementation")
    parser.add_argument("path", nargs="?", default=".", help="Root path (default: current directory)")
    parser.add_argument("-L", "--max-depth", type=int, help="Maximum depth to display")
    parser.add_argument("-P", "--pattern", help="Include files matching pattern")
    parser.add_argument("-I", "--ignore-pattern", help="Exclude files matching pattern")
    parser.add_argument("-d", "--dirs-only", action="store_true", help="Show directories only")
    parser.add_argument("-s", "--size", action="store_true", help="Show file sizes")
    parser.add_argument("--no-count", action="store_true", help="Don't show file/dir counts")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = parser.parse_args()
    if args.no_color:
        Colors.DIR = ""
        Colors.FILE = ""
        Colors.SIZE = ""
        Colors.RESET = ""
        Colors.BOLD = ""
    root_path = Path(args.path)
    if not root_path.exists():
        print(f"Error: {args.path} does not exist", file=sys.stderr)
        return 1
    tree = get_tree_structure(
        root_path,
        max_depth=args.max_depth,
        include_pattern=args.pattern,
        exclude_pattern=args.ignore_pattern,
        dirs_only=args.dirs_only,
    )
    if tree:
        tree = build_tree_parallel(tree, args.max_depth, args.pattern, args.ignore_pattern, args.dirs_only)
        print_tree(tree, show_counts=not args.no_count, show_size=args.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
