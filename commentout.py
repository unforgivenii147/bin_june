#!/data/data/com.termux/files/home/.local/bin/python
import sys
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from concurrent.futures import ProcessPoolExecutor

# Mapping of extensions to their comment characters
COMMENT_MAP = {
    ".lua": "--",
    ".py": "#",
    ".sh": "#",
    ".yml": "#",
    ".yaml": "#",
    ".js": "//",
    ".ts": "//",
    ".cpp": "//",
    ".c": "//",
    ".cs": "//",
    ".java": "//",
    ".sql": "--",
    ".rb": "#",
}


def process_chunk(lines, comment_char):
    """
    Worker function to process a block of lines.
    """
    processed = []
    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith(comment_char):
            processed.append(line)
        else:
            processed.append(f"{comment_char}{line}")
    return processed


def main():
    # 1. Argument Validation
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python commentout.py <filename> <start_line> [end_line]")
        sys.exit(1)
    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"Error: File {file_path} not found.")
        sys.exit(1)
    # 2. Determine Comment Character based on extension
    ext = file_path.suffix.lower()
    comment_char = COMMENT_MAP.get(ext)
    if not comment_char:
        # Fallback to # if extension is unknown, but warn the user
        comment_char = "#"
        print(f"Warning: Unknown extension {ext}. Using default '#' as comment char.")
    try:
        start_line = int(sys.argv[2])
        end_line = int(sys.argv[3]) if len(sys.argv) == 4 else None
    except ValueError:
        print("Error: Line numbers must be integers.")
        sys.exit(1)
    # 3. Streaming and Parallel Processing
    # We use a temporary file to avoid loading everything into RAM
    with open(file_path, "r", encoding="utf-8", errors="ignore") as infile:
        with NamedTemporaryFile("w", delete=False, dir=file_path.parent, encoding="utf-8") as temp_file:
            temp_path = Path(temp_file.name)
            current_line_idx = 1
            chunk_size = 10000  # Process 10k lines at a time to balance overhead vs speed
            with ProcessPoolExecutor() as executor:
                while True:
                    # Read a chunk of lines
                    lines = [infile.readline() for _ in range(chunk_size)]
                    # Remove empty strings (which indicate EOF)
                    lines = [l for l in lines if l]
                    if not lines:
                        break
                    # Calculate the range of lines in this current chunk
                    chunk_start = current_line_idx
                    chunk_end = current_line_idx + len(lines) - 1
                    # Determine if this chunk overlaps with the target range
                    # Range check: (ChunkStart <= TargetEnd) AND (ChunkEnd >= TargetStart)
                    target_end = end_line if end_line else float("inf")
                    if chunk_start <= target_end and chunk_end >= start_line:
                        # The chunk needs processing.
                        # To be precise, we split the chunk into: [prefix, target, suffix]
                        # Lines before the target range
                        prefix_count = max(0, start_line - chunk_start)
                        # Lines after the target range
                        suffix_start = max(0, target_end - chunk_start + 1) if end_line else len(lines)
                        prefix = lines[:prefix_count]
                        target_block = lines[prefix_count:suffix_start]
                        suffix = lines[suffix_start:]
                        # Parallelize ONLY the target block
                        future = executor.submit(process_chunk, target_block, comment_char)
                        # Write prefix immediately, then wait for the parallel result
                        temp_file.writelines(prefix)
                        temp_file.writelines(future.result())
                        temp_file.writelines(suffix)
                    else:
                        # No overlap, just write the chunk as is
                        temp_file.writelines(lines)
                    current_line_idx += len(lines)
    # 4. Atomic Swap (In-place update)
    # Replace the original file with the temporary one
    os.replace(temp_path, file_path)
    print(f"Successfully processed {file_path} using '{comment_char}'")


if __name__ == "__main__":
    main()
