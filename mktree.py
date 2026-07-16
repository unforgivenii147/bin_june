#!/data/data/com.termux/files/usr/bin/env python
import argparse
import re
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import List, Tuple

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

try:
    import pytesseract
    from PIL import Image

    PHOTO_SUPPORT = True
except ImportError:
    PHOTO_SUPPORT = False


class DirectoryBuilder:
    TREE_CHARS = {"├──": "├", "└──": "└", "│": "│", " ": " "}

    def __init__(self, use_multiprocessing: bool = True):
        self.use_multiprocessing = use_multiprocessing
        self.items_to_create: List[Tuple[Path, bool]] = []

    def read_tree_file(self, filepath: str) -> List[str]:
        tree_file = Path(filepath)
        if not tree_file.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        lines = []
        with open(tree_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].rstrip()
                if line.strip():
                    lines.append(line)
        return lines

    def read_from_photo(self, image_path: str) -> List[str]:
        if not PHOTO_SUPPORT:
            raise ImportError("""Photo support requires: pip install Pillow pytesseract
Also install tesseract: https://github.com/UB-Mannheim/tesseract/wiki""")
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            return text.split("\n")
        except Exception as e:
            raise ValueError(f"Failed to extract text from photo: {e}")

    def parse_tree_lines(self, lines: List[str]) -> List[Tuple[Path, bool]]:
        items = []
        stack = [Path(".")]
        for line in lines:
            depth = self._calculate_depth(line)
            name = self._extract_name(line)
            if not name:
                continue
            while len(stack) > depth + 1:
                stack.pop()
            is_file = self._is_file(name)
            current_path = stack[-1] / name
            items.append((current_path, is_file))
            if not is_file:
                stack.append(current_path)
        self.items_to_create = items
        return items

    def _calculate_depth(self, line: str) -> int:
        depth = 0
        i = 0
        while i < len(line):
            if line[i : i + 3] in ["├──", "└──"]:
                return depth
            elif line[i : i + 2] == "│ " or line[i : i + 2] == "  ":
                depth += 0.5 if line[i : i + 2] == "│ " else 0.5
                i += 2
            else:
                i += 1
        return int(depth)

    def _extract_name(self, line: str) -> str:
        cleaned = re.sub(r"[├└│─\s]+", "", line)
        return cleaned.strip()

    def _is_file(self, name: str) -> bool:
        if "/" in name:
            return True
        return "." in name.split("/")[-1]

    @staticmethod
    def _create_item(item_data: Tuple[Path, bool]) -> Tuple[Path, bool, str]:
        path, is_file = item_data
        try:
            if is_file:
                if "/" in str(path.name):
                    files = [f.strip() for f in str(path.name).split("/")]
                    for fname in files:
                        path = path.parent / fname
                        path.touch()
                        return path, is_file, "created"
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                    return path, is_file, "created"
            else:
                path.mkdir(parents=True, exist_ok=True)
                return path, is_file, "created"
        except Exception as e:
            return path, is_file, f"error: {e}"

    def create_structure(self, base_dir: str = ".", num_workers: int = None) -> None:
        if not self.items_to_create:
            print("No items to create. Parse tree first.")
            return
        base_path = Path(base_dir)
        base_path.mkdir(parents=True, exist_ok=True)
        items = [(base_path / item[0], item[1]) for item in self.items_to_create]
        if self.use_multiprocessing and num_workers is None:
            num_workers = max(1, cpu_count() - 1)
        print(f"Creating {len(items)} items...")
        if self.use_multiprocessing and num_workers > 1:
            with Pool(num_workers) as pool:
                results = pool.map(self._create_item, items)
        else:
            results = [self._create_item(item) for item in items]
        created = sum(1 for _, _, status in results if status == "created")
        errors = [r for r in results if "error" in r[2]]
        print(f"✓ Created: {created} items")
        if errors:
            print(f"✗ Errors: {len(errors)}")
            for path, _, status in errors:
                print(f"  - {path}: {status}")

    def print_structure(self) -> None:
        for path, is_file in self.items_to_create:
            marker = "📄" if is_file else "📁"
            depth = len(path.parts) - 1
            indent = "  " * depth
            print(f"{indent}{marker} {path.name}")


def main():
    parser = argparse.ArgumentParser(description="Build directory structure from tree.txt or photo")
    parser.add_argument(
        "source",
        nargs="?",
        default="tree.txt",
        help="Path to tree.txt file or photo (default: tree.txt)",
    )
    parser.add_argument("-o", "--output", default=".", help="Output directory (default: current directory)")
    parser.add_argument(
        "-j",
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes (default: cpu_count - 1)",
    )
    parser.add_argument("--no-multiprocessing", action="store_true", help="Disable multiprocessing")
    parser.add_argument("--preview", action="store_true", help="Preview structure without creating")
    args = parser.parse_args()
    builder = DirectoryBuilder(use_multiprocessing=not args.no_multiprocessing)
    source_path = Path(args.source)
    print(f"Reading from: {args.source}")
    if source_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp", ".gif"]:
        print("Detected photo format. Using OCR...")
        lines = builder.read_from_photo(args.source)
    else:
        lines = builder.read_tree_file(args.source)
    print(f"Found {len(lines)} lines")
    items = builder.parse_tree_lines(lines)
    print(f"Parsed {len(items)} items")
    if args.preview:
        print("\nPreview:")
        builder.print_structure()
    else:
        builder.create_structure(args.output, args.workers)
        print(f"\n✓ Directory structure created in: {args.output}")


if __name__ == "__main__":
    main()
