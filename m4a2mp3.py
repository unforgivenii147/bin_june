#!/data/data/com.termux/files/usr/bin/env python
import sys
import os
from pathlib import Path
from dh import runcmd


def convert_m4a_to_mp3(input_file, bitrate="64k"):
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    # Check if it's an M4A file
    if not input_file.lower().endswith(".m4a"):
        print(f"Warning: Input file doesn't have .m4a extension. Proceeding anyway...")

    # Generate output filename
    input_path = Path(input_file)
    output_file = str(input_path.with_suffix(".mp3"))

    print(f"Converting: {input_file}")
    print(f"Output: {output_file}")
    print(f"Bitrate: {bitrate}")

    # FFmpeg command
    cmd = [
        "ffmpeg",
        "-i",
        input_file,
        "-codec:a",
        "libmp3lame",  # MP3 encoder
        "-b:a",
        bitrate,  # Audio bitrate
        "-vn",  # No video
        "-y",  # Overwrite output file without asking
        output_file,
    ]

    try:
        # Run the conversion
        ret, txt, err = runcmd(cmd, show_output=True)
        if not ret:
            print(f"Successfully converted to: {output_file}")

        # Show file sizes
        input_size = os.path.getsize(input_file) / (1024 * 1024)  # MB
        output_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
        print(f"Input size: {input_size:.2f} MB")
        print(f"Output size: {output_size:.2f} MB")
        print(f"Size ratio: {output_size / input_size:.1%}")

    except subprocess.CalledProcessError as e:
        print(f"Error during conversion:")
        print(e.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: ffmpeg not found. Please install ffmpeg first.")
        print("Ubuntu/Debian: sudo apt install ffmpeg")
        print("macOS: brew install ffmpeg")
        print("Windows: Download from https://ffmpeg.org/download.html")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <input_file.m4a>")
        print("Example: python script.py song.m4a")
        sys.exit(1)

    input_file = sys.argv[1]
    convert_m4a_to_mp3(input_file, bitrate="64k")
