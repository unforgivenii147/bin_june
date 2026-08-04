#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from dh import MIME2EXT, cprint, is_binary, unique_path, colored, runcmd

SKIP_DIRS = {".git", "__pycache__"}
SHEBANG_MAP: dict[str, str] = {
    "python": ".py",
    "python2": ".py",
    "python3": ".py",
    "bash": ".sh",
    "sh": ".sh",
    "zsh": ".sh",
    "fish": ".sh",
    "dash": ".sh",
    "ksh": ".sh",
    "tcsh": ".sh",
    "csh": ".sh",
    "perl": ".pl",
    "perl5": ".pl",
    "ruby": ".rb",
    "lua": ".lua",
    "tcl": ".tcl",
    "expect": ".exp",
    "awk": ".awk",
    "gawk": ".awk",
    "nawk": ".awk",
    "sed": ".sed",
    "make": ".mk",
    "gmake": ".mk",
    "node": ".js",
    "nodejs": ".js",
    "deno": ".js",
    "php": ".php",
    "php-cgi": ".php",
    "racket": ".rkt",
    "guile": ".scm",
    "clisp": ".lisp",
    "sbcl": ".lisp",
    "ccl": ".lisp",
    "octave": ".m",
    "Rscript": ".R",
    "R": ".R",
    "swipl": ".pl",
    "yap": ".pl",
    "ghc": ".hs",
    "runghc": ".hs",
    "erlc": ".erl",
    "escript": ".erl",
    "elixir": ".exs",
    "mix": ".exs",
    "scala": ".scala",
    "kotlin": ".kt",
    "dart": ".dart",
    "swift": ".swift",
    "crystal": ".cr",
    "nim": ".nim",
    "zig": ".zig",
    "v": ".v",
    "go": ".go",
    "rustc": ".rs",
    "cargo": ".rs",
    "julia": ".jl",
    "coffee": ".coffee",
    "csharp": ".cs",
    "dotnet": ".cs",
    "fsharp": ".fsx",
    "groovy": ".groovy",
    "gradle": ".gradle",
    "haxe": ".hx",
    "neko": ".neko",
    "valac": ".vala",
    "genie": ".gs",
    "meson": ".build",
    "ninja": ".ninja",
    "cmake": ".cmake",
    "qmake": ".pro",
    "scons": ".sconstruct",
    "waf": ".wscript",
    "autoconf": ".ac",
    "automake": ".am",
    "m4": ".m4",
    "bison": ".y",
    "yacc": ".y",
    "flex": ".l",
    "lex": ".l",
    "ant": ".xml",
    "mvn": ".xml",
    "sbt": ".sbt",
    "lein": ".clj",
    "boot": ".clj",
    "clojure": ".clj",
    "lisp": ".lisp",
    "scheme": ".scm",
    "chicken": ".scm",
    "csi": ".scm",
    "csc": ".scm",
    "bigloo": ".scm",
    "stklos": ".scm",
    "gosh": ".scm",
    "kawa": ".scm",
    "sisc": ".scm",
    "mit-scheme": ".scm",
    "tinyscheme": ".scm",
    "prolog": ".pl",
    "gprolog": ".pl",
    "xsb": ".pl",
    "mercury": ".m",
    "sqlite3": ".sql",
    "psql": ".sql",
    "mysql": ".sql",
    "isql": ".sql",
    "osql": ".sql",
    "tsql": ".sql",
    "bc": ".bc",
    "dc": ".dc",
    "factor": ".factor",
    "gforth": ".fs",
    "lush": ".lsh",
    "newlisp": ".lsp",
    "picolisp": ".lsp",
    "rebol": ".r",
    "red": ".red",
    "io": ".io",
    "self": ".self",
    "smalltalk": ".st",
    "gst": ".st",
    "squeak": ".st",
    "pharo": ".st",
    "cuis": ".st",
    "scratch": ".sb3",
    "pure": ".pure",
    "q": ".q",
    "k": ".k",
    "j": ".ijs",
    "apl": ".apl",
    "gnuapl": ".apl",
    "dzyn": ".dzyn",
    "bqn": ".bqn",
    "uiua": ".ua",
    "purescript": ".purs",
    "idris": ".idr",
    "agda": ".agda",
    "coq": ".v",
    "isabelle": ".thy",
    "lean": ".lean",
    "smt": ".smt2",
    "z3": ".smt2",
    "cvc4": ".smt2",
    "cvc5": ".smt2",
    "vampire": ".vampire",
    "eprover": ".eprover",
    "spass": ".spass",
    "tptp": ".tptp",
    "maude": ".maude",
    "elf": ".elf",
    "twelf": ".elf",
    "abella": ".abella",
    "lambda-prolog": ".lprolog",
    "minikanren": ".mk",
    "core.logic": ".clj",
    "datalog": ".dl",
    "souffle": ".dl",
    "clingo": ".lp",
    "gringo": ".lp",
    "dlv": ".dlv",
    "xsb": ".P",
    "eclipse": ".ecl",
    "sicstus": ".pl",
    "swi-prolog": ".pl",
    "yap-prolog": ".pl",
    "gnu-prolog": ".pl",
    "b-prolog": ".pl",
    "ciao": ".pl",
    "tuprolog": ".pl",
    "jiprolog": ".pl",
    "logtalk": ".lgt",
    "visual-prolog": ".pro",
    "pdc-prolog": ".pro",
    "amzi": ".pro",
    "arity": ".pro",
    "lpa": ".pro",
    "micro-prolog": ".pro",
    "poplog": ".pop",
    "pop-11": ".pop",
    "prolog++": ".pp",
    "object-prolog": ".op",
    "flora-2": ".flr",
    "er-go": ".ergo",
    "fril": ".fril",
    "godel": ".gdl",
    "hal": ".hal",
    "mozilla": ".moz",
    "oz": ".oz",
    "mz": ".mz",
    "scheme48": ".scm",
    "scsh": ".scm",
    "stalin": ".scm",
    "larceny": ".scm",
    "mosh": ".scm",
    "ypsilon": ".scm",
    "iron-scheme": ".scm",
    "sagittarius": ".scm",
    "foment": ".scm",
    "chibi": ".scm",
    "picrin": ".scm",
    "cyclone": ".scm",
    "gerbil": ".scm",
    "gambit": ".scm",
    "typed-racket": ".rkt",
    "lazy-racket": ".rkt",
    "frracket": ".rkt",
    "scribble": ".scrbl",
    "slideshow": ".scrbl",
    "pollen": ".pm",
    "raco": ".rkt",
    "planet": ".plt",
    "snow": ".snow",
    "snow2": ".snow",
    "snow3": ".snow",
    "snow4": ".snow",
    "snow5": ".snow",
    "snow6": ".snow",
    "snow7": ".snow",
    "snow8": ".snow",
    "snow9": ".snow",
    "snow10": ".snow",
    "snow11": ".snow",
    "snow12": ".snow",
    "snow13": ".snow",
    "snow14": ".snow",
    "snow15": ".snow",
    "snow16": ".snow",
    "snow17": ".snow",
    "snow18": ".snow",
    "snow19": ".snow",
    "snow20": ".snow",
    "snow21": ".snow",
    "snow22": ".snow",
    "snow23": ".snow",
    "snow24": ".snow",
    "snow25": ".snow",
    "snow26": ".snow",
    "snow27": ".snow",
    "snow28": ".snow",
    "snow29": ".snow",
    "snow30": ".snow",
    "snow31": ".snow",
    "snow32": ".snow",
    "snow33": ".snow",
    "snow34": ".snow",
    "snow35": ".snow",
    "snow36": ".snow",
    "snow37": ".snow",
    "snow38": ".snow",
    "snow39": ".snow",
    "snow40": ".snow",
    "snow41": ".snow",
    "snow42": ".snow",
    "snow43": ".snow",
    "snow44": ".snow",
    "snow45": ".snow",
    "snow46": ".snow",
    "snow47": ".snow",
    "snow48": ".snow",
    "snow49": ".snow",
    "snow50": ".snow",
    "snow51": ".snow",
    "snow52": ".snow",
    "snow53": ".snow",
    "snow54": ".snow",
    "snow55": ".snow",
    "snow56": ".snow",
    "snow57": ".snow",
    "snow58": ".snow",
    "snow59": ".snow",
    "snow60": ".snow",
    "snow61": ".snow",
    "snow62": ".snow",
    "snow63": ".snow",
    "snow64": ".snow",
    "snow65": ".snow",
    "snow66": ".snow",
    "snow67": ".snow",
    "snow68": ".snow",
    "snow69": ".snow",
    "snow70": ".snow",
    "snow71": ".snow",
    "snow72": ".snow",
    "snow73": ".snow",
    "snow74": ".snow",
    "snow75": ".snow",
    "snow76": ".snow",
    "snow77": ".snow",
    "snow78": ".snow",
    "snow79": ".snow",
    "snow80": ".snow",
    "snow81": ".snow",
    "snow82": ".snow",
    "snow83": ".snow",
    "snow84": ".snow",
    "snow85": ".snow",
    "snow86": ".snow",
    "snow87": ".snow",
    "snow88": ".snow",
    "snow89": ".snow",
    "snow90": ".snow",
    "snow91": ".snow",
    "snow92": ".snow",
    "snow93": ".snow",
    "snow94": ".snow",
    "snow95": ".snow",
    "snow96": ".snow",
    "snow97": ".snow",
    "snow98": ".snow",
    "snow99": ".snow",
    "snow100": ".snow",
}

SKIP_EXTS: frozenset[str] = frozenset({".css", ".js"})


def fix_by_shebang(path: Path) -> str | None:
    if is_binary(path):
        return None
    try:
        with open(path, "rb") as f:
            first_line = f.readline(256)
        if not first_line.startswith(b"#!"):
            return None
        shebang = first_line.decode("utf-8", errors="replace").strip()
        for interpreter, ext in SHEBANG_MAP.items():
            if interpreter in shebang:
                return ext
        return None
    except Exception:
        return None


def get_file_mime(path: Path) -> str | None:
    result = runcmd(["file", "--brief", "--mime-type", str(path)])
    if result["exit_code"] != 0:
        return None
    mime = result["stdout"].strip()
    if not mime:
        return None
    return mime


def safe_rename(old: Path, new: Path) -> bool:
    try:
        new = unique_path(new)
        old.rename(new)
        return True
    except Exception:
        return False


def process_directory(directory: Path, confirm: bool = False) -> list[dict]:
    mismatches: list[dict] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            file_path = Path(root) / file
            if not file_path.is_file() or file_path.is_symlink():
                continue
            if file_path.stat().st_size == 0:
                continue
            ext = file_path.suffix.lower()
            if ext in SKIP_EXTS:
                continue
            shebang_ext = fix_by_shebang(file_path)
            if shebang_ext:
                current_ext = file_path.suffix.lower()
                if current_ext != shebang_ext:
                    new_name = file_path.with_suffix(shebang_ext).name
                    new_path = file_path.with_name(new_name)
                    mismatches.append(
                        {
                            "path": file_path,
                            "mime": "shebang",
                            "current_ext": current_ext or "(none)",
                            "expected_ext": shebang_ext,
                            "new_path": new_path,
                        }
                    )
                continue
            mime = get_file_mime(file_path)
            if not mime:
                continue
            if mime == "text/plain":
                continue
            expected_exts = MIME2EXT.get(mime, [])
            if not expected_exts:
                continue
            expected_ext = expected_exts[0]
            current_ext = file_path.suffix.lower()
            if current_ext == expected_ext:
                continue
            if current_ext in expected_exts:
                continue
            if current_ext:
                new_name = file_path.stem + expected_ext
            else:
                new_name = file_path.name + expected_ext
            new_path = file_path.with_name(new_name)
            mismatches.append(
                {
                    "path": file_path,
                    "mime": mime,
                    "current_ext": current_ext or "(none)",
                    "expected_ext": expected_ext,
                    "new_path": new_path,
                }
            )
    return mismatches


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix file extension mismatches by analyzing file content.")
    parser.add_argument("-y", action="store_true", help="Enable confirmation mode")
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to scan (default: current directory)",
    )
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        cprint(f"Error: {directory} is not a valid directory", color="red", attrs=["bold"])
        sys.exit(1)
    mismatches = process_directory(directory, confirm=args.y)
    if not mismatches:
        cprint("No mismatches found.", color="green", attrs=["bold"])
        sys.exit(0)
    cprint(
        f"\nFound {len(mismatches)} mismatched file(s):\n",
        color="yellow",
        attrs=["bold"],
    )
    for item in mismatches:
        orig = colored(str(item["path"]), color="red", attrs=["bold"])
        mime_info = colored(f"mime={item['mime']}", color="cyan")
        expected = colored(f"expected ext ={item['expected_ext']}", color="green")
        new_name = colored(item["new_path"].name, color="green", attrs=["bold"])
        print(f"{orig}")
        print(f"  {mime_info}")
        print(f"  {expected}")
        print(f"  new name = {new_name}")
        if args.y:
            response = input(f"  {item['path'].name} -> {item['new_path'].name} ? [y/N] ").strip().lower()
            if response != "y":
                print("  Skipped.")
                continue
        if safe_rename(item["path"], item["new_path"]):
            cprint(f"  Renamed to {item['new_path'].name}", color="green")
        else:
            cprint("  Failed to rename", color="red", attrs=["bold"])
        print()
    cprint("Done.", color="green", attrs=["bold"])


if __name__ == "__main__":
    main()
