#!/data/data/com.termux/files/home/.local/bin/python


import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import NamedTuple, Optional

from dh import cprint, is_binary, runcmd

MIME_MAP = {
    "application/pdf": [".pdf"],
    "application/msword": [".doc"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    "application/vnd.ms-excel": [".xls"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    "application/vnd.ms-powerpoint": [".ppt"],
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
    "application/odtext": [".odt"],
    "application/ods": [".ods"],
    "application/odp": [".odp"],
    "application/zip": [".zip"],
    "application/x-rar-compressed": [".rar"],
    "application/x-7z-compressed": [".7z"],
    "application/x-tar": [".tar"],
    "application/gzip": [".gz", ".tar.gz"],
    "application/x-bzip2": [".bz2", ".tar.bz2"],
    "application/x-xz": [".xz", ".tar.xz"],
    "application/x-zstd": [".zst", ".tar.zst"],
    "application/x-msdownload": [".exe", ".dll"],
    "application/vnd.android.package-archive": [".apk"],
    "application/x-appimage": [".AppImage"],
    "application/vnd.debian.binary-package": [".deb"],
    "application/x-rpm-package": [".rpm"],
    "application/x-flatpak": [".flatpak"],
    "application/x-iso9660-image": [".iso"],
    "application/x-dmg": [".dmg"],
    "application/x-virtualbox-disk": [".vdi"],
    "application/vnd.vmware.vmdk": [".vmdk"],
    "audio/mpeg": [".mp3"],
    "audio/flac": [".flac"],
    "audio/aac": [".aac"],
    "audio/ogg": [".ogg"],
    "audio/wav": [".wav"],
    "audio/midi": [".mid", ".midi"],
    "audio/x-mod": [".mod"],
    "video/mp4": [".mp4"],
    "video/x-msvideo": [".avi"],
    "video/x-matroska": [".mkv"],
    "video/webm": [".webm"],
    "video/quicktime": [".mov"],
    "video/x-ms-wmv": [".wmv"],
    "video/x-flv": [".flv"],
    "application/x-nintendo-nes-rom": [".nes"],
    "application/x-nintendo-snes-rom": [".snes"],
    "application/x-gameboy-rom": [".gb"],
    "application/x-nintendo64-rom": [".n64"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/gif": [".gif"],
    "image/svg+xml": [".svg"],
    "image/tiff": [".tif", ".tiff"],
    "image/webp": [".webp"],
    "image/avif": [".avif"],
    "image/heic": [".heic"],
    "image/x-canon-cr2": [".cr2"],
    "image/x-nikon-nef": [".nef"],
    "image/x-sony-arw": [".arw"],
    "image/x-gnome-xcf": [".xcf"],
    "text/plain": [".txt"],
    "text/x-python": [".py"],
    "text/x-rust": [".rs"],
    "text/x-go": [".go"],
    "text/x-java": [".java"],
    "text/x-c": [".c"],
    "text/x-c++": [".cpp", ".hpp", ".cc"],
    "text/html": [".html", ".htm"],
    "text/xml": [".xml"],
    "text/markdown": [".md"],
    "application/json": [".json"],
    "application/x-yaml": [".yaml", ".yml"],
    "application/toml": [".toml"],
    "application/x-ini": [".ini"],
    "font/ttf": [".ttf"],
    "font/otf": [".otf"],
    "font/woff": [".woff"],
    "font/woff2": [".woff2"],
    "font/eot": [".eot"],
    "application/sla": [".stl"],
    "model/obj": [".obj"],
    "model/gltf+json": [".gltf"],
    "application/collada": [".dae"],
    "model/vrml": [".wrl"],
}
SKIP_DIRS = frozenset({".git", "__pycache__"})
SKIP_EXTS = frozenset({".css", ".js"})


class Mismatch(NamedTuple):
    path: Path
    current_ext: str
    detected_mime: str
    expected_ext: str
    new_path: Path


def get_file_mime(path: Path) -> str:
    code, stdout, _ = runcmd(["file", "--brief", "--mime-type", str(path)])
    return stdout if code == 0 else "unknown/unknown"


def analyze_file(path: Path) -> Optional[Mismatch]:
    try:
        if not path.is_file() or path.is_symlink():
            return None
        if path.suffix.lower() in SKIP_EXTS:
            return None
        if path.stat().st_size == 0:
            return None
        if not is_binary(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline()
                    if first_line.startswith("#!"):
                        if "python" in first_line:
                            expected = ".py"
                        elif any((x in first_line for x in ["bash", "sh", "zsh"])):
                            expected = ".sh"
                        else:
                            expected = None
                        if expected and path.suffix.lower() != expected:
                            return Mismatch(
                                path, path.suffix, "shebang", expected, unique_path(path.with_suffix(expected))
                            )
                        if expected:
                            return None
            except Exception:
                pass
        mime = get_file_mime(path)
        if mime == "text/plain" or mime == "unknown/unknown":
            return None
        expected_list = MIME_MAP.get(mime, [])
        if not expected_list:
            return None
        expected = expected_list[0]
        current_ext = "".join(path.suffixes).lower()
        if current_ext != expected.lower():
            new_p = path.with_suffix(expected) if not path.suffix else path.with_suffix(expected)
            return Mismatch(path, current_ext, mime, expected, unique_path(new_p))
    except Exception:
        return None
    return None


def main():
    parser = argparse.ArgumentParser(description="Detect and fix file extension mismatches.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan (default: current)")
    parser.add_argument("-y", "--yes", action="store_true", help="Automatic rename without confirmation")
    args = parser.parse_args()
    root_path = Path(args.directory)
    if not root_path.is_dir():
        cprint(f"Error: {args.directory} is not a valid directory.", "red")
        sys.exit(1)
    all_files = []
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            all_files.append(Path(root) / f)
    cprint(f"Scanning {len(all_files)} files... ")
    mismatches: list[Mismatch] = []
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(analyze_file, all_files))
        mismatches = [r for r in results if r is not None]
    if not mismatches:
        cprint("✨ No mismatches found. Your filesystem is clean!", "red")
        return
    fixed_count = 0
    for m in mismatches:
        cprint(f"\nMismatch found:", "yellow")
        cprint(f"  File: {m.path.name} ({m.current_ext})", "grey")
        cprint(f"  MIME: {m.detected_mime} → Expected: {m.expected_ext}")
        cprint(f"  Proposed: {m.new_path.name}", "green")
        do_rename = False
        if args.yes:
            do_rename = True
        else:
            choice = input(f"  Rename to {m.new_path.name}? [y/N]: ").lower()
            if choice == "y":
                do_rename = True
        if do_rename:
            try:
                m.path.rename(m.new_path)
                cprint("  ✅ Renamed successfully.", "green")
                fixed_count += 1
            except Exception as e:
                cprint(f"  ❌ Failed to rename: {e}", "red")
    cprint("\n" + "=" * 42, "white")
    cprint(f"SUMMARY REPORT")
    cprint(f"Total Mismatches: {len(mismatches)}")
    cprint(f"Remaining: {len(mismatches) - fixed_count}", "yellow")
    cprint("=" * 42, "white")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(1)
