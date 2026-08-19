#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import argparse
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Patterns we recognize.
# ---------------------------------------------------------------------------
# fmt: off
# Matches lines that import pkg_resources in some form.
IMPORT_RE = re.compile(r"""^(?P<indent>\s*)(?P<stmt>(?:import|from)\s+pkg_resources(?:\s+import\s+(?P<names>[^\n#]+))?)\s*(?P<comment>#.*)?$""", re.VERBOSE,)

# Specific usages of pkg_resources.* API that we know how to translate.
# Each entry: (regex, replacement_template, needs_metadata_import, needs_resources_import)
USAGE_PATTERNS: list[tuple[re.Pattern, str, bool, bool]] = [
    # pkg_resources.get_distribution("name").version  ->  importlib.metadata.version("name")
    (
        re.compile(r"pkg_resources\.get_distribution\(\s*([^)]+?)\s*\)\.version"),
        r"importlib.metadata.version(\1)",
        True,
        False,
    ),
    # pkg_resources.get_distribution("name")
    (
        re.compile(r"pkg_resources\.get_distribution\(\s*([^)]+?)\s*\)"),
        r"importlib.metadata.distribution(\1)",
        True,
        False,
    ),
    # pkg_resources.resource_string(pkg, path)  ->  importlib.resources.files(pkg).joinpath(path).read_bytes()
    (
        re.compile(r"pkg_resources\.resource_string\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"),
        r"importlib.resources.files(\1).joinpath(\2).read_bytes()",
        False,
        True,
    ),
    # pkg_resources.resource_text(...)  ->  ...read_text(encoding="utf-8")
    (
        re.compile(r"pkg_resources\.resource_text\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"),
        r"importlib.resources.files(\1).joinpath(\2).read_text(encoding='utf-8')",
        False,
        True,
    ),
    # pkg_resources.resource_filename(pkg, path)  ->  str(importlib.resources.files(pkg).joinpath(path))
    (
        re.compile(r"pkg_resources\.resource_filename\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"),
        r"str(importlib.resources.files(\1).joinpath(\2))",
        False,
        True,
    ),
    # pkg_resources.resource_stream(pkg, path)  ->  (importlib.resources.files(pkg) / path).open("rb")
    (
        re.compile(r"pkg_resources\.resource_stream\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)"),
        r"importlib.resources.files(\1).joinpath(\2).open('rb')",
        False,
        True,
    ),
    # pkg_resources.require(...)  ->  importlib.metadata.requires(...)  (returns list of requirements)
    (
        re.compile(r"pkg_resources\.require\(\s*([^)]+?)\s*\)"),
        r"importlib.metadata.requires(\1)",
        True,
        False,
    ),
    # pkg_resources.DistributionNotFound  ->  importlib.metadata.PackageNotFoundError
    (
        re.compile(r"pkg_resources\.DistributionNotFound"),
        r"importlib.metadata.PackageNotFoundError",
        True,
        False,
    ),
    # pkg_resources.VersionConflict  ->  importlib.metadata.PackageNotFoundError (semantics differ; warn)
    # We *report* but do NOT autofix this one (no safe translation).
]

# Generic pattern: any remaining pkg_resources.* usage we just report.
GENERIC_USAGE_RE = re.compile(r"pkg_resources\.([A-Za-z_][A-Za-z0-9_]*)")


@dataclass
class Finding:
    path: Path
    lineno: int
    col: int
    line: str
    kind: str  # "import" | "usage_known" | "usage_unknown"
    pattern: str = ""
    autofixable: bool = False


@dataclass
class FileReport:
    path: Path
    findings: list[Finding] = field(default_factory=list)
    needs_metadata: bool = False
    needs_resources: bool = False
    has_pkg_resources_import: bool = False

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)


# ---------------------------------------------------------------------------
# Scanning / fixing logic.
# ---------------------------------------------------------------------------


def scan_file(path: Path) -> FileReport:
    """Read the file, locate pkg_resources imports/usages, return a report."""
    report = FileReport(path=path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # Skip files we can't read cleanly; surface a benign finding.
        report.findings.append(
            Finding(
                path=path,
                lineno=0,
                col=0,
                line=f"<unreadable: {exc}>",
                kind="usage_unknown",
                pattern="",
                autofixable=False,
            )
        )
        return report

    for i, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.rstrip("\n")
        # Skip lines that look like they are inside a docstring/comment-only.
        # (We still scan them; pkg_resources in a comment is still "usage" worth noting.)

        # Detect imports first.
        m_import = IMPORT_RE.match(stripped)
        if m_import:
            report.has_pkg_resources_import = True
            report.findings.append(
                Finding(
                    path=path,
                    lineno=i,
                    col=m_import.start("stmt") + 1,
                    line=stripped,
                    kind="import",
                    pattern=m_import.group("stmt"),
                    autofixable=True,
                )
            )
            continue

        # Detect known usages.
        for pat, _repl, needs_meta, needs_res in USAGE_PATTERNS:
            for m in pat.finditer(stripped):
                report.findings.append(
                    Finding(
                        path=path,
                        lineno=i,
                        col=m.start() + 1,
                        line=stripped,
                        kind="usage_known",
                        pattern=m.group(0),
                        autofixable=True,
                    )
                )
                report.needs_metadata = report.needs_metadata or needs_meta
                report.needs_resources = report.needs_resources or needs_res

        # Detect any other pkg_resources.X usage we cannot autofix.
        for m in GENERIC_USAGE_RE.finditer(stripped):
            # Don't double-count: if this span is inside a known usage match, skip.
            span = m.span()
            already = False
            for f in report.findings:
                if f.lineno == i and f.kind == "usage_known":
                    # Find that finding's match position; we stored the matched text.
                    pos = stripped.find(f.pattern)
                    if pos != -1 and pos <= span[0] and span[1] <= pos + len(f.pattern):
                        already = True
                        break
            if not already:
                report.findings.append(
                    Finding(
                        path=path,
                        lineno=i,
                        col=m.start() + 1,
                        line=stripped,
                        kind="usage_unknown",
                        pattern=m.group(0),
                        autofixable=False,
                    )
                )

    return report


def autofix_file(path: Path) -> tuple[bool, list[str]]:
    """Apply mechanical replacements to the given file.

    Returns (changed, notes).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False, [f"cannot read {path}"]

    original = text
    notes: list[str] = []

    # 1) Replace known usages of pkg_resources.* API.
    needs_metadata = False
    needs_resources = False

    for pat, repl, needs_meta, needs_res in USAGE_PATTERNS:
        new_text, n = pat.subn(repl, text)
        if n:
            notes.append(f"replaced {n} occurrence(s) of {pat.pattern!r}")
            needs_metadata = needs_metadata or needs_meta
            needs_resources = needs_resources or needs_res
            text = new_text

    # 2) Rewrite imports of pkg_resources.
    #
    #   import pkg_resources                                   -> (removed; we add proper imports below)
    #   from pkg_resources import resource_string              -> (removed; replaced by importlib.resources usage)
    #   import pkg_resources as pr                             -> (removed)
    #
    # We drop the import entirely and re-add `import importlib.metadata`
    # and/or `import importlib.resources` at the top of the file as needed.
    # NOTE: We do not handle aliased `import pkg_resources as pr` rewrites
    # (would need to rewrite all `pr.` references too) — those are reported
    # but not autofixed.

    lines = text.splitlines(keepends=True)
    new_lines: list[str] = []
    removed_import = False
    skipped_alias = False

    for line in lines:
        m = IMPORT_RE.match(line.rstrip("\n"))
        if not m:
            new_lines.append(line)
            continue

        stmt = m.group("stmt")
        # If aliased import (e.g. "import pkg_resources as pr"), do not remove
        # automatically — that would break `pr.` references. Leave a marker.
        if re.search(r"\bas\s+\w+\b", stmt) or (
            stmt.startswith("from")
            and m.group("names")
            and re.search(r"\bas\s+\w+\b", m.group("names"))
        ):
            skipped_alias = True
            new_lines.append(line)
            continue

        removed_import = True
        notes.append(f"removed import: {stmt.strip()}")

    text = "".join(new_lines)

    # 3) If we removed the import, insert the proper importlib imports at the top.
    if removed_import or needs_metadata or needs_resources:
        # Find a good insertion point: after any leading shebang / coding cookie /
        # module docstring is overkill for this tool; we just insert at the very top.
        insertion_lines: list[str] = []
        if needs_metadata:
            insertion_lines.append("import importlib.metadata\n")
        if needs_resources:
            insertion_lines.append("import importlib.resources\n")
        if insertion_lines:
            text = "".join(insertion_lines) + text
            notes.append("added importlib.metadata / importlib.resources imports")

    if skipped_alias:
        notes.append(
            "WARNING: aliased pkg_resources import left untouched; manual review required"
        )

    if text == original:
        return False, notes

    path.write_text(text, encoding="utf-8")
    return True, notes


# ---------------------------------------------------------------------------
# Driver.
# ---------------------------------------------------------------------------


def iter_python_files(root: Path):
    skipped_dirs = {".git", "__pycache__", ".venv", "venv", "env", ".tox", "build", "dist", ".eggs"}
    for p in root.rglob("*.py"):
        # Skip if any path component is a skipped dir.
        if any(part in skipped_dirs for part in p.parts):
            continue
        if p.is_file():
            yield p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report (and optionally autofix) deprecated pkg_resources usage in .py files."
    )
    parser.add_argument(
        "-a", "--autofix", action="store_true", help="Apply mechanical autofixes."
    )
    parser.add_argument(
        "-w",
        "--max-workers",
        type=int,
        default=8,
        help="Number of parallel workers (default: 8).",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress per-file output."
    )
    args = parser.parse_args(argv)

    if sys.version_info < (3, 12):
        print(
            f"warning: running on Python {sys.version.split()[0]}; "
            "pkg_resources is deprecated in Python 3.12+.",
            file=sys.stderr,
        )

    root = Path.cwd()
    files = list(iter_python_files(root))
    if not files:
        print("no .py files found")
        return 0

    max_workers = max(1, args.max_workers)
    total_findings = 0
    files_with_findings = 0
    autofixed_files = 0

    reports: list[FileReport] = []

    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(scan_file, p): p for p in files}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                rep = fut.result()
            except Exception as exc:  # pragma: no cover
                print(f"error scanning {p}: {exc}", file=sys.stderr)
                continue
            reports.append(rep)

    # Sort reports for stable output.
    reports.sort(key=lambda r: r.path)

    # First pass: report.
    for rep in reports:
        if not rep.has_findings:
            continue
        files_with_findings += 1
        if not args.quiet:
            print(f"\n== {rep.path} ==")
        for f in rep.findings:
            total_findings += 1
            tag = "AUTOFIX" if f.autofixable else "MANUAL"
            if not args.quiet:
                print(
                    f"  {f.lineno}:{f.col}  [{tag}] ({f.kind})  {f.pattern!r}"
                )
                print(f"      | {f.line.strip()}")

    print()
    print(f"scanned files      : {len(files)}")
    print(f"files with findings: {files_with_findings}")
    print(f"total findings     : {total_findings}")

    # Second pass: autofix, in main process (writes need to be serialized-ish;
    # we still parallelize scanning, but writes are cheap and ordering matters less).
    if args.autofix:
        print("\n--autofix enabled--")
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(autofix_file, r.path): r.path for r in reports if r.has_findings}
            for fut in as_completed(futures):
                p = futures[fut]
                try:
                    changed, notes = fut.result()
                except Exception as exc:  # pragma: no cover
                    print(f"  error autofixing {p}: {exc}", file=sys.stderr)
                    continue
                if changed:
                    autofixed_files += 1
                    print(f"  fixed: {p}")
                    for n in notes:
                        print(f"      - {n}")
                else:
                    if notes:
                        print(f"  no-op: {p}")
                        for n in notes:
                            print(f"      - {n}")

        print(f"files autofixed    : {autofixed_files}")

    return 0 if total_findings == 0 or not args.autofix else (1 if total_findings else 0)


if __name__ == "__main__":
    raise SystemExit(main())
