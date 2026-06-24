#!/data/data/com.termux/files/usr/bin/python
"""
run_script.py - Run a CLI app over all files with a specific extension in current directory
Usage: python run_script.py <extension> <cli_app> [args...]
Example: python run_script.py .svg svgo
         python run_script.py .svg svgo -c config.json -o output/
"""

import os
import subprocess
import sys
from functools import partial
from multiprocessing import Pool, cpu_count
from pathlib import Path


def process_file(cli_app, cli_args, file_path):
    """
    Process a single file with the CLI app
    """
    try:
        # Build command with file path as argument
        # Assuming the CLI app takes the file as the last argument
        # If you need to place file in a specific position, modify here
        cmd = [cli_app] + cli_args + [str(file_path)]

        # Run the command
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            return f"✅ Processed: {file_path.name}"
        else:
            return f"❌ Failed: {file_path.name} - {result.stderr.strip()}"

    except Exception as e:
        return f"❌ Error processing {file_path.name}: {str(e)}"


def main():
    # Check minimum arguments
    if len(sys.argv) < 3:
        print("Usage: python run_script.py <extension> <cli_app> [args...]")
        print("Example: python run_script.py .svg svgo")
        print("         python run_script.py .svg svgo -c config.json -o output/")
        sys.exit(1)

    # Parse arguments
    extension = sys.argv[1]
    cli_app = sys.argv[2]
    cli_args = sys.argv[3:]  # Any additional arguments

    # Validate extension
    if not extension.startswith("."):
        print(f"Error: Extension must start with '.', got '{extension}'")
        sys.exit(1)

    # Get current directory
    current_dir = Path.cwd()

    # Find all files with the given extension (non-recursive)
    files = list(current_dir.glob(f"*{extension}"))

    if not files:
        print(f"No *{extension} files found in {current_dir}")
        sys.exit(0)

    print(f"Found {len(files)} *{extension} files in {current_dir}")
    print(f"Processing with: {cli_app} {' '.join(cli_args)}")
    print("-" * 50)

    # Use multiprocessing for parallel processing
    # Use 75% of available CPU cores to avoid overloading
    num_processes = max(1, int(cpu_count() * 0.75))

    # Create a partial function with fixed arguments
    process_func = partial(process_file, cli_app, cli_args)

    # Process files in parallel
    with Pool(processes=num_processes) as pool:
        results = pool.map(process_func, files)

    # Print results
    print("-" * 50)
    print("\n".join(results))

    # Count successes and failures
    success_count = sum(1 for r in results if r.startswith("✅"))
    failure_count = len(results) - success_count

    print("-" * 50)
    print(f"Summary: {success_count} successful, {failure_count} failed")


if __name__ == "__main__":
    main()
