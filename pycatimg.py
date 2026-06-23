#!/data/data/com.termux/files/usr/bin/python

"""
catimg - Display images in terminal with true color support (including SVG)
"""

import argparse
import io
import os
import sys

# Try to import SVG support
from cairosvg import svg2png
from PIL import Image
from PIL.ImageFile import ImageFile

SVG_SUPPORT = True


def resize_image(img: ImageFile, terminal_width: int, terminal_height: int, max_width=None, max_height=None):
    """Resize image based on terminal dimensions and constraints"""
    orig_width, orig_height = img.size

    # Calculate target dimensions
    if max_width and max_height:
        target_width = min(max_width, terminal_width)
        target_height = min(max_height, terminal_height)
    else:
        target_width = terminal_width
        target_height = terminal_height

    # Maintain aspect ratio
    aspect = orig_height / orig_width
    new_width = target_width
    new_height = int(target_width * aspect)

    if new_height > target_height:
        new_height = target_height
        new_width = int(target_height / aspect)

    # Ensure at least 1x1
    new_width = max(1, new_width)
    new_height = max(1, new_height)

    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def load_svg(svg_path, width=None, height=None) -> ImageFile:
    """Load SVG file and convert to PIL Image"""
    if not SVG_SUPPORT:
        print("Error: SVG support requires 'cairosvg' library. Install with: pip install cairosvg", file=sys.stderr)
        sys.exit(1)

    try:
        # Get terminal size if dimensions not specified
        if not width or not height:
            term_width, term_height = get_terminal_size()
            # Half-block mode doubles vertical resolution
            term_height *= 2
            width = width or term_width
            height = height or term_height

        # Convert SVG to PNG in memory
        png_data = svg2png(url=svg_path, output_width=width, output_height=height)

        # Load PNG data into PIL Image
        img = Image.open(io.BytesIO(png_data))
        return img

    except Exception as e:
        print(f"Error loading SVG: {e}", file=sys.stderr)
        sys.exit(1)


def load_image(image_path, width=None, height=None) -> ImageFile:
    """Load image from file (supports PNG, JPEG, GIF, BMP, SVG)"""
    # Check if it's an SVG file
    if image_path.lower().endswith(".svg"):
        return load_svg(image_path, width, height)

    # For other formats, use PIL directly
    try:
        return Image.open(image_path)
    except Exception as e:
        print(f"Error loading image: {e}", file=sys.stderr)
        sys.exit(1)


def rgb_to_ansi(r, g, b) -> str:
    """Convert RGB to ANSI true color escape sequence"""
    return f"\033[38;2;{r};{g};{b}m"


def image_to_ansi(img) -> str:
    """Convert PIL Image to ANSI colored string"""
    img = img.convert("RGB")
    width, height = img.size

    output_lines = []

    for y in range(height):
        line = []
        for x in range(width):
            r, g, b = img.getpixel((x, y))
            line.append(f"{rgb_to_ansi(r, g, b)}██")
        output_lines.append("".join(line))

    # Add reset code at the end
    output = "\n".join(output_lines) + "\033[0m"
    return output


def image_to_ansi_blocks(img) -> str:
    """Convert image using half-block characters (▀) for better vertical resolution"""
    img = img.convert("RGB")
    width, height = img.size

    # Ensure even height for proper half-block rendering
    if height % 2 != 0:
        # Pad with a transparent/black row if needed
        new_img = Image.new("RGB", (width, height + 1), (0, 0, 0))
        new_img.paste(img, (0, 0))
        img = new_img
        height += 1

    output_lines = []

    for y in range(0, height, 2):
        line = []
        for x in range(width):
            # Get top and bottom pixel colors
            r1, g1, b1 = img.getpixel((x, y))
            r2, g2, b2 = img.getpixel((x, y + 1)) if y + 1 < height else (0, 0, 0)

            # Use half-block character with foreground for top, background for bottom
            line.append(f"\033[38;2;{r1};{g1};{b1}m\033[48;2;{r2};{g2};{b2}m▀")

        output_lines.append("".join(line))

    output = "\n".join(output_lines) + "\033[0m"
    return output


def get_terminal_size() -> tuple[int, int]:
    """Get terminal width and height in characters"""
    try:
        columns, rows = os.get_terminal_size()
        return columns, rows
    except:
        return 80, 24


def catimg(image_path, width=None, height=None, use_half_blocks=True, dpi=96, bg_color=None) -> None:
    """Display image in terminal"""
    # Check if file exists
    if not os.path.exists(image_path):
        print(f"Error: File '{image_path}' not found", file=sys.stderr)
        sys.exit(1)

    try:
        # Get terminal size
        term_width, term_height = get_terminal_size()

        # Adjust term_height for half-block mode (each character shows 2 rows)
        if use_half_blocks:
            term_height *= 2

        # Calculate dimensions for SVG rendering
        render_width = None
        render_height = None

        if width or height:
            # Apply constraints
            if width:
                render_width = min(width, term_width)
            if height:
                render_height = min(height, term_height)
        else:
            render_width = term_width
            render_height = term_height

        # Load image (handles SVG specially)
        if image_path.lower().endswith(".svg"):
            img = load_svg(image_path, render_width, render_height)
        else:
            img = load_image(image_path)
            # Resize for non-SVG images
            img = resize_image(img, term_width, term_height, width, height)

        # Convert to ANSI
        if use_half_blocks:
            output = image_to_ansi_blocks(img)
        else:
            output = image_to_ansi(img)

        print(output)

    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Display images in terminal with true color support (including SVG)",
        epilog="Supports: PNG, JPEG, GIF, BMP, TIFF, SVG (requires cairosvg)",
    )

    parser.add_argument("image", help="Path to image file (supports SVG)")
    parser.add_argument("-w", "--width", type=int, help="Maximum width in characters")
    parser.add_argument("-H", "--height", type=int, help="Maximum height in characters")
    parser.add_argument(
        "--no-half-blocks", action="store_true", help="Disable half-block characters (lower vertical resolution)"
    )
    parser.add_argument("--dpi", type=int, default=96, help="DPI for SVG rendering (default: 96)")
    parser.add_argument("--bg-color", help='Background color for transparent areas (e.g., "black" or "#000000")')

    args = parser.parse_args()

    # Check SVG support if needed
    if args.image.lower().endswith(".svg") and not SVG_SUPPORT:
        print("Warning: SVG support requires 'cairosvg'. Install with:", file=sys.stderr)
        print("  pip install cairosvg", file=sys.stderr)
        print("\nFor system dependencies (Linux):", file=sys.stderr)
        print("  Ubuntu/Debian: sudo apt-get install libcairo2-dev", file=sys.stderr)
        print("  Fedora: sudo dnf install cairo-devel", file=sys.stderr)
        print("Arch: sudo pacman -S cairo", file=sys.stderr)
        sys.exit(1)

    catimg(args.image, args.width, args.height, use_half_blocks=not args.no_half_blocks)


if __name__ == "__main__":
    main()
