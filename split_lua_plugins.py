#!/data/data/com.termux/files/home/.local/bin/python
"""Script to split a lazy.nvim plugin configuration file into individual files."""
import re
import sys
from pathlib import Path
def split_lua_plugins(input_path, move=False):
    input_file = Path(input_path)
    content = input_file.read_text()
    start_idx = content.find("{")
    end_idx = content.rfind("}")
    if start_idx == -1 or end_idx == -1:
        return
    inner = content[start_idx + 1 : end_idx].strip()
    blocks = []
    current = []
    depth = 0
    for char in inner:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        current.append(char)
        if depth == 0 and char == "}":
            block_text = "".join(current).strip()
            if block_text.endswith(","):
                block_text = block_text[:-1].strip()
            blocks.append(block_text)
            current = []
        elif depth == 0 and current and current[-1] == ",":
            current = []
    for block in blocks:
        match = re.search(r'["\']([^"\']+)["\']', block)
        if not match:
            continue
        raw_name = match.group(1)
        plugin_name = raw_name.split("/")[-1].removesuffix(".nvim")
        if plugin_name == "nvim-lspconfig":
            plugin_name = "nvim-lsp-config"
        target = Path(f"{plugin_name}.lua")
        if target.exists():
            target.rename(target.with_suffix(target.suffix + ".orig"))
        target.write_text(f"return {block}")
    if move and blocks:
        input_file.write_text("return {\n}")
if __name__ == "__main__":
    move = False
    input_path = None
    for arg in sys.argv[1:]:
        if arg == "-m":
            move = True
        else:
            input_path = arg
    if not input_path:
        sys.exit(1)
    split_lua_plugins(input_path, move)
