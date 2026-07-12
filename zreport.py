#!/data/data/com.termux/files/usr/bin/env python

"""
Report uncompressed sizes of compressed files in the current directory
and calculate total disk space needed for extraction.

Supported formats: .zst, .xz, .gz, .bz2, .bz3, .br, .lz4, .7z, .zip, .whl
and their tarred variants (.tar.zst, .tar.xz, .tar.gz, .tar.bz2, .tar.lz4, etc.)
"""

import bz2
import gzip
import io
import lzma
import struct
import tarfile
import zipfile
from pathlib import Path

# ── optional dependency probes ────────────────────────────────────────────────


def _try_import(module_name):
    try:
        import importlib

        return importlib.import_module(module_name)
    except ImportError:
        return None


zstd = _try_import("zstandard")
lz4f = _try_import("lz4.frame")
bzip3 = _try_import("bzip3")  # pybzip3 / bzip3-python
brotli = _try_import("brotli")
py7zr = _try_import("py7zr")


# ── size helpers ──────────────────────────────────────────────────────────────


def _stream_size(readable, chunk=1 << 20):
    """Drain a readable object and return total bytes read."""
    total = 0
    while True:
        data = readable.read(chunk)
        if not data:
            break
        total += len(data)
    return total


def _tar_uncompressed_size(fileobj, mode="r:*"):
    """Sum member sizes inside a tar archive opened from a file-like object."""
    try:
        with tarfile.open(fileobj=fileobj, mode=mode) as tf:
            return sum(m.size for m in tf.getmembers() if m.isfile())
    except Exception:
        return None


# ── per-format size getters ───────────────────────────────────────────────────


def _size_zst(path: Path):
    if zstd is None:
        return None, "zstandard not installed"
    try:
        with open(path, "rb") as f:
            dctx = zstd.ZstdDecompressor()
            params = dctx.frame_parameters(f.read(32))
            if params.uncompressed_size:
                size = params.uncompressed_size
            else:
                f.seek(0)
                size = _stream_size(dctx.stream_reader(f))
        return size, None
    except Exception as e:
        return None, str(e)


def _size_xz(path: Path):
    try:
        with lzma.open(path, "rb") as f:
            size = _stream_size(f)
        return size, None
    except Exception as e:
        return None, str(e)


def _size_gz(path: Path):
    try:
        with gzip.open(path, "rb") as f:
            size = _stream_size(f)
        return size, None
    except Exception as e:
        return None, str(e)


def _size_bz2(path: Path):
    try:
        with bz2.open(path, "rb") as f:
            size = _stream_size(f)
        return size, None
    except Exception as e:
        return None, str(e)


def _size_bz3(path: Path):
    if bzip3 is None:
        return None, "bzip3 not installed"
    try:
        # pybzip3 exposes bzip3.decompress(data) -> bytes
        data = path.read_bytes()
        out = bzip3.decompress(data)
        return len(out), None
    except Exception as e:
        return None, str(e)


def _size_br(path: Path):
    if brotli is None:
        return None, "brotli not installed"
    try:
        data = path.read_bytes()
        out = brotli.decompress(data)
        return len(out), None
    except Exception as e:
        return None, str(e)


def _size_lz4(path: Path):
    if lz4f is None:
        return None, "lz4 not installed"
    try:
        with open(path, "rb") as f:
            data = f.read()
        out = lz4f.decompress(data)
        return len(out), None
    except Exception as e:
        return None, str(e)


def _size_7z(path: Path):
    if py7zr is None:
        return None, "py7zr not installed"
    try:
        with py7zr.SevenZipFile(path, mode="r") as z:
            size = sum(f.uncompressed for f in z.list() if f.uncompressed is not None)
        return size, None
    except Exception as e:
        return None, str(e)


def _size_zip(path: Path):
    try:
        with zipfile.ZipFile(path, "r") as z:
            size = sum(i.file_size for i in z.infolist())
        return size, None
    except Exception as e:
        return None, str(e)


# ── tar combo handlers ────────────────────────────────────────────────────────


def _size_tar_zst(path: Path):
    if zstd is None:
        return None, "zstandard not installed"
    try:
        with open(path, "rb") as f:
            dctx = zstd.ZstdDecompressor()
            raw = io.BytesIO(dctx.stream_reader(f).read())
        size = _tar_uncompressed_size(raw)
        return size, None
    except Exception as e:
        return None, str(e)


def _size_tar_xz(path: Path):
    try:
        with lzma.open(path, "rb") as f:
            raw = io.BytesIO(f.read())
        size = _tar_uncompressed_size(raw)
        return size, None
    except Exception as e:
        return None, str(e)


def _size_tar_gz(path: Path):
    try:
        size = _tar_uncompressed_size(None, mode="r:gz") or _tar_uncompressed_size(open(path, "rb"), mode="r:gz")
        # simpler: let tarfile handle it directly
        with tarfile.open(path, "r:gz") as tf:
            size = sum(m.size for m in tf.getmembers() if m.isfile())
        return size, None
    except Exception as e:
        return None, str(e)


def _size_tar_bz2(path: Path):
    try:
        with tarfile.open(path, "r:bz2") as tf:
            size = sum(m.size for m in tf.getmembers() if m.isfile())
        return size, None
    except Exception as e:
        return None, str(e)


def _size_tar_lz4(path: Path):
    if lz4f is None:
        return None, "lz4 not installed"
    try:
        with open(path, "rb") as f:
            raw = io.BytesIO(lz4f.decompress(f.read()))
        size = _tar_uncompressed_size(raw)
        return size, None
    except Exception as e:
        return None, str(e)


def _size_tar_bz3(path: Path):
    if bzip3 is None:
        return None, "bzip3 not installed"
    try:
        raw = io.BytesIO(bzip3.decompress(path.read_bytes()))
        size = _tar_uncompressed_size(raw)
        return size, None
    except Exception as e:
        return None, str(e)


def _size_tar_br(path: Path):
    if brotli is None:
        return None, "brotli not installed"
    try:
        raw = io.BytesIO(brotli.decompress(path.read_bytes()))
        size = _tar_uncompressed_size(raw)
        return size, None
    except Exception as e:
        return None, str(e)


def _size_tar_plain(path: Path):
    try:
        with tarfile.open(path, "r:") as tf:
            size = sum(m.size for m in tf.getmembers() if m.isfile())
        return size, None
    except Exception as e:
        return None, str(e)


# ── extension → handler map ───────────────────────────────────────────────────
# Order matters for suffix matching (longest suffix first).

EXT_HANDLERS = {
    # tarred combos
    ".tar.zst": ("tar+zst", _size_tar_zst),
    ".tzst": ("tar+zst", _size_tar_zst),
    ".tar.xz": ("tar+xz", _size_tar_xz),
    ".txz": ("tar+xz", _size_tar_xz),
    ".tar.gz": ("tar+gz", _size_tar_gz),
    ".tgz": ("tar+gz", _size_tar_gz),
    ".tar.bz2": ("tar+bz2", _size_tar_bz2),
    ".tbz2": ("tar+bz2", _size_tar_bz2),
    ".tar.lz4": ("tar+lz4", _size_tar_lz4),
    ".tar.bz3": ("tar+bz3", _size_tar_bz3),
    ".tar.br": ("tar+br", _size_tar_br),
    ".tar": ("tar", _size_tar_plain),
    # single-stream
    ".zst": ("zst", _size_zst),
    ".xz": ("xz", _size_xz),
    ".gz": ("gz", _size_gz),
    ".bz2": ("bz2", _size_bz2),
    ".bz3": ("bz3", _size_bz3),
    ".br": ("br", _size_br),
    ".lz4": ("lz4", _size_lz4),
    ".7z": ("7z", _size_7z),
    ".zip": ("zip", _size_zip),
    ".whl": ("whl/zip", _size_zip),  # wheels are zips
}


def match_handler(path: Path):
    """Return (label, handler) for the longest matching suffix, or None."""
    name = path.name.lower()
    for ext, (label, handler) in EXT_HANDLERS.items():
        if name.endswith(ext):
            return label, handler
    return None, None


# ── formatting ────────────────────────────────────────────────────────────────


def format_size(size_bytes):
    if size_bytes is None:
        return "Unknown"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


# ── main ──────────────────────────────────────────────────────────────────────


def main():
    dir_path = Path(".")

    # Collect all matching files
    all_files = []
    for path in sorted(dir_path.rglob("*")):
        if not path.is_file():
            continue
        label, handler = match_handler(path)
        if label:
            all_files.append((path, label, handler))

    if not all_files:
        print("No supported compressed files found in the current directory.")
        print("Supported: .zst .xz .gz .bz2 .bz3 .br .lz4 .7z .zip .whl")
        print("           and .tar.* / .t*z* tarred variants")
        return

    print(f"Found {len(all_files)} compressed file(s) in {dir_path.absolute()}\n")

    # ── per-file report ───────────────────────────────────────────────────────
    print("=" * 80)
    print("PER-FILE REPORT")
    print("=" * 80)

    # group results by extension label for the summary
    by_ext = {}  # label -> list of (name, compressed, uncompressed)
    grand_compressed = 0
    grand_uncompressed = 0

    for path, label, handler in all_files:
        compressed_size = path.stat().st_size
        uncompressed_size, err = handler(path)

        grand_compressed += compressed_size
        if uncompressed_size is not None:
            grand_uncompressed += uncompressed_size

        ratio = (uncompressed_size / compressed_size) if uncompressed_size else None
        ratio_str = f"{ratio:.2f}x" if ratio else "N/A"

        print(f"\nFile : {path.name}")
        print(f"Type : {label}")
        print(f"  Compressed   : {format_size(compressed_size)}")
        print(
            f"  Uncompressed : {format_size(uncompressed_size)}"
            + (f"   [{err}]" if err and uncompressed_size is None else "")
        )
        if ratio:
            print(f"  Ratio        : {ratio_str}")
        print("-" * 40)

        by_ext.setdefault(label, []).append((path.name, compressed_size, uncompressed_size))

    # ── per-extension summary ─────────────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("SUMMARY BY EXTENSION / FORMAT")
    print("=" * 80)

    col = "{:<12} {:>6} {:>18} {:>18} {:>10}"
    print(col.format("Format", "Files", "Compressed", "Uncompressed", "Ratio"))
    print("-" * 70)

    for label in sorted(by_ext):
        entries = by_ext[label]
        n = len(entries)
        c_total = sum(e[1] for e in entries)
        u_total = sum(e[2] for e in entries if e[2] is not None)
        has_u = any(e[2] is not None for e in entries)
        ratio = (u_total / c_total) if (has_u and c_total) else None
        print(
            col.format(
                label,
                n,
                format_size(c_total),
                format_size(u_total) if has_u else "Unknown",
                f"{ratio:.2f}x" if ratio else "N/A",
            )
        )

    print("-" * 70)
    overall_ratio = (grand_uncompressed / grand_compressed) if grand_compressed else None
    print(
        col.format(
            "TOTAL",
            len(all_files),
            format_size(grand_compressed),
            format_size(grand_uncompressed) if grand_uncompressed else "Unknown",
            f"{overall_ratio:.2f}x" if overall_ratio else "N/A",
        )
    )

    # ── disk space check ──────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("DISK SPACE")
    print("=" * 80)
    print(f"Total compressed size   : {format_size(grand_compressed)}")
    print(f"Total uncompressed size : {format_size(grand_uncompressed)}")

    try:
        import shutil

        _, _, free = shutil.disk_usage(".")
        print(f"Available disk space    : {format_size(free)}")
        if grand_uncompressed and grand_uncompressed > free:
            shortfall = grand_uncompressed - free
            print("\n⚠️  WARNING: Not enough disk space!")
            print(f"   Need      : {format_size(grand_uncompressed)}")
            print(f"   Have      : {format_size(free)}")
            print(f"   Shortfall : {format_size(shortfall)}")
        elif grand_uncompressed:
            print("\n✓  Enough disk space available.")
        else:
            print("\n⚠️  Could not determine uncompressed size for all files.")
    except Exception:
        pass

    print("=" * 80)


if __name__ == "__main__":
    main()
