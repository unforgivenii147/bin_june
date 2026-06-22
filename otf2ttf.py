#!/data/data/com.termux/files/usr/bin/python
"""
Convert OTF files to TTF recursively using multiprocessing.
Removes original OTF files after successful conversion.
Requires: pip install fonttools brotli
"""

import sys
from multiprocessing import Pool
from pathlib import Path

from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont


def convert_otf_to_ttf(otf_path: Path) -> dict:
    """
    Convert a single OTF font to TTF format and remove original if successful.

    Args:
        otf_path: Path object pointing to the OTF file

    Returns:
        Dictionary with conversion status and info
    """
    ttf_path = otf_path.with_suffix(".ttf")
    result = {"otf": str(otf_path), "ttf": str(ttf_path), "status": "unknown"}

    # Skip if TTF already exists
    if ttf_path.exists():
        result["status"] = "skipped_exists"
        return result

    try:
        # Load the OTF font
        font = TTFont(otf_path)

        # If it's already a TrueType font (has glyf table), no conversion needed
        if "glyf" in font:
            result["status"] = "skipped_already_ttf"
            return result

        # Get the CFF (PostScript) outlines
        cff_table = None
        if "CFF2" in font:
            cff_table = font["CFF2"]
        elif "CFF " in font:
            cff_table = font["CFF "]
        else:
            result["status"] = "failed_no_cff"
            return result

        # Get character map and glyph order
        glyph_order = font.getGlyphOrder()

        # Convert CFF outlines to TrueType outlines
        for glyph_name in glyph_order:
            if glyph_name in cff_table:
                # Create a new TTGlyphPen for each glyph
                glyph_pen = TTGlyphPen(None)

                # Draw the CFF outline
                char_string = cff_table[glyph_name]
                char_string.draw(glyph_pen)

                # Add to TrueType glyph set
                font["glyf"][glyph_name] = glyph_pen.glyph()

        # Update tables for TrueType format
        font.flavor = None  # Ensure it's not a woff/woff2

        # Remove CFF tables and make it a TrueType font
        for table in ["CFF ", "CFF2", "VORG"]:
            if table in font:
                del font[table]

        # Ensure required TrueType tables exist
        if "glyf" not in font:
            raise ValueError("Failed to create glyf table")

        # Set TrueType scaler type
        font.sfVersion = "\x00\x01\x00\x00"
        font.reader = None

        # Save as TTF
        font.save(ttf_path)

        # Remove original OTF file after successful conversion
        otf_path.unlink()
        result["status"] = "success"

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        # Clean up TTF file if it was partially created
        if ttf_path.exists():
            ttf_path.unlink()

    return result


def find_otf_files(root_dir: Path = None, pattern: str = "**/*.otf") -> list[Path]:
    """
    Find all OTF files recursively using pathlib.

    Args:
        root_dir: Starting directory (default: current directory)
        pattern: Glob pattern for finding files

    Returns:
        List of Path objects for OTF files
    """
    if root_dir is None:
        root_dir = Path.cwd()
    else:
        root_dir = Path(root_dir)

    return list(root_dir.glob(pattern))


def process_file(args: tuple) -> dict:
    """
    Wrapper function for multiprocessing.

    Args:
        args: Tuple of (otf_path,)

    Returns:
        Conversion result dictionary
    """
    (otf_path,) = args
    print(f"Processing: {otf_path}")
    result = convert_otf_to_ttf(otf_path)

    # Print result for this file
    if result["status"] == "success":
        print(f"  ✓ Converted: {result['ttf']} (original removed)")
    elif result["status"] == "skipped_exists":
        print(f"  ⚠ Skipped: {result['ttf']} (already exists)")
    elif result["status"] == "skipped_already_ttf":
        print(f"  ⚠ Skipped: {result['otf']} (already has TrueType outlines)")
    else:
        error_msg = result.get("error", "Unknown error")
        print(f"  ✗ Failed: {result['otf']} - {error_msg}")

    return result


def main():
    """Main function to convert all OTF files to TTF using multiprocessing."""
    # Configuration
    root_dir = Path.cwd()
    num_workers = 6

    print(f"Searching for OTF files in: {root_dir}")
    otf_files = find_otf_files(root_dir)

    if not otf_files:
        print("No OTF files found.")
        return

    print(f"Found {len(otf_files)} OTF file(s)")
    print(f"Using {num_workers} worker processes")
    print("Original OTF files will be removed after successful conversion\n")

    # Prepare arguments for multiprocessing
    args = [(path,) for path in otf_files]

    # Process files using multiprocessing pool
    with Pool(processes=num_workers) as pool:
        results = pool.map(process_file, args)

    # Generate summary
    summary = {"total": len(results), "success": 0, "skipped_exists": 0, "skipped_already_ttf": 0, "failed": 0}

    for result in results:
        if result["status"] == "success":
            summary["success"] += 1
        elif result["status"] == "skipped_exists":
            summary["skipped_exists"] += 1
        elif result["status"] == "skipped_already_ttf":
            summary["skipped_already_ttf"] += 1
        else:
            summary["failed"] += 1

    # Print summary
    print("\n" + "=" * 50)
    print("Conversion Summary:")
    print(f"  Total OTF files found: {summary['total']}")
    print(f"  Successfully converted & removed: {summary['success']}")
    print(f"  Skipped (TTF exists): {summary['skipped_exists']}")
    print(f"  Skipped (already TrueType): {summary['skipped_already_ttf']}")
    print(f"  Failed: {summary['failed']}")

    # List failed files
    if summary["failed"] > 0:
        print("\nFailed conversions (original files preserved):")
        for result in results:
            if result["status"] == "failed":
                error = result.get("error", "Unknown error")
                print(f"  ✗ {result['otf']}: {error}")

    return summary


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nConversion interrupted by user.")
        sys.exit(1)
