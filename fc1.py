#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

import argparse
import logging
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.stderr.write("fonttools is not installed.\n  pip install fonttools\n")
    sys.exit(1)

try:
    import brotli

    _HAS_BROTLI = True
except ImportError:
    try:
        import brotlicffi

        _HAS_BROTLI = True
    except ImportError:
        _HAS_BROTLI = False

SUPPORTED_FORMATS: set[str] = {"ttf", "otf", "woff", "woff2"}

SFNT_VERSIONS: dict[str, object] = {
    "ttf": 0x00010000,
    "otf": "OTTO",
}

FLAVORS: dict[str, str] = {
    "woff": "woff",
    "woff2": "woff2",
}

DEFAULT_OUTPUT_FORMAT = "woff2"
DEFAULT_WORKERS = 4

logger = logging.getLogger("font_converter")


def detect_format(path: Path) -> str | None:
    ext = path.suffix.lower().lstrip(".")
    return ext if ext in SUPPORTED_FORMATS else None


def generate_output_path(
    input_path: Path,
    output_format: str,
    output_dir: Path | None = None,
) -> Path:
    stem = input_path.stem
    if output_dir is not None:
        return output_dir / f"{stem}.{output_format}"
    return input_path.with_suffix(f".{output_format}")


def format_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def convert_font(
    input_path: Path,
    output_format: str,
    remove_original: bool,
    output_dir: Path | None,
    force: bool,
) -> dict:
    stats: dict = {
        "input": str(input_path),
        "output": None,
        "input_format": None,
        "output_format": output_format,
        "input_size": 0,
        "output_size": 0,
        "time": 0.0,
        "success": False,
        "error": None,
        "warning": None,
        "removed_original": False,
    }

    start = time.perf_counter()

    try:
        input_format = detect_format(input_path)
        if input_format is None:
            raise ValueError(f"unsupported extension '{input_path.suffix}'")
        stats["input_format"] = input_format

        if input_format == output_format:
            raise ValueError(f"already .{output_format}")

        output_path = generate_output_path(input_path, output_format, output_dir)
        stats["output"] = str(output_path)

        if output_path.exists() and not force:
            raise FileExistsError(f"output exists (use --force): {output_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        input_size = input_path.stat().st_size
        stats["input_size"] = input_size

        font = TTFont(str(input_path), lazy=False)

        has_cff = "CFF " in font or "CFF2" in font
        has_glyf = "glyf" in font
        warning: str | None = None

        if output_format in FLAVORS:
            font.flavor = FLAVORS[output_format]
        else:
            font.flavor = None

        if output_format in SFNT_VERSIONS:
            if output_format == "otf" and has_glyf and not has_cff:
                warning = "font has TrueType outlines; .otf conventionally uses CFF — outlines were NOT converted"
            elif output_format == "ttf" and has_cff and not has_glyf:
                warning = "font has CFF outlines; .ttf conventionally uses TrueType — outlines were NOT converted"
            font.sfntVersion = SFNT_VERSIONS[output_format]

        font.save(str(output_path))
        font.close()

        output_size = output_path.stat().st_size
        elapsed = time.perf_counter() - start

        stats["output_size"] = output_size
        stats["time"] = elapsed
        stats["success"] = True
        stats["warning"] = warning

        if (
            remove_original
            and input_path.resolve() != output_path.resolve()
            and output_path.exists()
            and output_path.stat().st_size > 0
        ):
            input_path.unlink()
            stats["removed_original"] = True

    except Exception as exc:
        stats["error"] = str(exc)
        stats["time"] = time.perf_counter() - start

    return stats


def find_font_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []

    for path in paths:
        if path.is_file():
            if detect_format(path):
                files.append(path)
            else:
                logger.warning("skipping non-font file: %s", path)
        elif path.is_dir():
            for ext in SUPPORTED_FORMATS:
                files.extend(path.rglob(f"*.{ext}"))
                files.extend(path.rglob(f"*.{ext.upper()}"))
        else:
            logger.warning("path not found: %s", path)

    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        r = f.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(f)
    return unique


def print_file_stats(stats: dict) -> None:
    name = Path(stats["input"]).name
    status = "✓" if stats["success"] else "✗"

    if stats["success"]:
        in_sz = stats["input_size"]
        out_sz = stats["output_size"]
        ratio = (out_sz / in_sz * 100) if in_sz else 0
        saved = (1 - out_sz / in_sz) * 100 if in_sz else 0

        print(f"  {status} {name}")
        print(
            f"      {format_size(in_sz)} → {format_size(out_sz)}  ({ratio:.1f}% of original, {saved:+.1f}% change)"
        )
        print(f"      Time: {stats['time']:.3f}s")

        if stats["warning"]:
            print(f"      ⚠  {stats['warning']}")
        if stats["removed_original"]:
            print("      🗑  original removed")
    else:
        print(f"  {status} {name} — ERROR: {stats['error']}")


def print_summary(all_stats: list[dict]) -> None:
    total = len(all_stats)
    ok = sum(1 for s in all_stats if s["success"])
    fail = total - ok

    print("\n" + "=" * 60)
    print("Summary")
    print("-" * 60)
    print(f"  Files processed : {total}")
    print(f"  Successful      : {ok}")
    print(f"  Failed          : {fail}")

    if ok:
        total_in = sum(s["input_size"] for s in all_stats if s["success"])
        total_out = sum(s["output_size"] for s in all_stats if s["success"])
        total_time = sum(s["time"] for s in all_stats if s["success"])

        print(f"  Input size      : {format_size(total_in)}")
        print(f"  Output size     : {format_size(total_out)}")
        if total_in:
            print(f"  Ratio           : {total_out / total_in * 100:.1f}% of original")
        print(f"  Total time      : {total_time:.3f}s")
        if total > 1:
            print(f"  Avg per file    : {total_time / total:.3f}s")

    print("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert font files between TTF, OTF, WOFF, and WOFF2.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s                              Convert all fonts in cwd → woff2
  %(prog)s font.ttf --to woff            Single file → woff
  %(prog)s ./fonts/ --to ttf -r         Dir → ttf, remove originals
  %(prog)s a.ttf b.otf --to woff2 -j 8   Two files, 8 workers
  %(prog)s ./fonts/ --to otf -o ./out/   Output to ./out/ directory
""",
    )

    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Input font files or directories (default: current directory, recursive)",
    )
    parser.add_argument(
        "--to",
        dest="output_format",
        choices=sorted(SUPPORTED_FORMATS),
        default=DEFAULT_OUTPUT_FORMAT,
        help=f"Output format (default: {DEFAULT_OUTPUT_FORMAT})",
    )
    parser.add_argument(
        "-r",
        "--remove",
        action="store_true",
        help="Remove original file after successful conversion",
    )
    parser.add_argument(
        "-j",
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Max parallel workers (default: {DEFAULT_WORKERS})",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: alongside each input)",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing output files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be converted without converting",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    if args.output_format == "woff2" and not _HAS_BROTLI:
        sys.stderr.write("WOFF2 output requires brotli.\n  pip install brotli\n")
        sys.exit(1)

    input_paths = args.inputs if args.inputs else [Path.cwd()]

    font_files = find_font_files(input_paths)

    if not font_files:
        print("No font files found.")
        sys.exit(0)

    to_convert: list[Path] = []
    already_target: list[Path] = []

    for f in font_files:
        if detect_format(f) == args.output_format:
            already_target.append(f)
        else:
            to_convert.append(f)

    if already_target:
        print(
            f"Skipping {len(already_target)} file(s) already in .{args.output_format} format"
        )

    if not to_convert:
        print("Nothing to convert.")
        sys.exit(0)

    print(f"\nConverting {len(to_convert)} file(s) → .{args.output_format}")
    if args.remove:
        print("  (originals will be removed on success)")
    print()

    if args.dry_run:
        for f in to_convert:
            out = generate_output_path(f, args.output_format, args.output_dir)
            print(f"  {f}  →  {out}")
        sys.exit(0)

    if len(to_convert) == 1:
        all_stats = [
            convert_font(
                to_convert[0],
                args.output_format,
                args.remove,
                args.output_dir,
                args.force,
            )
        ]
        print_file_stats(all_stats[0])

    else:
        all_stats: list[dict] = []
        workers = min(args.workers, len(to_convert))

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    convert_font,
                    f,
                    args.output_format,
                    args.remove,
                    args.output_dir,
                    args.force,
                ): f
                for f in to_convert
            }

            try:
                for future in as_completed(futures):
                    stats = future.result()
                    all_stats.append(stats)
                    print_file_stats(stats)
            except KeyboardInterrupt:
                print("\n\nInterrupted — cancelling remaining tasks …")
                for fut in futures:
                    fut.cancel()
                for fut in futures:
                    if fut.done() and not fut.cancelled():
                        all_stats.append(fut.result())
                print_summary(all_stats)
                sys.exit(130)

    print_summary(all_stats)
    failed = sum(1 for s in all_stats if not s["success"])
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
