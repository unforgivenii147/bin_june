#!/data/data/com.termux/files/usr/bin/env python
import os
import sys
import termios
import tty
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# --- Core Data Structures ---


@dataclass
class FSItem:
    path: Path
    name: str
    is_dir: bool
    size: int = 0
    children: List["FSItem"] = field(default_factory=list)
    parent: "FSItem" = None
    flag: str = " "  # 'e' for empty, '!' for error, '@' for symlink


# --- Parallel Scanning Engine ---


class DiskAnalyzer:
    def __init__(self, root_path: Path):
        self.root_path = root_path.resolve()

    def scan(self) -> FSItem:
        root_item = FSItem(path=self.root_path, name=str(self.root_path), is_dir=True)
        try:
            top_level = list(self.root_path.iterdir())
        except Exception:
            root_item.flag = "!"
            return root_item

        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._scan_recursive, p): p for p in top_level}
            for future in as_completed(futures):
                child = future.result()
                child.parent = root_item
                root_item.children.append(child)
                root_item.size += child.size

        root_item.children.sort(key=lambda x: x.size, reverse=True)
        return root_item

    def _scan_recursive(self, path: Path) -> FSItem:
        if path.is_symlink():
            return FSItem(path=path, name=path.name, is_dir=False, size=0, flag="@")
        if path.is_file():
            try:
                return FSItem(path=path, name=path.name, is_dir=False, size=path.stat().st_size)
            except Exception:
                return FSItem(path=path, name=path.name, is_dir=False, size=0, flag="!")

        dir_item = FSItem(path=path, name=path.name, is_dir=True)
        try:
            for child in path.iterdir():
                child_item = self._scan_recursive(child)
                child_item.parent = dir_item
                dir_item.children.append(child_item)
                dir_item.size += child_item.size
        except Exception:
            dir_item.flag = "!"

        if not dir_item.children and dir_item.flag == " ":
            dir_item.flag = "e"

        dir_item.children.sort(key=lambda x: x.size, reverse=True)
        return dir_item


# --- Formatting Utilities ---


def format_size(num_bytes: int) -> str:
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if num_bytes < 1024.0:
            return f"{num_bytes:5.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:5.1f} PiB"


def get_progress_bar(item_size: int, max_size: int) -> str:
    if max_size == 0:
        return "[          ]"
    ratio = item_size / max_size
    filled = int(ratio * 10)
    return f"[{'#' * filled}{' ' * (10 - filled)}]"


# --- Input & Screen Controls ---


def get_key() -> str:
    """Reads raw terminal keypress without hitting Enter."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":  # Handle multi-byte control characters (arrow keys)
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def clear_screen():
    sys.stdout.write("\x1b[2J\x1b[H")  # ANSI sequence to clear terminal and home cursor
    sys.stdout.flush()


# --- Core UI Loop ---


def draw_interface(current_node: FSItem, selected_idx: int):
    # ANSI escape configurations for styling
    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"
    REVERSE = "\x1b[7m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    MAGENTA = "\x1b[35m"
    CYAN = "\x1b[36m"

    lines = []
    lines.append(f"{BOLD}Directory: {current_node.path}{RESET}\n")

    max_size = max([c.size for c in current_node.children], default=1)

    for idx, item in enumerate(current_node.children):
        size_str = format_size(item.size)
        bar_str = get_progress_bar(item.size, max_size)
        flag_str = f"[{item.flag}]" if item.flag != " " else "   "
        name_str = f"{item.name}/" if item.is_dir else item.name

        if idx == selected_idx:
            # Highlight current selection
            line = f"{REVERSE}{size_str}  {bar_str}  {flag_str}  {name_str}{RESET}"
        else:
            line = f"{GREEN}{size_str}{RESET}  {YELLOW}{bar_str}{RESET}  {MAGENTA}{flag_str}{RESET}  {CYAN if item.is_dir else RESET}{name_str}{RESET}"

        lines.append(line)

    clear_screen()
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()


def main():
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    if not target_dir.is_dir():
        print(f"Error: {target_dir} is not a valid directory.")
        sys.exit(1)

    print(f"Scanning {target_dir.resolve()} targets efficiently...")
    analyzer = DiskAnalyzer(target_dir)
    current_node = analyzer.scan()
    selected_idx = 0

    while True:
        draw_interface(current_node, selected_idx)
        key = get_key()

        # Navigation Engine mapping
        if key in ("q", "\x03"):  # 'q' key or Ctrl+C
            clear_screen()
            break
        elif key in ("\x1b[A", "k"):  # Up Arrow or 'k'
            if selected_idx > 0:
                selected_idx -= 1
        elif key in ("\x1b[B", "j"):  # Down Arrow or 'j'
            if selected_idx < len(current_node.children) - 1:
                selected_idx += 1
        elif key in ("\x1b[C", "l", "\r"):  # Right Arrow, 'l', or Enter
            if current_node.children:
                target = current_node.children[selected_idx]
                if target.is_dir and target.children:
                    current_node = target
                    selected_idx = 0
        elif key in ("\x1b[D", "h", "\x1b"):  # Left Arrow, 'h', or Escape
            if current_node.parent:
                old_node = current_node
                current_node = current_node.parent
                try:
                    selected_idx = current_node.children.index(old_node)
                except ValueError:
                    selected_idx = 0


if __name__ == "__main__":
    main()
