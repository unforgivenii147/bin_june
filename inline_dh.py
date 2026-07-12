#!/data/data/com.termux/files/usr/bin/env python

import argparse
import ast
import sys
from concurrent.futures import ThreadPoolExecutor
from os.path import join
from pathlib import Path

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


paths = [
    "2to313.py",
    "20commonwords.py",
    "223.py",
    "20most.py",
    "2to3ruff.py",
    "alu.py",
    "asteval.py",
    "aremci.py",
    "autotrans.py",
    "b642f.py",
    "bcss.py",
    "best_compression.py",
    "binortxt.py",
    "bightml.py",
    "binsanity.py",
    "bnn.py",
    "buildr.py",
    "cairosvg2pdf.py",
    "ccss.py",
    "cforyou.py",
    "charcount.py",
    "check_double_shebang.py",
    "check_dups.py",
    "check_path_dups.py",
    "clean_names.py",
    "clean_meta.py",
    "clean_subs.py",
    "cleaner.py",
    "cleanuri.py",
    "cliner.py",
    "compare_dirs.py",
    "cppu.py",
    "create_stub.py",
    "crun.py",
    "cytonizer.py",
    "del_empty_lines.py",
    "delbefor.py",
    "delemp.py",
    "delshort.py",
    "delemp2.py",
    "detect_repeated_lines.py",
    "dh_usage.py",
    "dh_usage.py",
    "dh_usage.py",
    "distinfo3.py",
    "distinfo2.py",
    "dufpy.py",
    "dupf.py",
    "ensurebracket.py",
    "ex_const.py",
    "ex_imports.py",
    "excolors.py",
    "excolors2.py",
    "excss.py",
    "eximports.py",
    "eximports3.py",
    "exjs.py",
    "extinfo.py",
    "extract_embedded_elements.py",
    "extract_lines_contains_base64.py",
    "f66.py",
    "fafontpreview.py",
    "file_urls.py",
    "find_big_files.py",
    "find_dup_folders.py",
    "find_non_eng.py",
    "find_nonenglish_files.py",
    "find_scripts.py",
    "find_py2_imports.py",
    "fix_regex_escape.py",
    "fixext.py",
    "fmt_bash.py",
    "foldesiz.py",
    "fontpre.py",
    "fontpreview.py",
    "fsimz.py",
    "frmc.py",
    "furls.py",
    "gclone1.py",
    "gp.py",
    "gz2xz.py",
    "h2md.py",
    "havebin.py",
    "htmin.py",
    "htm2md.py",
    "hijri.py",
    "html_entity.py",
    "html_to_md.py",
    "htmlformat.py",
    "img2asci.py",
    "image2text.py",
    "img2txt.py",
    "import_collector.py",
    "imports.py",
    "imzzz.py",
    "imz3.py",
    "imz.py",
    "imz_plex.py",
    "is2or3.py",
    "isnude.py",
    "isporn.py",
    "jb2.py",
    "jm2.py",
    "joincss.py",
    "jtc2.py",
    "jtc.py",
    "keep_latest_version.py",
    "lll.py",
    "lowername.py",
    "lst.py",
    "ltxt.py",
    "man_doc.py",
    "mergecss.py",
    "mincss.py",
    "merger.py",
    "mkpyc.py",
    "mkpic.py",
    "mkx.py",
    "move_installed_wheels.py",
    "movebin.py",
    "noneng.py",
    "noreq.py",
    "normalize_jscss_filenames.py",
    "noroot.py",
    "ocrgrid2.py",
    "oldest_files.py",
    "oldpy.py",
    "opng.py",
    "oldpi.py",
    "os2p.py",
    "os2p2.py",
    "oxip.py",
    "p45.py",
    "pcssmin.py",
    "perpage.py",
    "pilenhancer.py",
    "piprm.py",
    "pjsmin.py",
    "piu.py",
    "pnew.py",
    "pnr.py",
    "pngq.py",
    "pret2.py",
    "pretret.py",
    "pret4.py",
    "ptranslator.py",
    "pu.py",
    "pycppcheck.py",
    "pydiff.py",
    "pydocr.py",
    "pymht.py",
    "pymhtml.py",
    "pyrg.py",
    "pysvg2.py",
    "pysvg.py",
    "pytokei.py",
    "pytranslator.py",
    "pytokei2.py",
    "r2h.py",
    "re2regex.py",
    "remc.py",
    "remove_dh_dependency.py",
    "remove_dh_dependency.py",
    "remove_lines_containing_str_from_files.py",
    "rename_meta.py",
    "rename_html_by_title.py",
    "renm.py",
    "replacer.py",
    "rm_comments_toml.py",
    "rmbash.py",
    "rmcpp.py",
    "rmempty.py",
    "rmhtml.py",
    "rmi.py",
    "rmlic.py",
    "rmmc.py",
    "rmimg.py",
    "rmjscomments.py",
    "rmshebang.py",
    "rprompt.py",
    "rrw.py",
    "run223.py",
    "run_pylint.py",
    "s16.py",
    "sanity-check.py",
    "shrinkpdf.py",
    "similar_size_files.py",
    "snapper.py",
    "sortbylen.py",
    "soverify.py",
    "spdf.py",
    "spdf2.py",
    "ssdiper.py",
    "strep.py",
    "stringr.py",
    "strip_installed_pkgs.py",
    "strip_tags.py",
    "strip_stdlib.py",
    "stripsofiles.py",
    "svg2png.py",
    "t5.py",
    "tchn.py",
    "tell_font_name.py",
    "ter_ser.py",
    "tnn.py",
    "tfn.py",
    "to_jpg.py",
    "to_png.py",
    "todel.py",
    "tomd.py",
    "top11.py",
    "tottf.py",
    "trans_py.py",
    "transchin.py",
    "transline2.py",
    "transline.py",
    "ts_cpp_doc_remover.py",
    "tsext.py",
    "ttf2woff2.py",
    "txz2whl.py",
    "ucss.py",
    "ufa.py",
    "ultralinetrans.py",
    "ultratranslator.py",
    "upimg.py",
    "urlzz.py",
    "uxz.py",
    "vid2txt.py",
    "woff22woff.py",
]

DH_SRC_DIR = Path("~/isaac/pkgs/dh/src/dh").expanduser()


def build_dh_mapping(dh_path: Path) -> dict:
    init_file = dh_path / "__init__.py"
    if not init_file.exists():
        raise FileNotFoundError(f"Could not find __init__.py at {init_file}")
    mapping = {}
    tree = ast.parse(init_file.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            module_name = node.module
            module_path = dh_path / f"{module_name}.py"
            for alias in node.names:
                mapping[alias.name] = module_path
    return mapping


class ModuleDependencyAnalyzer(ast.NodeVisitor):
    def __init__(self, global_names):
        self.global_names = global_names
        self.references = set()
        self.imported_modules = []

    def visit_Import(self, node):
        self.imported_modules.append(node)

    def visit_ImportFrom(self, node):
        if node.module != "dh" and node.level == 0:
            self.imported_modules.append(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.global_names:
            self.references.add(node.id)


def get_all_dependencies(path: Path, target_symbol: str) -> tuple[set[str], list[str]]:
    if not path.exists():
        return (set(), [])
    content = path.read_text(encoding="utf-8")
    tree = ast.parse(content)
    lines = content.splitlines()
    nodes_by_name = {}
    global_imports = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nodes_by_name[node.name] = node
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    nodes_by_name[t.id] = node
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if getattr(node, "module", "") != "dh" and getattr(node, "level", 0) == 0:
                global_imports.append(node)
    if target_symbol not in nodes_by_name:
        return (set(), [])
    needed_symbols = set()
    to_resolve = [target_symbol]
    while to_resolve:
        current = to_resolve.pop(0)
        if current in needed_symbols:
            continue
        needed_symbols.add(current)
        node = nodes_by_name.get(current)
        if node:
            analyzer = ModuleDependencyAnalyzer(nodes_by_name.keys())
            analyzer.visit(node)
            for ref in analyzer.references:
                if ref not in needed_symbols:
                    to_resolve.append(ref)
    needed_imports = set()
    all_code_text = "\n".join(
        "\n".join(lines[nodes_by_name[sym].lineno - 1 : nodes_by_name[sym].end_lineno]) for sym in needed_symbols
    )
    for imp in global_imports:
        imp_text = ast.unparse(imp)
        if isinstance(imp, ast.Import):
            for alias in imp.names:
                name = alias.asname or alias.name
                if name in all_code_text:
                    needed_imports.add(imp_text)
        elif isinstance(imp, ast.ImportFrom):
            for alias in imp.names:
                name = alias.asname or alias.name
                if name in all_code_text:
                    needed_imports.add(imp_text)
    source_blocks = []
    sorted_symbols = sorted(needed_symbols, key=lambda s: nodes_by_name[s].lineno)
    for sym in sorted_symbols:
        node = nodes_by_name[sym]
        source_blocks.append("\n".join(lines[node.lineno - 1 : node.end_lineno]))
    return (needed_imports, source_blocks)


def process_file(path: Path, mapping: dict):
    path = Path(path)
    if path.resolve() == Path(__file__).resolve():
        return
    try:
        content = path.read_text(encoding="utf-8")
        if "dh" not in content:
            return
        tree = ast.parse(content)
        lines = content.splitlines(keepends=True)

        dh_import_ranges = []
        used_dh_symbols = set()

        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "dh":
                dh_import_ranges.append((node.lineno - 1, node.end_lineno))
                for alias in node.names:
                    used_dh_symbols.add(alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "dh":
                        dh_import_ranges.append((node.lineno - 1, node.end_lineno))

        if not used_dh_symbols:
            return

        for start, end in sorted(dh_import_ranges, reverse=True):
            del lines[start:end]

        file_imports = set()
        file_source_blocks = []
        for symbol in used_dh_symbols:
            if symbol in mapping:
                imports, blocks = get_all_dependencies(mapping[symbol], symbol)
                file_imports.update(imports)
                for block in blocks:
                    if block not in file_source_blocks:
                        file_source_blocks.append(block)
            else:
                file_source_blocks.append(f"# WARNING: Source code for '{symbol}' not found.")

        if file_source_blocks:
            injection_parts = []
            if file_imports:
                injection_parts.append("\n".join(file_imports))
            injection_parts.extend(file_source_blocks)
            inlined_code = "\n\n" + "\n\n".join(injection_parts) + "\n\n"

            # Find the insertion point: after shebang and all imports
            insert_idx = 0

            # Skip shebang line if present
            if lines and lines[0].startswith("#!"):
                insert_idx = 1

            # Parse the file to find the last import statement
            tree = ast.parse(content)
            last_import_end = 0

            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    # Skip dh imports as they'll be removed
                    if isinstance(node, ast.ImportFrom) and node.module == "dh":
                        continue
                    if isinstance(node, ast.Import):
                        skip = False
                        for alias in node.names:
                            if alias.name == "dh":
                                skip = True
                                break
                        if skip:
                            continue
                    last_import_end = max(last_import_end, node.end_lineno)
                else:
                    # Stop at the first non-import statement
                    break

            # If we found imports, insert after them; otherwise insert after shebang
            if last_import_end > 0:
                insert_idx = last_import_end

            # Ensure we have a blank line between imports and inlined code
            if insert_idx > 0 and lines[insert_idx - 1].strip():
                inlined_code = "\n" + inlined_code

            new_content = "".join(lines[:insert_idx]) + inlined_code + "".join(lines[insert_idx:])
            path.write_text(new_content, encoding="utf-8")
            print(f"Refactored: {path} -> Inlined: {', '.join(used_dh_symbols)}")
    except Exception as e:
        print(f"Error processing {path}: {e}")


def main():
    try:
        mapping = build_dh_mapping(DH_SRC_DIR)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    hb = Path.home() / "bin"
    py_files = [join(str(hb), p) for p in paths]
    #    targets = args.targets if args.targets else ["."]

    #    for target in targets:
    #        path = Path(target)
    #        if path.is_file():
    #            if path.suffix == ".py":
    #                py_files.add(path)
    #        elif path.is_dir():
    #            py_files.update(path.rglob("*.py"))
    #        else:
    #            print(f"Warning: Path '{target}' does not exist or is not a file/directory.", file=sys.stderr)

    py_files = list(py_files)

    print(f"Processing {len(py_files)} files using parallel threads...")
    with ThreadPoolExecutor() as executor:
        executor.map(lambda p: process_file(p, mapping), py_files)

    print("Done!")


if __name__ == "__main__":
    main()
