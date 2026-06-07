#!/data/data/com.termux/files/usr/bin/python

import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python extract_subtitles.py <input_file>")
    sys.exit(1)
input_file = sys.argv[1]
output_dir = "subtitles"
if not Path(output_dir).exists():
    Path(output_dir).mkdir(parents=True)
command = f"ffmpeg -i {input_file} -map_metadata:s:0 -o sub.srt"
subprocess.run(command, check=False, shell=True)
