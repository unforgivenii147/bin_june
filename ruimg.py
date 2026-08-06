#!/data/data/com.termux/files/home/.local/bin/python
"""
Extract Russian and English text from images using OCR.
Supports parallel processing of multiple directories.
"""
import argparse
import sys
from pathlib import Path
from multiprocessing import Pool, cpu_count
from dataclasses import dataclass
from typing import Optional
import json
from datetime import datetime
try:
    import pytesseract
    from PIL import Image
except ImportError:
    print("Error: Required packages not installed.")
    print("Install with: pip install pillow pytesseract")
    sys.exit(1)
@dataclass
class ExtractionResult:
    """Result of text extraction from a single image."""
    file_path: Path
    success: bool
    text: str = ""
    error: str = ""
    char_count: int = 0
    line_count: int = 0
class TextExtractor:
    """Extract text from images using Tesseract OCR."""
    # Supported image extensions
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp", ".gif"}
    @staticmethod
    def extract_from_image(image_path: Path) -> ExtractionResult:
        """
        Extract Russian and English text from an image.
        Args:
            image_path: Path to the image file
        Returns:
            ExtractionResult with extracted text and statistics
        """
        try:
            if not image_path.exists():
                return ExtractionResult(file_path=image_path, success=False, error=f"File not found")
            # Open and extract text using Tesseract
            # Language config: 'rus' for Russian, 'eng' for English
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang="rus+eng")
            if not text.strip():
                return ExtractionResult(file_path=image_path, success=True, text="", char_count=0, line_count=0)
            char_count = len(text)
            line_count = len(text.strip().split("\n"))
            return ExtractionResult(
                file_path=image_path, success=True, text=text, char_count=char_count, line_count=line_count
            )
        except Exception as e:
            return ExtractionResult(file_path=image_path, success=False, error=str(e))
    @staticmethod
    def find_images(directories: list[Path]) -> list[Path]:
        """
        Recursively find all image files in given directories.
        Args:
            directories: List of directory paths to search
        Returns:
            List of image file paths
        """
        images = []
        for directory in directories:
            if not directory.is_dir():
                print(f"⚠ Warning: {directory} is not a directory, skipping")
                continue
            for ext in TextExtractor.IMAGE_EXTENSIONS:
                images.extend(directory.rglob(f"*{ext}"))
                images.extend(directory.rglob(f"*{ext.upper()}"))
        return sorted(set(images))  # Remove duplicates and sort
class TextExtractionReport:
    """Generate formatted reports for extraction results."""
    @staticmethod
    def print_header(total_files: int) -> None:
        """Print report header."""
        print("\n" + "=" * 80)
        print(f"📄 TEXT EXTRACTION REPORT")
        print(f"⏱  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Total files to process: {total_files}")
        print("=" * 80 + "\n")
    @staticmethod
    def print_file_result(result: ExtractionResult, rel_path: Path) -> None:
        """Print result for a single file."""
        if result.success:
            status = "✓ SUCCESS"
            stats = f"│ Characters: {result.char_count:,} | Lines: {result.line_count}"
        else:
            status = "✗ ERROR"
            stats = f"│ Error: {result.error}"
        print(f"{status:12} │ {rel_path}")
        print(f"{stats}")
        print()
    @staticmethod
    def print_summary(results: list[ExtractionResult], base_paths: list[Path]) -> None:
        """Print extraction summary statistics."""
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        total_chars = sum(r.char_count for r in results if r.success)
        total_lines = sum(r.line_count for r in results if r.success)
        print("=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"✓ Successful: {successful}/{len(results)}")
        print(f"✗ Failed:     {failed}/{len(results)}")
        print(f"📝 Total characters extracted: {total_chars:,}")
        print(f"📄 Total lines extracted:      {total_lines:,}")
        print("=" * 80 + "\n")
    @staticmethod
    def save_json_report(results: list[ExtractionResult], output_path: Path) -> None:
        """Save detailed results to JSON file."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_files": len(results),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "results": [
                {
                    "file": str(r.file_path),
                    "success": r.success,
                    "char_count": r.char_count,
                    "line_count": r.line_count,
                    "error": r.error if not r.success else None,
                    "preview": r.text[:200] if r.text else "",
                }
                for r in results
            ],
        }
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"📋 Detailed report saved to: {output_path}")
def process_image_worker(image_path: Path) -> ExtractionResult:
    """Worker function for multiprocessing."""
    return TextExtractor.extract_from_image(image_path)
def main():
    parser = argparse.ArgumentParser(
        description="Extract Russian and English text from images using OCR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Process current directory recursively
  %(prog)s /path/to/dir1 /path/to/dir2  # Process multiple directories
  %(prog)s . --workers 4            # Use 4 parallel workers
  %(prog)s . --json report.json     # Save detailed report to JSON
        """,
    )
    parser.add_argument(
        "directories",
        nargs="*",
        type=Path,
        default=[Path.cwd()],
        help="Directories to process (default: current directory)",
    )
    parser.add_argument(
        "-w", "--workers", type=int, default=cpu_count(), help=f"Number of parallel workers (default: {cpu_count()})"
    )
    parser.add_argument("-j", "--json", type=Path, help="Save detailed report to JSON file")
    parser.add_argument("-s", "--silent", action="store_true", help="Suppress file-by-file output (summary only)")
    args = parser.parse_args()
    # Convert to absolute paths
    directories = [d.resolve() for d in args.directories]
    # Find all images
    print("🔍 Scanning for images...")
    images = TextExtractor.find_images(directories)
    if not images:
        print("❌ No images found in the specified directories.")
        return 1
    print(f"✓ Found {len(images)} image(s)\n")
    # Process images in parallel
    print(f"⚙️  Processing with {args.workers} worker(s)...\n")
    if not args.silent:
        TextExtractionReport.print_header(len(images))
    with Pool(processes=args.workers) as pool:
        results = pool.map(process_image_worker, images)
    # Print individual results
    if not args.silent:
        for result, img_path in zip(results, images):
            # Calculate relative path from base directory
            try:
                rel_path = img_path.relative_to(Path.cwd())
            except ValueError:
                rel_path = img_path
            TextExtractionReport.print_file_result(result, rel_path)
    # Print summary
    TextExtractionReport.print_summary(results, directories)
    # Save JSON report if requested
    if args.json:
        TextExtractionReport.save_json_report(results, args.json)
    return 0
if __name__ == "__main__":
    sys.exit(main())
