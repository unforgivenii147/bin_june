#!/data/data/com.termux/files/usr/bin/python

import subprocess
import sys
from pathlib import Path


def extract_subtitles(path) -> None:
    if not path.exists():
        return
    output_path = path.with_suffix(".srt")
    cmd = ["ffmpeg", "-i", str(path), "-map", f"0:s:0", "-y", str(output_path)]
    try:
        subprocess.run(cmd, check=True)
    except:
        print(f"Error")


if __name__ == "__main__":
    fn = Path(sys.argv[1].strip())
    extract_subtitles(fn)
