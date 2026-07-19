#!/data/data/com.termux/files/usr/bin/env python
from __future__ import annotations

import ast
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import libcst as cst

# Create output directories using pathlib
OUTPUT_DIR = Path("output")
FUNCTIONS_DIR = OUTPUT_DIR / "functions"
CLASSES_DIR = OUTPUT_DIR / "classes"
CONSTANTS_DIR = OUTPUT_DIR / "constants"

for directory in [FUNCTIONS_DIR, CLASSES_DIR, CONSTANTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


def validate_python_code(code: str, filename: str) -> bool:
    """Validate Python code using ast.parse."""
    try:
        ast.parse(code)
        return True
    except SyntaxError as e:
        print(f"Syntax error in extracted code of {filename}: {e}")
        return False


class TopLevelExtractor(cst.CSTVisitor):
    def __init__(self, original_path: Path, module: cst.Module):
        super().__init__()
        self.original_path = original_path
        self.module = module
        self.functions: Dict[str, str] = {}
        self.classes: Dict[str, str] = {}
        self.constants: Dict[str, str] = {}
        self.imports: Set[str] = set()

    def save_to_file(self, directory: Path, filename: str, content: str, node_name: str) -> None:
        """Save content to file with validation and automatic deduplication."""
        if not content.strip().endswith("\n"):
            content += "\n\n"

        if not content.startswith(("#!", "# -*-", '"""')):
            content = f"#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\n{content}"

        source_comment = f"# Extracted from: {self.original_path.name}\n"
        if content.startswith('"""'):
            parts = content.split('"""', 2)
            if len(parts) >= 3:
                content = '"""'.join([parts[0], parts[1], source_comment + '"""' + parts[2]])
        else:
            content = source_comment + content

        if validate_python_code(content, node_name):
            base_stem = Path(filename).stem
            filepath = directory / f"{filename}.py"

            counter = 1
            while filepath.exists():
                filepath = directory / f"{base_stem}_{counter}.py"
                counter += 1

            try:
                filepath.write_text(content.strip() + "\n", encoding="utf-8")
            except Exception as e:
                print(f"Error writing to {filepath}: {e}")

    def visit_Import(self, node: cst.Import) -> None:
        self.imports.add(cst.Module([node]).code.strip())

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        self.imports.add(cst.Module([node]).code.strip())

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        if not self._is_top_level(node):
            return

        try:
            # Using cst.Module([node]).code is the safest way to get the block
            # without triggering the 'default_indicator' error
            code = cst.Module([node]).code.strip()
            self.functions[node.name.value] = code
            self.save_to_file(FUNCTIONS_DIR, node.name.value, code, f"function_{node.name.value}")
        except Exception as e:
            print(f"Error extracting function {node.name.value}: {e}")

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        if not self._is_top_level(node):
            return

        try:
            code = cst.Module([node]).code.strip()
            self.classes[node.name.value] = code
            self.save_to_file(CLASSES_DIR, node.name.value, code, f"class_{node.name.value}")
        except Exception as e:
            print(f"Error extracting class {node.name.value}: {e}")

    def visit_Assign(self, node: cst.Assign) -> None:
        if not self._is_top_level(node):
            return

        if node.semicolon:
            return

        try:
            if len(node.targets) == 1 and isinstance(node.targets[0].target, cst.Name):
                name = node.targets[0].target.value
                if name.isidentifier() and name.isupper() and not name.startswith("_"):
                    constant_code = cst.Module([node]).code.strip()
                    if validate_python_code(constant_code, f"constant_{name}"):
                        self.constants[name] = constant_code
                        self.save_to_file(CONSTANTS_DIR, name, constant_code, f"constant_{name}")
        except Exception as e:
            print(f"Error extracting constant: {e}")

    def _is_top_level(self, node) -> bool:
        # We use the parent attribute provided by the MetadataWrapper
        current = node
        while hasattr(current, "parent") and current.parent:
            if isinstance(current.parent, (cst.FunctionDef, cst.ClassDef, cst.If, cst.For, cst.While, cst.With)):
                return False
            current = current.parent
        return True


def process_file(filepath: Path) -> Dict:
    try:
        code = filepath.read_text(encoding="utf-8")
        module = cst.parse_module(code)

        # Use MetadataWrapper to ensure nodes have .parent attributes
        wrapper = cst.metadata.MetadataWrapper(module)

        # Pass the module to the extractor
        extractor = TopLevelExtractor(filepath, module)

        # Visit the wrapped module so that the visitor can access parents
        wrapper.visit(extractor)

        return {
            "filepath": str(filepath),
            "functions": extractor.functions,
            "classes": extractor.classes,
            "constants": extractor.constants,
            "imports": extractor.imports,
            "status": "success",
        }
    except Exception as e:
        return {"filepath": str(filepath), "status": "error", "error": str(e)}


def collect_python_files(root_dir: Path = Path(".")) -> List[Path]:
    return [
        p
        for p in root_dir.rglob("*.py")
        if not any(part.startswith(".") or part == "__pycache__" for part in p.parts) and p.name != Path(__file__).name
    ]


def write_imports_file(all_imports: Set[str]) -> None:
    imports_file = OUTPUT_DIR / "imports.py"

    # Simple sort to group imports
    sorted_imports = sorted(all_imports)

    content = "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n"
    content += "# Combined imports from all processed files\n\n"
    content += "\n".join(sorted_imports)
    content += "\n"

    try:
        imports_file.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"Error writing imports file: {e}")


def main() -> None:
    python_files = collect_python_files()
    if not python_files:
        print("No Python files found to process.")
        return

    print(f"Found {len(python_files)} Python file(s) to process...")

    all_imports: Set[str] = set()
    processed_files = 0
    total_functions = 0
    total_classes = 0
    total_constants = 0
    error_files = []

    max_workers = min(os.cpu_count() or 1, len(python_files))

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(process_file, filepath): filepath for filepath in python_files}

        try:
            for future in as_completed(future_to_file):
                filepath = future_to_file[future]
                try:
                    result = future.result()
                    if result["status"] == "success":
                        processed_files += 1
                        total_functions += len(result["functions"])
                        total_classes += len(result["classes"])
                        total_constants += len(result["constants"])
                        all_imports.update(result["imports"])
                        print(f"✓ Processed [{processed_files}/{len(python_files)}]: {result['filepath']}")
                    else:
                        error_files.append((result["filepath"], result.get("error")))
                        print(f"✗ Error processing {result['filepath']}: {result.get('error')}")
                except Exception as e:
                    error_files.append((str(filepath), str(e)))
                    print(f"✗ Unexpected error processing {filepath}: {e}")
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            executor.shutdown(wait=False)

    if all_imports:
        write_imports_file(all_imports)

    print("\n" + "=" * 70)
    print(f"Extraction Complete!\nFiles: {processed_files}/{len(python_files)}")
    print(f"Functions: {total_functions} | Classes: {total_classes} | Constants: {total_constants}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
