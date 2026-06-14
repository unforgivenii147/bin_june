#!/data/data/com.termux/files/usr/bin/python

"""
Recursively rename font files based on their internal metadata (name and style).
Uses fontTools to extract font family name and style (Regular, Bold, Italic, etc.).
Usage:
    python rename_fonts.py
Examples:
    asrds.ttf -> Fontello-Regular.ttf
    13543.woff2 -> FontAwesome-Regular.woff2
If the target filename already exists, appends _1, _2, etc. to avoid overwriting.
"""

from pathlib import Path

from dh import FONT_EXT, unique_path
from fontTools.ttLib import TTFont

STYLE_MAPPING = {
    "normal": "Regular",
    "regular": "Regular",
    "bold": "Bold",
    "italic": "Italic",
    "bold italic": "BoldItalic",
    "bolditalic": "BoldItalic",
    "semibold": "SemiBold",
    "light": "Light",
    "thin": "Thin",
    "black": "Black",
    "medium": "Medium",
    "ultra light": "UltraLight",
    "extra bold": "ExtraBold",
    "condensed": "Condensed",
    "extended": "Extended",
    "narrow": "Narrow",
}


def get_font_name_and_style(font_path):
    """Extract font family name and style from a font file using fontTools."""
    ext = font_path.suffix.lower()
    try:
        font = TTFont(font_path)
        name_table = font.get("name")
        if not name_table:
            return (None, None)
        family_name = subfamily_name = None
        for record in name_table.names:
            name_str = record.string.decode("utf-16-be", errors="ignore").strip()
            if not name_str:
                continue
            if record.nameID == 1:
                family_name = name_str
            elif record.nameID == 2:
                subfamily_name = name_str
        font.close()
        style = "Regular"
        if subfamily_name:
            subfamily_lower = subfamily_name.lower().strip()
            for key, value in STYLE_MAPPING.items():
                if key in subfamily_lower:
                    style = value
                    break
            if style == "Regular" and subfamily_name.lower() != "regular":
                style = subfamily_name
        return (family_name, style)
    except Exception as e:
        print(f"  Warning: Could not read {font_path.name}: {e}")
        return (None, None)


def sanitize_filename(name) -> str:
    """Sanitize a string for use as a filename."""
    if not name:
        return "Unknown"
    sanitized = "".join((c if c.isalnum() or c in ("-", "_", " ") else "_" for c in name))
    sanitized = sanitized.replace(" ", "_").strip("_")
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    return sanitized


def rename_font_file(font_path: Path) -> str | None:
    """Rename a single font file based on its metadata."""
    family_name, style = get_font_name_and_style(font_path)
    if not family_name:
        print(f"  Skipping {font_path.name}: Could not extract font family name")
        return None
    family_name = sanitize_filename(family_name)
    style = sanitize_filename(style)
    ext = font_path.suffix
    new_name = f"{family_name}-{style}{ext}"
    new_path = font_path.parent / new_name
    if font_path == new_path:
        print(f"  {font_path.name} -> already has correct name")
        return None
    if new_path.exists():
        new_path = unique_path(new_path)
    try:
        font_path.rename(new_path)
        return new_name
    except Exception as e:
        print(f"  Error renaming {font_path.name}: {e}")
        return None


def process_directory(directory: Path, recursive=True) -> int:
    """Process all font files in a directory (and subdirectories if recursive)."""
    directory = Path(directory)
    renamed_count = 0
    for item in directory.iterdir():
        if item.is_file() and item.suffix.lower() in FONT_EXT:
            new_name = rename_font_file(item)
            if new_name:
                print(f"  {item.name} -> {new_name}")
                renamed_count += 1
        elif item.is_dir() and recursive:
            renamed_count += process_directory(item, recursive)
    return renamed_count


def main() -> None:
    cwd = Path.cwd()
    renamed_count = process_directory(cwd, recursive=True)
    print(f"\n{renamed_count} font file(s).")


if __name__ == "__main__":
    main()
