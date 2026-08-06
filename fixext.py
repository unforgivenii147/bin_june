#!/data/data/com.termux/files/home/.local/bin/python
import os
import sys
import subprocess
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from typing import NamedTuple, Optional
# =============================================================================
# MIME TYPE DATABASE
# =============================================================================
# Exhaustive mapping of MIME types to their standard extensions.
MIME_MAP = {
    # Applications / Documents
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
    # Archives
    "application/zip": [".zip"],
    "application/x-rar-compressed": [".rar"],
    "application/x-7z-compressed": [".7z"],
    "application/x-tar": [".tar"],
    "application/gzip": [".gz", ".tar.gz"],
    "application/x-bzip2": [".bz2", ".tar.bz2"],
    "application/x-xz": [".xz", ".tar.xz"],
    "application/x-zstd": [".zst", ".tar.zst"],
    # Executables / Packages
    "application/x-msdownload": [".exe", ".dll"],
    "application/vnd.android.package-archive": [".apk"],
    "application/x-appimage": [".AppImage"],
    "application/vnd.debian.binary-package": [".deb"],
    "application/x-rpm-package": [".rpm"],
    "application/x-flatpak": [".flatpak"],
    # Disk Images
    "application/x-iso9660-image": [".iso"],
    "application/x-dmg": [".dmg"],
    "application/x-virtualbox-disk": [".vdi"],
    "application/vnd.vmware.vmdk": [".vmdk"],
    # Audio
    "audio/mpeg": [".mp3"],
    "audio/flac": [".flac"],
    "audio/aac": [".aac"],
    "audio/ogg": [".ogg"],
    "audio/wav": [".wav"],
    "audio/midi": [".mid", ".midi"],
    "audio/x-mod": [".mod"],
    # Video
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
    # Images
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
    # Text / Code / Markup
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
    # Fonts
    "font/ttf": [".ttf"],
    "font/otf": [".otf"],
    "font/woff": [".woff"],
    "font/woff2": [".woff2"],
    "font/eot": [".eot"],
    # 3D Models
    "application/sla": [".stl"],
    "model/obj": [".obj"],
    "model/gltf+json": [".gltf"],
    "application/collada": [".dae"],
    "model/vrml": [".wrl"],
}
# Directories to ignore recursively
SKIP_DIRS = frozenset({".git", "__pycache__"})
# Extensions to skip due to high false-positive rates in MIME detection
SKIP_EXTS = frozenset({".css", ".js"})
class Mismatch(NamedTuple):
    path: Path
    current_ext: str
    detected_mime: str
    expected_ext: str
    new_path: Path
# =============================================================================
# TERMINAL COLOR SYSTEM
# =============================================================================
class Colors:
    # Standard ANSI
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    # Foreground
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    # Backgrounds
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
def can_colorize() -> bool:
    if "NO_COLOR" in os.environ or "ANSI_COLORS_DISABLED" in os.environ:
        return False
    if "FORCE_COLOR" in os.environ:
        return True
    return sys.stdout.isatty()
def colored(text: str, color: str = "", on_color: str = "", attrs: str = "") -> str:
    if not can_colorize():
        return text
    return f"{attrs}{on_color}{color}{text}{Colors.RESET}"
def cprint(text: str, color: str = "", on_color: str = "", attrs: str = "") -> None:
    print(colored(text, color, on_color, attrs))
# =============================================================================
# CORE UTILITIES
# =============================================================================
def runcmd(cmd: list[str], silent: bool = True, timeout: int = 5) -> tuple[int, str, str]:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout occurred"
    except FileNotFoundError:
        return -1, "", "Command 'file' not found. Please install it."
    except Exception as e:
        return -1, "", str(e)
def is_binary(path: Path) -> bool:
    """Heuristic binary detection based on null bytes and non-text ratios."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
            if not chunk:
                return False
            if b"\x00" in chunk:
                return True
            text_chars = sum(1 for b in chunk if 32 <= b <= 126 or b in b"\n\r\t")
            return (text_chars / len(chunk)) < 0.7
    except Exception:
        return True
def unique_path(path: Path) -> Path:
    """Generates a unique path by appending _1, _2 etc to the stem."""
    if not path.exists():
        return path
    # Handle compound extensions (.tar.gz)
    suffixes = "".join(path.suffixes)
    stem = path.name.replace(suffixes, "")
    parent = path.parent
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{suffixes}"
        candidate = parent / new_name
        if not candidate.exists():
            return candidate
        counter += 1
def get_file_mime(path: Path) -> str:
    code, stdout, _ = runcmd(["file", "--brief", "--mime-type", str(path)])
    return stdout if code == 0 else "unknown/unknown"
def analyze_file(path: Path) -> Optional[Mismatch]:
    """
    The worker function for parallel processing.
    Determines if a file extension is mismatched.
    """
    try:
        if not path.is_file() or path.is_symlink():
            return None
        # 1. Skip common problematic extensions
        if path.suffix.lower() in SKIP_EXTS:
            return None
        # 2. Empty files
        if path.stat().st_size == 0:
            return None
        # 3. Shebang Detection (only for non-binaries)
        if not is_binary(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline()
                    if first_line.startswith("#!"):
                        if "python" in first_line:
                            expected = ".py"
                        elif any(x in first_line for x in ["bash", "sh", "zsh"]):
                            expected = ".sh"
                        else:
                            expected = None
                        if expected and path.suffix.lower() != expected:
                            return Mismatch(
                                path, path.suffix, "shebang", expected, unique_path(path.with_suffix(expected))
                            )
                        if expected:
                            return None  # Fixed or matches
            except Exception:
                pass
        # 4. MIME Detection
        mime = get_file_mime(path)
        if mime == "text/plain" or mime == "unknown/unknown":
            return None  # Skip generic text to avoid false positives
        expected_list = MIME_MAP.get(mime, [])
        if not expected_list:
            return None
        expected = expected_list[0]
        # Detect current extension (handling compound extensions)
        current_ext = "".join(path.suffixes).lower()
        if current_ext != expected.lower():
            new_p = path.with_suffix(expected) if not path.suffix else path.with_suffix(expected)
            # Pathlib with_suffix replaces the LAST suffix. For compound, we might need logic.
            # But the requirement says pick first match from map.
            return Mismatch(path, current_ext, mime, expected, unique_path(new_p))
    except Exception:
        return None
    return None
# =============================================================================
# MAIN ENGINE
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Detect and fix file extension mismatches.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan (default: current)")
    parser.add_argument("-y", "--yes", action="store_true", help="Automatic rename without confirmation")
    args = parser.parse_args()
    root_path = Path(args.directory)
    if not root_path.is_dir():
        cprint(f"Error: {args.directory} is not a valid directory.", Colors.RED)
        sys.exit(1)
    # Collect all files first for parallel mapping
    all_files = []
    for root, dirs, files in os.walk(root_path):
        # Modify dirs in-place to skip them recursively
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            all_files.append(Path(root) / f)
    cprint(f"Scanning {len(all_files)} files... ", Colors.CYAN)
    mismatches: list[Mismatch] = []
    # PARALLEL ANALYSIS PHASE
    # We use ProcessPoolExecutor because 'file' is a subprocess call and is CPU/IO bound
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(analyze_file, all_files))
        mismatches = [r for r in results if r is not None]
    if not mismatches:
        cprint("✨ No mismatches found. Your filesystem is clean!", Colors.GREEN, attrs=Colors.BOLD)
        return
    # RENAMING PHASE (Sequential)
    fixed_count = 0
    for m in mismatches:
        cprint(f"\n{Colors.YELLOW}Mismatch found:{Colors.RESET}", attrs=Colors.BOLD)
        cprint(f"  File: {m.path.name} {Colors.DIM}({m.current_ext}){Colors.RESET}")
        cprint(f"  MIME: {m.detected_mime} → Expected: {m.expected_ext}", Colors.CYAN)
        cprint(f"  Proposed: {m.new_path.name}", Colors.GREEN)
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
                cprint("  ✅ Renamed successfully.", Colors.GREEN)
                fixed_count += 1
            except Exception as e:
                cprint(f"  ❌ Failed to rename: {e}", Colors.RED)
    # FINAL REPORT
    cprint("\n" + "=" * 40, Colors.WHITE)
    cprint(f"SUMMARY REPORT", Colors.MAGENTA, attrs=Colors.BOLD + Colors.UNDERLINE)
    cprint(f"Total Mismatches: {len(mismatches)}", Colors.WHITE)
    cprint(f"Successfully Fixed: {fixed_count}", Colors.GREEN, attrs=Colors.BOLD)
    cprint(f"Remaining: {len(mismatches) - fixed_count}", Colors.YELLOW)
    cprint("=" * 40, Colors.WHITE)
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(1)
