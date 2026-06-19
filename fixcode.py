#!/data/data/com.termux/files/usr/bin/python

import ast
import re
from pathlib import Path

INDENT = " " * 4
DEF_CLASS = re.compile("^\\s*(def|class)\\s+")
MAIN_GUARD = re.compile("^\\s*if\\s+__name__\\s*==\\s*['\"]__main__['\"]\\s*:")
BLOCK_START = re.compile(
    "\n    ^\\s*\n    (\n        if\\s+|\n        elif\\s+|\n        else\\s*:|\n        for\\s+|\n        while\\s+|\n        try\\s*:|\n        except\\s+|\n        finally\\s*:|\n        with\\s+\n    )\n    ",
    re.VERBOSE,
)


def is_code_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    return (
        s.startswith((
            "def ",
            "class ",
            "if ",
            "elif ",
            "else:",
            "for ",
            "while ",
            "try:",
            "except ",
            "finally:",
            "with ",
            "return",
            "import ",
            "from ",
            "@",
            "#",
        ))
        or "=" in s
        or "(" in s
        or s.endswith(":")
    )


def clean_text(text: str) -> str:
    out = []
    indent_level = 0
    in_code = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            out.append("")
            continue
        if DEF_CLASS.match(line):
            in_code = True
        if not in_code and (not is_code_line(line)):
            out.append("# " + line.strip())
            continue
        stripped = line.strip()
        if DEF_CLASS.match(stripped):
            indent_level = 0
            out.append(stripped)
            indent_level = 1
            continue
        if MAIN_GUARD.match(stripped):
            indent_level = 1
            out.append('if __name__ == "__main__":')
            continue
        if stripped.startswith(("return", "pass", "break", "continue", "raise")):
            out.append(INDENT * indent_level + stripped)
            indent_level = max(indent_level - 1, 0)
            continue
        if BLOCK_START.match(stripped):
            out.append(INDENT * indent_level + stripped)
            indent_level += 1
            continue
        out.append(INDENT * indent_level + stripped)
    return "\n".join(out)


def ast_validate(code: str) -> tuple[bool, str | None]:
    try:
        ast.parse(code)
        return (True, None)
    except SyntaxError as e:
        return (False, f"{e.msg} (line {e.lineno}, col {e.offset})")


def main() -> None:
    import sys

    src = Path(sys.argv[1])
    dst = Path(sys.argv[1])
    cleaned = clean_text(src.read_text(encoding="utf-8", errors="ignore"))
    ok, err = ast_validate(cleaned)
    if ok:
        dst.write_text(cleaned, encoding="utf-8")
        print(f"✔ AST valid → {dst}")
    else:
        dst.write_text(cleaned, encoding="utf-8")
        print("✘ AST validation failed")
        print(err)
        print("Wrote for inspection")


if __name__ == "__main__":
    main()
