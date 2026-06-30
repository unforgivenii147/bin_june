#!/data/data/com.termux/files/usr/bin/env python
"""
Delete a file from a tar.zst archive
Usage: python script.py <archive.tar.zst> <file-to-delete>
"""

import sys
import os
import tarfile
import zstandard as zstd
import tempfile
import shutil


def delete_from_tar_zst(archive_path, file_to_delete):
    """Delete a file from a tar.zst archive"""

    if not os.path.exists(archive_path):
        print(f"Error: Archive '{archive_path}' not found", file=sys.stderr)
        sys.exit(1)

    # Create output filename
    base, ext = os.path.splitext(archive_path)
    if ext == ".zst":
        output_path = f"{base}_modified.tar.zst"
    else:
        output_path = f"{archive_path}_modified"

    print(f"Reading archive: {archive_path}")
    print(f"Deleting: {file_to_delete}")

    # Read compressed data
    with open(archive_path, "rb") as f:
        compressed_data = f.read()

    # Decompress
    decompressor = zstd.ZstdDecompressor()
    tar_data = decompressor.decompress(compressed_data)

    # Use temporary file for tar operations
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tar") as tmp_tar:
        tmp_tar.write(tar_data)
        tmp_path = tmp_tar.name

    try:
        # Delete from tar
        with tarfile.open(tmp_path, "r:") as tar:
            members = tar.getmembers()
            found = False

            # Check if file exists
            for member in members:
                if member.name == file_to_delete:
                    found = True
                    break

            if not found:
                print(f"Warning: '{file_to_delete}' not found in archive", file=sys.stderr)
                # Still create output with original content
                shutil.copy2(archive_path, output_path)
                print(f"Original archive copied to: {output_path}")
                return

            # Create new tar without the file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tar") as new_tar:
                with tarfile.open(new_tar.name, "w") as new_tarf:
                    for member in members:
                        if member.name != file_to_delete:
                            # Extract and add member
                            f = tar.extractfile(member)
                            if f is not None:
                                new_tarf.addfile(member, f)
                            else:
                                new_tarf.addfile(member)
                new_tar_path = new_tar.name

            # Read new tar data
            with open(new_tar_path, "rb") as f:
                new_tar_data = f.read()
            os.unlink(new_tar_path)

        # Compress with zstandard
        compressor = zstd.ZstdCompressor(level=3)
        compressed_output = compressor.compress(new_tar_data)

        # Write output
        with open(output_path, "wb") as f:
            f.write(compressed_output)

        print(f"✅ Success! New archive created: {output_path}")
        print(f"   Size: {os.path.getsize(output_path)} bytes")

    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py <archive.tar.zst> <file-to-delete>")
        print("Example: python script.py archive.tar.zst 0/document.pdf")
        sys.exit(1)

    archive_path = sys.argv[1]
    file_to_delete = sys.argv[2]

    delete_from_tar_zst(archive_path, file_to_delete)


if __name__ == "__main__":
    main()
