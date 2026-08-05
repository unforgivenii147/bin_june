#!/data/data/com.termux/files/home/.local/bin/python
"""Extract embedded subtitles from MKV files using py-subtitle-extractor."""

from __future__ import annotations

import sys
from pathlib import Path

from py_subtitle_extractor import extract_subtitle_tracks, extract_subtitles_as_srt

SUB_EXTS = {
    "S_TEXT/UTF8": ".srt",
    "S_TEXT/ASS": ".ass",
    "S_TEXT/SSA": ".ssa",
    "S_TEXT/WEBVTT": ".vtt",
}


def iter_mkv_files(inputs: list[Path]) -> list[Path]:
    if not inputs:
        return sorted(p for p in Path.cwd().rglob("*.mkv") if p.is_file())
    out = []
    for p in inputs:
        if p.is_file() and p.suffix.lower() == ".mkv":
            out.append(p)
        elif p.is_dir():
            out.extend(sorted(x for x in p.rglob("*.mkv") if x.is_file()))
    return out


def safe_name(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    bad = r'<>:"/\|?*\0'
    return "".join("_" if c in bad else c for c in s).strip(" ._")


def exsrt():
    import subprocess

    input_file = sys.argv[1]
    output_file = input_file.replace(".mkv", ".srt")
    command = ["ffmpeg", "-i", input_file, "-map", "0:s:0", output_file]
    subprocess.run(command)


def main() -> int:
    inputs = [Path(a) for a in sys.argv[1:]]
    files = iter_mkv_files(inputs)
    if not files:
        print("No MKV files found.", file=sys.stderr)
        return 1

    for mkv in files:
        tracks = extract_subtitle_tracks(str(mkv))
        if not tracks:
            continue

        stem = safe_name(mkv.stem)
        for track in tracks:
            track_no = track.get("track_number")
            codec = str(track.get("codec_id") or "").upper()
            lang = safe_name(str(track.get("language") or "")) or "und"
            name = safe_name(str(track.get("name") or ""))

            ext = SUB_EXTS.get(codec, ".srt")
            parts = [stem, f"t{track_no}", lang]
            if name:
                parts.append(name)
            out_path = Path.cwd() / (".".join(parts) + ext)

            data = extract_subtitles_as_srt(str(mkv), int(track_no))
            out_path.write_text(data, encoding="utf-8")
            print(f"{mkv.name} → {out_path.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
