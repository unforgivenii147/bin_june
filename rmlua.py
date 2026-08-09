#!/data/data/com.termux/files/home/.local/bin/python
"""Remove comments from Lua files using tree-sitter."""

import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from tree_sitter import Language, Parser


def setup_parser():
    """Initialize tree-sitter parser for Lua."""
    lua_lang = Language("./build/my-languages.so", "lua")
    parser = Parser()
    parser.set_language(lua_lang)
    return parser


def get_lua_files(paths):
    """Get all Lua files from given paths."""
    lua_files = []

    if not paths:
        paths = [Path.cwd()]

    for path in paths:
        p = Path(path)
        if p.is_file() and p.suffix == ".lua":
            lua_files.append(p)
        elif p.is_dir():
            lua_files.extend(p.rglob("*.lua"))

    return list(set(lua_files))


def remove_comments_from_file(file_path):
    """Remove comments from a Lua file and return stats."""
    try:
        parser = setup_parser()
        content = file_path.read_text(encoding="utf-8")
        tree = parser.parse(content.encode("utf-8"))

        lines = content.split("\n")
        comment_count = 0
        comments_to_remove = []

        def traverse(node):
            nonlocal comment_count
            if node.type == "comment":
                comment_count += 1
                comments_to_remove.append((node.start_point[0], node.end_point[0], node.start_byte, node.end_byte))

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)

        if not comments_to_remove:
            return file_path, 0

        comments_to_remove.sort(key=lambda x: x[2], reverse=True)
        content_bytes = content.encode("utf-8")

        for start_byte, end_byte in [(c[2], c[3]) for c in comments_to_remove]:
            content_bytes = content_bytes[:start_byte] + content_bytes[end_byte:]

        result_content = content_bytes.decode("utf-8")
        result_lines = result_content.split("\n")

        cleaned_lines = []
        for line in result_lines:
            stripped = line.rstrip()
            if stripped and not stripped.startswith("--"):
                cleaned_lines.append(line)
            elif not stripped:
                cleaned_lines.append(line)
            elif stripped.startswith("--"):
                continue
            else:
                inline_parts = line.split("--", 1)
                if inline_parts[0].strip():
                    cleaned_lines.append(inline_parts[0].rstrip())

        final_content = "\n".join(cleaned_lines)
        file_path.write_text(final_content, encoding="utf-8")

        return file_path, comment_count

    except Exception as e:
        return file_path, f"Error: {e}"


def main():
    paths = sys.argv[1:] if len(sys.argv) > 1 else []
    lua_files = get_lua_files(paths)

    if not lua_files:
        print("No Lua files found.")
        return

    print(f"Processing {len(lua_files)} file(s)...\n")

    with ProcessPoolExecutor(max_workers=None) as executor:
        futures = {executor.submit(remove_comments_from_file, f): f for f in lua_files}

        for future in as_completed(futures):
            file_path, result = future.result()
            rel_path = file_path.relative_to(Path.cwd())

            if isinstance(result, int):
                print(f"{rel_path}: {result} comment(s) removed")
            else:
                print(f"{rel_path}: {result}")


if __name__ == "__main__":
    main()
