#!/data/data/com.termux/files/home/.local/bin/python
"""
Extract constant definitions from Python files recursively.
Saves each unique constant to a separate file in the output directory.

Usage:
    python extract_constants.py [source_dir] [output_dir] [--include-extensionless]
"""

import argparse
import ast
import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Set, Tuple

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn

console = Console()


def is_constant_name(name: str) -> bool:
    """Check if a variable name follows Python constant naming convention."""
    return bool(re.match(r"^[A-Z][A-Z0-9_]*$", name))


def looks_like_python_file(file_path: Path) -> bool:
    """Determine if a file without .py extension is likely a Python script."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            first_line = f.readline().strip()
            if first_line.startswith("#!") and "python" in first_line.lower():
                return True

            content = f.read(4096)
            if not content:
                return False

            python_patterns = [
                r"^\s*(import|from)\s+\w+",
                r"^\s*def\s+\w+\s*\(",
                r"^\s*class\s+\w+",
                r"^\s*if\s+__name__\s*==",
                r"^\s*print\s*\(",
                r"^\s*#.*python",
            ]

            for pattern in python_patterns:
                if re.search(pattern, content, re.MULTILINE):
                    return True

            try:
                ast.parse(content)
                return True
            except SyntaxError:
                return False

    except (IOError, UnicodeDecodeError):
        return False


def find_python_files(directory: Path, include_extensionless: bool = False) -> List[Path]:
    """Recursively find Python files in the given directory."""
    python_files = list(directory.rglob("*.py"))

    if include_extensionless:
        all_files = [f for f in directory.rglob("*") if f.is_file()]
        extensionless_files = [f for f in all_files if f.suffix == "" and f.name != "LICENSE" and f.name != "README"]

        for file_path in extensionless_files:
            if looks_like_python_file(file_path):
                python_files.append(file_path)

    return python_files


def extract_constants_from_file(file_path: Path) -> Tuple[Path, Dict[str, str]]:
    """Extract constant definitions from a single Python file."""
    constants = {}
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content)

        for node in ast.walk(tree):
            # Handle module-level assignments
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and is_constant_name(target.id):
                        try:
                            value = ast.literal_eval(node.value)
                            constants[target.id] = repr(value)
                        except (ValueError, SyntaxError):
                            try:
                                constants[target.id] = ast.unparse(node.value)
                            except AttributeError:
                                constants[target.id] = "UNKNOWN"

            # Handle annotated assignments
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and is_constant_name(node.target.id):
                    if node.value is not None:
                        try:
                            value = ast.literal_eval(node.value)
                            constants[node.target.id] = repr(value)
                        except (ValueError, SyntaxError):
                            try:
                                constants[node.target.id] = ast.unparse(node.value)
                            except AttributeError:
                                constants[node.target.id] = "UNKNOWN"

        return file_path, constants

    except (SyntaxError, UnicodeDecodeError) as e:
        console.print(f"[yellow]Warning:[/yellow] Could not parse {file_path}: {e}")
        return file_path, {}
    except Exception as e:
        console.print(f"[red]Error:[/red] Processing {file_path}: {e}")
        return file_path, {}


def process_files_parallel(files: List[Path], max_workers: int = None) -> Dict[Path, Dict[str, str]]:
    """Process multiple files in parallel using ProcessPoolExecutor."""
    results = {}

    if not files:
        return results

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(extract_constants_from_file, file_path): file_path for file_path in files}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Processing Python files...", total=len(files))

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    _, constants = future.result()
                    if constants:
                        results[file_path] = constants
                except Exception as e:
                    console.print(f"[red]Error processing {file_path}: {e}[/red]")

                progress.update(task, advance=1)

    return results


def save_constants_separately(all_constants: Dict[Path, Dict[str, str]], output_dir: Path) -> None:
    """
    Save each unique constant to its own file in the output directory.

    Output structure:
    output_dir/
        CONSTANT_NAME.py
        ANOTHER_CONSTANT.py
        ...

    Each file contains:
        CONSTANT_NAME = value
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect unique constants with their values
    unique_constants: Dict[str, Set[str]] = {}

    for file_path, constants in all_constants.items():
        for name, value in constants.items():
            if name not in unique_constants:
                unique_constants[name] = set()
            unique_constants[name].add(value)

    # Save each constant to its own file
    for name, values in unique_constants.items():
        # Sanitize filename (remove any invalid characters)
        safe_name = re.sub(r"[^\w\-.]", "_", name)
        file_path = output_dir / f"{safe_name}.py"

        # If multiple values exist for the same constant name,
        # save the first one (or you could save all values as a list)
        value = sorted(values)[0] if values else "None"

        # Write the constant definition
        content = f"{name} = {value}\n"
        file_path.write_text(content, encoding="utf-8")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Extract constants from Python files recursively")
    parser.add_argument(
        "source_dir", nargs="?", default=".", help="Source directory to scan (default: current directory)"
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="output",
        help="Output directory for results (default: constants_output)",
    )
    parser.add_argument(
        "--include-extensionless", action="store_true", help="Include Python files without .py extension"
    )
    parser.add_argument("--max-workers", type=int, default=8, help="Maximum number of parallel workers")

    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)

    # Validate source directory
    if not source_dir.exists():
        console.print(f"[red]Error:[/red] Source directory '{source_dir}' does not exist.")
        sys.exit(1)

    if not source_dir.is_dir():
        console.print(f"[red]Error:[/red] '{source_dir}' is not a directory.")
        sys.exit(1)

    console.print(f"[bold cyan]Extracting constants from:[/bold cyan] {source_dir}")
    console.print(f"[bold cyan]Output directory:[/bold cyan] {output_dir}")
    if args.include_extensionless:
        console.print("[bold cyan]Including extensionless Python files[/bold cyan]")
    console.print()

    # Find all Python files
    console.print("[bold]Finding Python files...[/bold]")
    python_files = find_python_files(source_dir, include_extensionless=args.include_extensionless)
    console.print(f"Found [green]{len(python_files)}[/green] Python files\n")

    if not python_files:
        console.print("[yellow]No Python files found.[/yellow]")
        return

    # Process files in parallel
    console.print("[bold]Processing files in parallel...[/bold]")
    all_constants = process_files_parallel(python_files, args.max_workers)

    # Save constants to separate files
    console.print("\n[bold]Saving constants to separate files...[/bold]")
    save_constants_separately(all_constants, output_dir)

    # Count and display results
    total_constants = sum(len(constants) for constants in all_constants.values())
    unique_names = set()
    for constants in all_constants.values():
        unique_names.update(constants.keys())

    console.print(
        f"\n[green]✓[/green] Extracted [bold]{total_constants}[/bold] constants "
        f"([bold]{len(unique_names)}[/bold] unique)"
    )
    console.print(f"[green]✓[/green] Saved to: [bold]{output_dir}[/bold]")


if __name__ == "__main__":
    main()
