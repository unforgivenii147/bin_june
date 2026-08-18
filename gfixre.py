#!/data/data/com.termux/files/home/.local/bin/python
"""Convert regex strings to raw strings safely."""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from difflib import unified_diff
from pathlib import Path


class RegexRawConverter(ast.NodeTransformer):
    def __init__(self, source_lines, source_text):
        self.source_lines = source_lines
        self.source_text = source_text
        self.modified = False
        self.changes = []

    def visit_Call(self, node):
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in ("compile", "match", "search", "sub", "findall", "split", "fullmatch")
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            const = node.args[0]
            if isinstance(const.value, str) and "\\" in const.value and not const.value.startswith("\\x"):
                if const.lineno <= len(self.source_lines):
                    line = self.source_lines[const.lineno - 1]
                    if "'" in line or '"' in line:
                        self.modified = True
                        self.changes.append({"line": const.lineno, "col": const.col_offset, "value": const.value})
        return self.generic_visit(node)


def convert_to_raw_string(source_text: str) -> str:
    lines = source_text.split("\n")
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return source_text
    converter = RegexRawConverter(lines, source_text)
    converter.visit(tree)
    if not converter.modified:
        return source_text
    for change in sorted(converter.changes, key=lambda x: x["line"], reverse=True):
        line_idx = change["line"] - 1
        line = lines[line_idx]
        quote_char = None
        for char in ['"', "'"]:
            if char in line:
                quote_char = char
                break
        if quote_char:
            old_line = line
            pattern = f"{quote_char}{change['value']}{quote_char}"
            raw_pattern = f"r{quote_char}{change['value']}{quote_char}"
            if pattern in line and not line.count("r" + quote_char):
                line = line.replace(pattern, raw_pattern, 1)
                lines[line_idx] = line
    return "\n".join(lines)


def process_file(file_path: Path, autofix: bool = False) -> dict:
    try:
        original = file_path.read_text(encoding="utf-8")
        converted = convert_to_raw_string(original)
        if original != converted:
            if autofix:
                file_path.write_text(converted, encoding="utf-8")
                return {"status": "fixed", "path": file_path}
            else:
                orig_lines = original.splitlines(keepends=True)
                conv_lines = converted.splitlines(keepends=True)
                diff = list(unified_diff(orig_lines, conv_lines, fromfile=str(file_path), tofile=str(file_path)))
                return {"status": "diff", "path": file_path, "diff": diff}
        return {"status": "unchanged", "path": file_path}
    except (SyntaxError, UnicodeDecodeError) as e:
        return {"status": "error", "path": file_path, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Convert regex strings to raw strings")
    parser.add_argument("-a", "--autofix", action="store_true", help="Apply changes")
    args = parser.parse_args()
    py_files = [f for f in Path(".").rglob("*.py") if f.is_file() and f.name != Path(__file__).name]
    results = {"fixed": 0, "diff": 0, "unchanged": 0, "error": 0}
    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks = [executor.submit(process_file, f, args.autofix) for f in py_files]
        for future in tasks:
            result = future.result()
            status = result["status"]
            results[status] += 1
            if status == "fixed":
                print(f"✅ {result['path'].name}")
            elif status == "diff":
                print(f"⚠️  {result['path'].name}")
                print("".join(result["diff"]))
            elif status == "error":
                print(f"❌ {result['path'].name}: {result['error']}")
    print(
        f"\n📊 Fixed: {results['fixed']}, Changed: {results['diff']}, Unchanged: {results['unchanged']}, Errors: {results['error']}"
    )
    if results["diff"] > 0 and not args.autofix:
        print("\n💡 Run with -a/--autofix to apply changes")


if __name__ == "__main__":
    main()
