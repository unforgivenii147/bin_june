#!/data/data/com.termux/files/usr/bin/python

import os


def split_file(path: str, output_dir: str, chunk_size: int = 5000) -> None:
    if not os.path.exists(path):
        print(f"Error: Input file '{path}' not found.")
        return
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: '{output_dir}'")
    try:
        with open(path, "r", encoding="utf-8") as infile:
            part_num = 0
            while True:
                chunk = infile.read(chunk_size)
                if not chunk:
                    break
                base_name = os.path.basename(path)
                name_without_ext, ext = os.path.splitext(base_name)
                output_filename = f"{name_without_ext}_part_{part_num}{ext}"
                output_path = os.path.join(output_dir, output_filename)
                with open(output_path, "w", encoding="utf-8") as outfile:
                    outfile.write(chunk)
                print(f"Saved part {part_num} to '{output_path}'")
                part_num += 1
        print(f"File splitting complete. {part_num} parts created in '{output_dir}'.")
    except Exception as e:
        print(f"An error occurred during file splitting: {e}")


if __name__ == "__main__":
    import sys

    file_path = sys.argv[1]
    output_directory = "output"
    split_file(file_path, output_directory, chunk_size=5000)
