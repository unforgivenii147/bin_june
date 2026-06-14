#!/data/data/com.termux/files/usr/bin/python

import os
import subprocess
from pathlib import Path


def extract_subtitles(input_file: str, output_file=None, subtitle_index=0) -> None:
    if not Path(input_file).exists():
        raise FileNotFoundError(msg)
    if output_file is None:
        output_file = os.path.splitext(input_file)[0] + ".srt"
    cmd = ["ffmpeg", "-i", input_file, "-map", f"0:s:{subtitle_index}", "-y", output_file]
    try:
        subprocess.run(cmd, check=True)
        print(f"Subtitles extracted to: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error extracting subtitles: {e}")


extract_subtitles("your_movie.mkv")
