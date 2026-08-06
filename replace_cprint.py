#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import ast
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from dh import get_pyfiles

CODE_BLOCK = r"""
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
"""
BLOCK_LINES = [line.rstrip() for line in CODE_BLOCK.strip("\n").splitlines()]


def find_block_range(lines: list[str]) -> tuple[int, int] | None:
    normalized = [line.rstrip("\n").rstrip() for line in lines]
    n, m = len(normalized), len(BLOCK_LINES)
    for i in range(n - m + 1):
        if normalized[i : i + m] == BLOCK_LINES:
            return (i, i + m)
    return None


def already_imports_cprint(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "dh":
            if any(alias.name == "cprint" for alias in node.names):
                return True
        if isinstance(node, ast.Import) and any(alias.name == "cprint" for alias in node.names):
            return True
    return False


def last_import_end_line(tree: ast.Module) -> int:
    last_end = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last_end = max(last_end, node.end_lineno)
        else:
            break
    return last_end


def process_file(path: Path):
    path = Path(path)
    if path.resolve() == Path(__file__).resolve():
        return
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        print(f"Skipping {path}: {e}")
        return
    lines = content.splitlines(keepends=True)
    match = find_block_range(lines)
    if match is None:
        return
    start, end = match
    # trim a single blank line immediately before/after the block, if present,
    # so we don't leave double blank lines behind
    if start > 0 and lines[start - 1].strip() == "":
        start -= 1
    if end < len(lines) and lines[end].strip() == "":
        end += 1
    del lines[start:end]
    new_content = "".join(lines)
    try:
        tree = ast.parse(new_content)
    except SyntaxError as e:
        print(f"Skipping write for {path} (would break syntax): {e}")
        return
    if already_imports_cprint(tree):
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            print(f"Removed block: {path} (cprint already imported)")
        return
    import_line = "from dh import cprint\n"
    body_lines = new_content.splitlines(keepends=True)
    last_end = last_import_end_line(tree)
    if last_end > 0:
        insert_idx = last_end
    else:
        insert_idx = 1 if body_lines and body_lines[0].startswith("#!") else 0
    body_lines.insert(insert_idx, import_line)
    final_content = "".join(body_lines)
    path.write_text(final_content, encoding="utf-8")
    print(f"Removed block and added import: {path}")


def main():
    cwd = Path.cwd()
    args = sys.argv[1:]
    py_files = [Path(p) for p in args] if args else get_pyfiles(cwd)
    with ThreadPoolExecutor(8) as executor:
        executor.map(process_file, py_files)


if __name__ == "__main__":
    main()
