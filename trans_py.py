#!/data/data/com.termux/files/usr/bin/env python
import ast
import os
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from re import Match

from deep_translator import GoogleTranslator


from pathlib import Path
from os import scandir as os_scandir


def is_python_file(path: (str | Path)) -> bool:
    from ast import parse as ast_parse

    path = Path(path)
    if is_binary(path):
        return False
    if not path.stat().st_size:
        return False
    if path.is_file() and path.suffix == ".py":
        return True
    if not path.suffix:
        content = path.read_text(encoding="utf-8")
        if not content:
            return False
        if content.startswith("#!") and "python" in content[:100]:
            return True
        try:
            _ = ast_parse(content)
            return True
        except:
            return False
    return False


def is_binary(path: (Path | str)) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


def get_pyfiles(path: str | Path) -> list[Path]:
    path = Path(path)
    if path.is_file():
        if path.suffix == ".py":
            return [path]
        if not path.suffix and not path.name.startswith(".") and is_python_file(path):
            return [path]
        return []

    if not path.is_dir():
        return []

    pyfiles = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        p = Path(entry.path)
                        if p.suffix == ".py":
                            pyfiles.append(p)
                        elif not p.suffix and not p.name.startswith(".") and is_python_file(p):
                            pyfiles.append(p)
        except (PermissionError, OSError):
            continue

    return sorted(pyfiles)


PYTHON_EXT = ".py"
BACKUP_EXT = ".bak"
CHUNK_SIZE = 5000
TARGET_LANG = "en"
SRC_LANG = "auto"
_thread_local = threading.local()


def get_translator():
    if not hasattr(_thread_local, "translator"):
        _thread_local.translator = GoogleTranslator(source=SRC_LANG, target=TARGET_LANG)
    return _thread_local.translator


def is_non_english(line: str) -> Match[str] | None:
    return re.search(r"[^\x00-\x7F]", line)


def translate_line(line: str):
    if is_non_english(line.strip()):
        try:
            trans = get_translator().translate(line.strip())
            if trans and trans.strip() and trans.strip() != line.strip():
                return trans
        except Exception as e:
            print(f"Translation error: {e} -- Line: {line}")
            return None
    return None


def split_large_text_blocks(text, max_len):
    lines = text.splitlines(keepends=True)
    chunks = []
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) > max_len:
            chunks.append(chunk)
            chunk = ""
        chunk += line
    if chunk:
        chunks.append(chunk)
    return chunks


def translate_docstring(docstr: str) -> str:
    new_lines = []
    for line in docstr.splitlines():
        new_lines.append(line)
        transl = translate_line(line)
        if transl:
            new_lines.append(transl)
    return "\n".join(new_lines)


def process_file(filepath) -> None:
    path = Path(path)
    backup_path = filepath + BACKUP_EXT
    shutil.copyfile(filepath, backup_path)
    code = Path(filepath).read_text(encoding="utf-8")
    len(code) > CHUNK_SIZE
    try:
        parsed = ast.parse(code, filename=filepath, type_comments=True)
    except Exception as e:
        print(f"Failed to parse {filepath}: {e}")
        return
    lines = code.splitlines(keepends=False)
    new_lines = list(lines)
    offset_map = {}
    for node in ast.walk(parsed):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            docstring = ast.get_docstring(node, clean=False)
            if docstring:
                doc_start = node.body[0].lineno - 1 if node.body else None
                for lookback in range(3):
                    possible = doc_start - lookback
                    if possible >= 0 and (
                        lines[possible].lstrip().startswith(DOC_TH1) or lines[possible].lstrip().startswith(DOC_TH2)
                    ):
                        docstring_line = possible
                        break
                else:
                    continue
                doc_lines = []
                line_idx = docstring_line
                quote_type = DOC_TH1 if lines[line_idx].lstrip().startswith(DOC_TH1) else DOC_TH2
                while True:
                    doc_lines.append(lines[line_idx])
                    if lines[line_idx].rstrip().endswith(quote_type) and line_idx != docstring_line:
                        break
                    line_idx += 1
                doc_block = "\n".join(doc_lines)
                doc_body = re.sub(f"^{quote_type}|{quote_type}$", "", doc_block.strip(), flags=re.MULTILINE).strip()
                translated_doc_body = translate_docstring(doc_body)
                translated_doc_block = f"{quote_type}\n{translated_doc_body}\n{quote_type}"
                start = docstring_line + offset_map.get(docstring_line, 0)
                end = line_idx + 1 + offset_map.get(line_idx, 0)
                translated_lines = translated_doc_block.splitlines()
                new_lines[start:end] = translated_lines
                offset = len(translated_lines) - (end - start)
                for k in range(end, len(new_lines)):
                    offset_map[k] = offset_map.get(k, 0) + offset
    final_lines = []
    for line in new_lines:
        final_lines.append(line)
        stripped = line.strip()
        if stripped.startswith("#") and is_non_english(stripped[1:]):
            trans = translate_line(stripped[1:].strip())
            if trans:
                indentation = re.match(r"\s*", line).group(0)
                final_lines.append(f"{indentation}# {trans}")
    Path(filepath).write_text("\n".join(final_lines) + "\n", encoding="utf-8")
    print(f"Translated: {filepath}")


def main() -> None:
    cwd = Path.cwd()
    py_files = get_pyfiles(cwd)
    if not py_files:
        print("No Python files found.")
        return
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {executor.submit(process_file, f): f for f in py_files}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Failed processing {futures[future]}: {e}")


if __name__ == "__main__":
    main()
