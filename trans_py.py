#!/data/data/com.termux/files/usr/bin/python

import ast
import os
import re
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from deep_translator import GoogleTranslator
from dh import DOC_TH1, DOC_TH2, get_pyfiles

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


def is_non_english(line):
    return re.search("[^\\x00-\\x7F]", line)


def translate_line(line):
    if is_non_english(line.strip()):
        try:
            trans = get_translator().translate(line.strip())
            if trans and trans.strip() and (trans.strip() != line.strip()):
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


def translate_docstring(docstr):
    new_lines = []
    for line in docstr.splitlines():
        new_lines.append(line)
        transl = translate_line(line)
        if transl:
            new_lines.append(transl)
    return "\n".join(new_lines)


def process_file(filepath):
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
                indentation = re.match("\\s*", line).group(0)
                final_lines.append(f"{indentation}# {trans}")
    Path(filepath).write_text("\n".join(final_lines) + "\n", encoding="utf-8")
    print(f"Translated: {filepath}")


def main():
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
