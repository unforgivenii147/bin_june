#!/data/data/com.termux/files/usr/bin/python


import sys
from pathlib import Path
import tree_sitter_python as tsp
from dh import STDLIB2, cprint, get_filez
from rapidfuzz import fuzz
from tree_sitter import Language, Parser

cwd = Path.cwd()
parser = Parser()
parser.language = Language(tsp.language())
VALID = {"import_statement", "import_from_statement"}


def process_file(path: Path) -> None:
    path = Path(path)
    src = path.read_bytes()
    tree = parser.parse(src)
    root = tree.root_node
    impoz = []
    results = [src[node.start_byte : node.end_byte].decode() for node in root.children if node.type in VALID]
    if results:
        for k in results:
            if k.startswith("import "):
                k = k.replace("import ", "")
                if " as " in k:
                    indx = k.index(" as ")
                    k = k[:indx]
                if "." in k:
                    indx = k.index(".")
                    k = k[:indx]
                if k not in impoz and not k.startswith("_"):
                    impoz.append(k + "\n")
            elif k.startswith("from "):
                k = k.replace("from ", "")
                if k.startswith("."):
                    continue
                if " as " in k:
                    indx = k.index(" as ")
                    k = k[:indx]
                if "." in k:
                    indx = k.index(".")
                    k = k[:indx]
                if " import" in k:
                    indx = k.index(" import")
                    k = k[:indx]
                if k not in impoz and not k.startswith("_"):
                    impoz.append(k + "\n")
    impoz = sorted(set(impoz))
    stdlib2 = list(STDLIB2)
    for x in impoz:
        x = x.strip().lower()
        if x in STDLIB2 and x not in {"io", "os", "pathlib", "ast", "urllib"}:
            cprint(f"{path.relative_to(cwd)}", "cyan")
            continue
        for v in stdlib2:
            v = v.lower()
            ratio = fuzz.ratio(x, v)
            if (
                ratio > 85
                and len(x) > 3
                and len(v) > 3
                and x
                not in {
                    "io",
                    "os",
                    "pathlib",
                    "urllib",
                    "tkinter",
                    "pickle",
                    "string",
                    "queue",
                    "urllib3",
                    "configparser",
                    "copyreg",
                    "httplib2",
                }
            ):
                cprint(f"{path.relative_to(cwd)}", "yellow")
                cprint(f"{x} / {v} / {ratio}", "green")
                continue


def main() -> None:
    for path in get_filez(cwd):
        if path.is_symlink():
            continue
        if path.suffix == ".py":
            process_file(path)


if __name__ == "__main__":
    sys.exit(main())
