#!/data/data/com.termux/files/usr/bin/env python


from pathlib import Path

from rcssmin import cssmin
from rjsmin import jsmin

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def minify_assets_in_directory(cwd: Path | str = ".") -> None:
    root_dir = Path(cwd)
    if not root_dir.is_dir():
        raise ValueError(f"Directory not found: {root_dir}")
    MINIFIERS = {".js": jsmin, ".css": cssmin}
    minified_count = 0
    errors_count = 0
    asset_files = []
    for ext in MINIFIERS:
        asset_files.extend(root_dir.rglob(f"*{ext}"))
    for file_path in asset_files:
        if not file_path.is_file():
            continue
        ext = file_path.suffix.lower()
        minifier_func = MINIFIERS.get(ext)
        if minifier_func is None:
            continue
        try:
            print(f"processing ... {file_path.name}")
            original_content = file_path.read_text(encoding="utf-8")
            minified_content = minifier_func(original_content)
            file_path.write_text(minified_content, encoding="utf-8")
            minified_count += 1
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
            errors_count += 1
    print(f"\n{'=' * 50}")
    print(f"MINIFICATION SUMMARY")
    print(f"{'=' * 50}")
    print(f"Files minified: {minified_count}")
    print(f"Errors: {errors_count}")
    print(f"Total processed: {minified_count + errors_count}")
    print(f"{'=' * 50}")


def minify_assets_with_extensions(cwd: Path | str = ".", extensions: list[str] | None = None) -> None:
    if extensions is None:
        extensions = [".js", ".css"]
    root_dir = Path(cwd)
    if not root_dir.is_dir():
        raise ValueError(f"Directory not found: {root_dir}")
    MINIFIERS = {".js": jsmin, ".css": cssmin}
    minified_count = 0
    errors_count = 0
    asset_files = []
    for ext in extensions:
        ext_lower = ext.lower()
        if ext_lower in MINIFIERS:
            asset_files.extend(root_dir.rglob(f"*{ext_lower}"))
    for file_path in asset_files:
        if not file_path.is_file():
            continue
        minifier_func = MINIFIERS.get(file_path.suffix.lower())
        if minifier_func is None:
            continue
        try:
            print(f"processing ... {file_path.name}")
            original_content = file_path.read_text(encoding="utf-8")
            minified_content = minifier_func(original_content)
            file_path.write_text(minified_content, encoding="utf-8")
            minified_count += 1
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
            errors_count += 1
    print(f"\n{'=' * 50}")
    print(f"MINIFICATION SUMMARY")
    print(f"{'=' * 50}")
    print(f"Files minified: {minified_count}")
    print(f"Errors: {errors_count}")
    print(f"{'=' * 50}")


def minify_asset(file_path: Path, dry_run: bool = False, backup: bool = False) -> bool:
    if not file_path.is_file():
        print(f"File not found: {file_path}")
        return False
    MINIFIERS = {".js": jsmin, ".css": cssmin}
    minifier_func = MINIFIERS.get(file_path.suffix.lower())
    if minifier_func is None:
        print(f"Unsupported file type: {file_path.suffix}")
        return False
    try:
        print(f"processing ... {file_path.name}")
        if dry_run:
            print(f"  [DRY RUN] Would minify: {file_path}")
            return True
        if backup:
            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            if not backup_path.exists():
                shutil.copy2(file_path, backup_path)
                print(f"  Backup created: {backup_path.name}")
        original_content = file_path.read_text(encoding="utf-8")
        minified_content = minifier_func(original_content)
        file_path.write_text(minified_content, encoding="utf-8")
        original_size = len(original_content.encode("utf-8"))
        minified_size = len(minified_content.encode("utf-8"))
        savings = (original_size - minified_size) / original_size * 100
        print(f"  Minified: {original_size:,} -> {minified_size:,} bytes ({savings:.1f}% reduction)")
        return True
    except Exception as e:
        print(f"Error processing {file_path.name}: {e}")
        return False


def minify_assets_parallel(cwd: Path | str = ".", max_workers: int = 4) -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    root_dir = Path(cwd)
    if not root_dir.is_dir():
        raise ValueError(f"Directory not found: {root_dir}")
    MINIFIERS = {".js": jsmin, ".css": cssmin}
    files_to_process = []
    for ext in MINIFIERS:
        files_to_process.extend(root_dir.rglob(f"*{ext}"))
    if not files_to_process:
        print("No files to minify")
        return
    print(f"Processing {len(files_to_process)} files with {max_workers} workers...")
    minified_count = 0
    errors_count = 0

    def process_file(file_path: Path) -> tuple[Path, bool, str]:
        try:
            original_content = file_path.read_text(encoding="utf-8")
            minifier = MINIFIERS[file_path.suffix.lower()]
            minified_content = minifier(original_content)
            file_path.write_text(minified_content, encoding="utf-8")
            return (file_path, True, "")
        except Exception as e:
            return (file_path, False, str(e))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_file, file_path): file_path for file_path in files_to_process}
        for future in as_completed(futures):
            file_path, success, error = future.result()
            if success:
                minified_count += 1
                print(f"✓ {file_path.name}")
            else:
                errors_count += 1
                print(f"✗ {file_path.name}: {error}")
    print(f"\n{'=' * 50}")
    print(f"MINIFICATION SUMMARY")
    print(f"{'=' * 50}")
    print(f"Files minified: {minified_count}")
    print(f"Errors: {errors_count}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Minify JavaScript and CSS files in a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\nExamples:\n  python minify_assets.py                    # Minify all .js and .css files in current dir\n  python minify_assets.py --dir /path/to/dir # Minify in specific directory\n  python minify_assets.py --ext .js .css     # Minify specific extensions\n  python minify_assets.py --dry-run          # Preview what would be done\n  python minify_assets.py --backup           # Create backups before minifying\n  python minify_assets.py --parallel         # Use parallel processing\n  python minify_assets.py --file style.css   # Minify a single file\n        ",
    )
    parser.add_argument("--dir", default=".", help="Directory to process (default: current directory)")
    parser.add_argument("--ext", nargs="+", help="File extensions to minify (default: .js .css)")
    parser.add_argument("--file", help="Minify a single file instead of directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without modifying files")
    parser.add_argument("--backup", action="store_true", help="Create .bak backup files before minifying")
    parser.add_argument("--parallel", action="store_true", help="Use parallel processing for better performance")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    if args.file:
        success = minify_asset(Path(args.file), dry_run=args.dry_run, backup=args.backup)
        sys.exit(0 if success else 1)
    if args.parallel:
        minify_assets_parallel(Path(args.dir), max_workers=args.workers)
    elif args.ext:
        minify_assets_with_extensions(Path(args.dir), extensions=args.ext)
    else:
        minify_assets_in_directory(Path(args.dir))
