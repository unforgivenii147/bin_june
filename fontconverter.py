#!/data/data/com.termux/files/home/.local/bin/python
"""
font_convert.py — Convert TTF/OTF/WOFF/WOFF2 font files using fontTools.

Scope note:
    fontTools can freely re-wrap the SAME outline format between the raw
    SFNT container (.ttf/.otf) and the compressed web formats (.woff/.woff2).
    It does NOT convert glyph outlines between TrueType (glyf) and
    PostScript/CFF (CFF /CFF2) — that requires outline-level tooling
    (cu2qu, AFDKO, etc.) and is out of scope. Requests that would need that
    (e.g. a CFF/OTF font -> .ttf, or a TrueType font -> .otf) are detected
    and reported as SKIPPED rather than producing a broken font.

Requirements:
    pip install "fonttools[woff]>=4.50,<5"   # [woff] pulls in brotli for woff2

Usage:
    python font_convert.py                          # cwd, recursive, -> woff2
    python font_convert.py fonts/ extra.ttf --to otf
    python font_convert.py fonts/ --to woff2 -r      # remove originals on success
    python font_convert.py fonts/ --to ttf -j 8
"""

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont, TTLibError

SUPPORTED_EXTS = {".ttf", ".otf", ".woff", ".woff2"}
VALID_TARGETS = {"ttf", "otf", "woff", "woff2"}
CFF_TABLES = {"CFF ", "CFF2"}
TRUETYPE_TABLE = "glyf"


@dataclass
class ConvResult:
    src: Path
    dst: Path | None = None
    ok: bool = False
    skipped_reason: str | None = None
    error: str | None = None
    src_size: int = 0
    dst_size: int = 0
    seconds: float = 0.0
    removed_src: bool = False


def iter_font_files(paths: list[Path]) -> list[Path]:
    """Expand files/dirs into a deduplicated, sorted list of font files."""
    found: set[Path] = set()
    for p in paths:
        if p.is_dir():
            for ext in SUPPORTED_EXTS:
                found.update(p.rglob(f"*{ext}"))
        elif p.is_file():
            if p.suffix.lower() in SUPPORTED_EXTS:
                found.add(p)
            else:
                print(f"warning: ignoring non-font file: {p}", file=sys.stderr)
    return sorted(found)


def _outline_kind(font: TTFont) -> str:
    """Return 'cff', 'truetype', or 'unknown' based on tables actually present."""
    tags = set(font.keys())
    if tags & CFF_TABLES:
        return "cff"
    if TRUETYPE_TABLE in tags:
        return "truetype"
    return "unknown"


def convert_one(src: Path, target: str, remove_src: bool) -> ConvResult:
    start = time.perf_counter()
    res = ConvResult(src=src)

    try:
        res.src_size = src.stat().st_size
    except OSError as exc:
        res.error = f"stat failed: {exc}"
        res.seconds = time.perf_counter() - start
        return res

    dst = src.with_suffix(f".{target}")
    if dst == src:
        res.skipped_reason = "source already matches target format"
        res.seconds = time.perf_counter() - start
        return res

    font = None
    try:
        # lazy=True: don't decompile tables we don't touch (memory efficiency).
        # recalcBBoxes/recalcTimestamp=False: we're only re-flavoring the
        # container, not editing glyph data, so skip the extra work/decompile
        # that recalculation would force.
        font = TTFont(str(src), lazy=True, recalcBBoxes=False, recalcTimestamp=False)
        kind = _outline_kind(font)

        if target in ("woff", "woff2"):
            font.flavor = target  # works for either outline kind
        else:
            if kind == "unknown":
                res.skipped_reason = "no recognizable glyf/CFF outline table"
                return res
            needs_cff = target == "otf"
            if needs_cff and kind != "cff":
                res.skipped_reason = (
                    "source has TrueType (glyf) outlines; converting to .otf "
                    "requires outline conversion, which is unsupported"
                )
                return res
            if not needs_cff and kind != "truetype":
                res.skipped_reason = (
                    "source has CFF outlines; converting to .ttf requires outline conversion, which is unsupported"
                )
                return res
            font.flavor = None  # unwrap to raw sfnt container

        font.save(str(dst))
        res.dst = dst
        res.dst_size = dst.stat().st_size
        res.ok = True

        if remove_src:
            try:
                src.unlink()
                res.removed_src = True
            except OSError as exc:
                res.error = f"converted ok, but failed to remove source: {exc}"

    except (TTLibError, OSError, Exception) as exc:
        # Broad catch is deliberate: one malformed font must not kill the
        # whole batch. Clean up any partial output file.
        res.error = f"conversion failed: {exc}"
        if dst.exists():
            try:
                dst.unlink()
            except OSError:
                pass
    finally:
        if font is not None:
            try:
                font.close()
            except Exception:
                pass
        res.seconds = time.perf_counter() - start

    return res


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB"):
        if abs(n) < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


def print_report(results: list[ConvResult]) -> None:
    results.sort(key=lambda r: str(r.src))
    name_w = min(max((len(r.src.name) for r in results), default=4), 40)

    header = f"{'FILE':<{name_w}}  {'STATUS':<6}  {'SIZE (in->out)':<18}  {'RATIO':<7}  {'TIME':<7}  NOTE"
    print(header)
    print("-" * len(header))

    ok = skipped = failed = 0
    total_in = total_out = 0

    for r in results:
        name = r.src.name if len(r.src.name) <= name_w else r.src.name[: name_w - 1] + "…"

        if r.ok:
            ok += 1
            total_in += r.src_size
            total_out += r.dst_size
            ratio = (r.dst_size / r.src_size * 100) if r.src_size else 0.0
            size_str = f"{human_size(r.src_size)}->{human_size(r.dst_size)}"
            status = "OK*" if r.removed_src else "OK"
            note = r.error or ""  # e.g. "removed source" failure, if any
            print(f"{name:<{name_w}}  {status:<6}  {size_str:<18}  {ratio:5.1f}%  {r.seconds:5.2f}s  {note}")
        elif r.skipped_reason:
            skipped += 1
            print(f"{name:<{name_w}}  {'SKIP':<6}  {'-':<18}  {'-':<7}  {r.seconds:5.2f}s  {r.skipped_reason}")
        else:
            failed += 1
            print(f"{name:<{name_w}}  {'FAIL':<6}  {'-':<18}  {'-':<7}  {r.seconds:5.2f}s  {r.error}")

    print("-" * len(header))
    print(f"Total: {len(results)}  ok={ok}  skipped={skipped}  failed={failed}")
    if total_in:
        print(
            f"Size:  {human_size(total_in)} -> {human_size(total_out)} ({total_out / total_in * 100:.1f}% of original)"
        )
    if any(r.removed_src for r in results):
        print("(* = original file removed)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="font_convert.py",
        description="Convert TTF/OTF/WOFF/WOFF2 font files using fontTools.",
    )
    p.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Font files and/or directories (searched recursively). Default: current directory, recursive.",
    )
    p.add_argument(
        "--to",
        dest="target",
        choices=sorted(VALID_TARGETS),
        default="woff2",
        help="Output format (default: woff2).",
    )
    p.add_argument(
        "-r",
        "--remove",
        action="store_true",
        help="Delete the original file after a successful conversion.",
    )
    p.add_argument(
        "-j",
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel worker processes (default: 4).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    raw_inputs = [p.resolve() for p in (args.inputs or [Path(".")])]
    missing = [p for p in raw_inputs if not p.exists()]
    if missing:
        for p in missing:
            print(f"error: path not found: {p}", file=sys.stderr)
        return 2

    files = iter_font_files(raw_inputs)

    already_target = [f for f in files if f.suffix.lower().lstrip(".") == args.target]
    if already_target:
        print(f"Skipping {len(already_target)} file(s) already in .{args.target} format.")
    files = [f for f in files if f not in already_target]

    if not files:
        print("No convertible font files found.")
        return 0

    max_workers = max(1, args.max_workers)
    print(f"Converting {len(files)} file(s) -> .{args.target} with {max_workers} worker(s)...\n")

    results: list[ConvResult] = []
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(convert_one, f, args.target, args.remove): f for f in files}
        for fut in as_completed(futures):
            results.append(fut.result())

    print_report(results)

    failed = sum(1 for r in results if not r.ok and not r.skipped_reason)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
