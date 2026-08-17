#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import multiprocessing as mp
import re
import sys
from pathlib import Path
from dh import get_nobinary
CHUNK_SIZE = 1024 * 1024
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
        nontext = sum((1 for b in chunk if b not in text_chars))
        return nontext / len(chunk) > 0.3
    except Exception:
        return True
HTML_ENTITIES = {
    "&lt;": "<",
    "&gt;": ">",
    "&amp;": "&",
    "&quot;": '"',
    "&apos;": "'",
    "&nbsp;": " ",
    "&copy;": "©",
    "&reg;": "®",
    "&euro;": "€",
    "&pound;": "£",
    "&yen;": "¥",
    "&dollar;": "$",
    "&cent;": "¢",
    "&sect;": "§",
    "&dagger;": "†",
    "&Dagger;": "‡",
    "&hellip;": "…",
    "&mdash;": "—",
    "&ndash;": "–",
    "&lsquo;": "'",
    "&rsquo;": "'",
    "&ldquo;": '"',
    "&rdquo;": '"',
}
ENTITY_PATTERN = re.compile("|".join((re.escape(k) for k in HTML_ENTITIES)))
def replace_entities(text: str) -> str:
    def replacer(match) -> str:
        return HTML_ENTITIES[match.group(0)]
    return ENTITY_PATTERN.sub(replacer, text)
def process_file(filepath: Path) -> tuple[Path, bool, str]:
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        new_content = replace_entities(content)
        changed = content != new_content
        if changed:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
        return (filepath, changed, "")
    except Exception as e:
        return (filepath, False, str(e))
def main() -> None:
    cwd = Path.cwd()
    args = sys.argv[1:]
    files = [Path(p) for p in args] if args else get_nobinary(cwd)
    changed_files = []
    error_files = []
    with mp.Pool(processes=8) as pool:
        results = pool.map(process_file, files)
        for filepath, changed, error in results:
            if error:
                error_files.append((filepath, error))
            elif changed:
                changed_files.append(filepath)
    print("\n" + "=" * 42)
    print("SUMMARY")
    print("-" * 42)
    if changed_files:
        print(f"\n✅ Modified {len(changed_files)} file(s):")
        for f in changed_files:
            print(f"  - {f.relative_to(cwd)}")
    else:
        print("\n✅ No files were modified")
    if error_files:
        print(f"\n❌ Errors in {len(error_files)} file(s):")
        for f, err in error_files:
            print(f"  - {f.relative_to(cwd)}: {err}")
    print(f"   Modified: {len(changed_files)}")
    print(f"   Errors: {len(error_files)}")
if __name__ == "__main__":
    main()
