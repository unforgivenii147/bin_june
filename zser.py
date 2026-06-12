#!/data/data/com.termux/files/usr/bin/python

"""
zser – pathlib + joblib parallel compressor/decompressor
No os module, uses pathlib exclusively.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
from io import BytesIO
from pathlib import Path

import zstandard as zstd
from dh import MAX_WORKERS, fsz, gsz, xtar
from joblib import Parallel, delayed

ZST_EXT = ".zst"
SKIP_EXTS = frozenset(
    {
        ".xz",
        ".br",
        ".7z",
        ".zip",
        ".gz",
        ".bz2",
        ".zst",
        ".whl",
        ".mp4",
        ".mp3",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".webm",
    }
)

CHUNK = 262_144


def compress_file(path: Path, level: int) -> dict:
    """Compress a single file, returns result dict (must be picklable)."""
    dst = path.with_suffix(path.suffix + ZST_EXT)
    if dst.exists():
        return {"status": "skip", "path": str(path)}

    try:
        size = path.stat().st_size
        if size == 0:
            return {"status": "skip", "path": str(path)}

        data = path.read_bytes()
        cctx = zstd.ZstdCompressor(level=level, write_content_size=True, threads=MAX_WORKERS)
        compressed = cctx.compress(data)

        if len(compressed) >= size:
            return {"status": "skip", "path": str(path)}

        dst.write_bytes(compressed)
        path.unlink()
        return {
            "status": "ok",
            "path": str(path),
            "original": size,
            "compressed": len(compressed),
        }
    except Exception as e:
        dst.unlink(missing_ok=True)
        return {"status": "error", "path": str(path), "error": str(e)}


def decompress_file(path: Path) -> dict:
    """Decompress a .zst file, detect and extract .tar.zst automatically."""
    if path.suffix != ZST_EXT:
        return {"status": "skip", "path": str(path)}

    # remove .zst suffix
    if path.name.endswith(".tar.zst"):
        if dst.exists():
            return {"status": "skip", "path": str(path)}

        if path.stat().st_size == 0:
            return {"status": "skip", "path": str(path)}

        if xtar(path):
            path.unlink()
            return {
                "status": "ok",
                "path": str(path),
                "extracted": True,
                "original": gsz(path),
                "decompressed": gsz(Path(path.stem)),
            }
        #        compressed = path.read_bytes()
        #        dctx = zstd.ZstdDecompressor()
        #        with dctx.stream_reader(BytesIO(compressed)) as reader:
        #            decompressed = reader.read()

        #        dst.write_bytes(decompressed)

        if dst.suffix == ".tar":
            try:
                with tarfile.open(dst, "r") as tar:
                    tar.extractall(path=dst.parent, filter="data")
                dst.unlink()  # remove .tar
                path.unlink()  # remove .zst
                return {
                    "status": "ok",
                    "path": str(path),
                    "extracted": True,
                    "original": len(compressed),
                    "decompressed": len(decompressed),
                }
            except Exception as e:
                return {"status": "error", "path": str(path), "error": f"tar extract: {e}"}

        # Normal file – just delete .zst
        path.unlink()
        return {
            "status": "ok",
            "path": str(path),
            "dst": str(dst),
            "original": len(compressed),
            "decompressed": len(decompressed),
        }


def compress_dir(path: Path, level: int) -> dict:
    """Tar + compress a whole directory, then delete original."""
    zst_path = path.with_name(path.name + ".tar" + ZST_EXT)
    try:
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            tar.add(str(path), arcname=path.name)
        tar_data = buf.getvalue()

        cctx = zstd.ZstdCompressor(level=level, write_content_size=True, threads=MAX_WORKERS)
        compressed = cctx.compress(tar_data)

        orig_size = gsz(path)
        if len(compressed) >= orig_size:
            return {"status": "skip", "path": str(path)}

        zst_path.write_bytes(compressed)
        shutil.rmtree(path)
        return {
            "status": "ok",
            "path": str(path),
            "original": orig_size,
            "compressed": len(compressed),
        }
    except Exception as e:
        zst_path.unlink(missing_ok=True)
        return {"status": "error", "path": str(path), "error": str(e)}


def scan(path: Path, compress: bool = True) -> tuple[list[Path], list[Path]]:
    """List directories and files to process, sorted for consistency."""
    dirs = []
    files = []
    if not compress:
        return [], [p for p in path.rglob("*.zst") if p.exists()]
    for entry in sorted(path.iterdir()):
        try:
            if entry.is_dir():
                dirs.append(entry)
            elif entry.is_file():
                if compress:
                    if entry.suffix not in SKIP_EXTS:
                        files.append(entry)
                else:
                    if entry.suffix == ZST_EXT:
                        files.append(entry)
        except (PermissionError, FileNotFoundError):
            continue
    return dirs, files


def main():
    parser = argparse.ArgumentParser(description="zser – fast parallel zstd compressor/decompressor")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-c", "--compress", action="store_true", help="Compress mode (default)")
    group.add_argument("-d", "--decompress", action="store_true", help="Decompress .zst files")
    parser.add_argument("-l", "--level", type=int, default=3, help="Compression level (1-22, default 3)")
    parser.add_argument("-w", "--workers", type=int, default=MAX_WORKERS, help="Number of parallel workers")
    parser.add_argument("-p", "--path", type=Path, default=Path.cwd(), help="Target directory")
    parser.add_argument("--no-dirs", action="store_true", help="Skip directory compression")
    parser.add_argument("--sequential", action="store_true", help="Disable parallelism (use 1 worker)")

    args = parser.parse_args()
    if not args.compress and not args.decompress:
        args.compress = True

    target = args.path.resolve()
    if not target.is_dir():
        print("Target must be a directory", file=sys.stderr)
        return 1

    workers = args.workers if args.workers > 0 else MAX_WORKERS
    if args.sequential:
        workers = 1

    initial = gsz(target)
    mode = "compress" if args.compress else "decompress"
    print(f"zser - {mode} | {target} | workers={workers} | size={fsz(initial)}")
    if args.compress:
        print(f"level={args.level}")
    print()

    # --- COMPRESS MODE ---
    if args.compress:
        if not args.no_dirs:
            dirs, files = scan(target, compress=True)
            for d in dirs:
                print(f"  dir  {d.name}...", end=" ")
                res = compress_dir(d, args.level)
                if res["status"] == "ok":
                    print(f"✓ {fsz(res['original'])} → {fsz(res['compressed'])}")
                elif res["status"] == "skip":
                    print("- skipped")
                else:
                    print(f"✗ {res.get('error')}")
            # refresh file list after directories removed
            _, files = scan(target, compress=True)
        else:
            _, files = scan(target, compress=True)

        if files:
            print(f"\nfiles: {len(files)}")
            # Use joblib with loky backend (process-based, safe)
            results = Parallel(n_jobs=workers, backend="loky")(delayed(compress_file)(f, args.level) for f in files)
            total_orig = total_comp = ok = 0
            for r in results:
                if r["status"] == "ok":
                    total_orig += r["original"]
                    total_comp += r["compressed"]
                    ok += 1
                    pct = (1 - r["compressed"] / r["original"]) * 100
                    print(f"  ✓ {Path(r['path']).name}: {fsz(r['original'])} → {fsz(r['compressed'])} ({pct:.1f}%)")
                elif r["status"] == "error":
                    print(f"  ✗ {Path(r.get('path', '?')).name}: {r.get('error')}")
            if ok:
                saved = total_orig - total_comp
                print(f"\nsaved: {fsz(saved)} ({(saved / total_orig) * 100:.1f}%)")
        else:
            print("nothing to compress")

    # --- DECOMPRESS MODE ---
    else:
        _, files = scan(target, compress=False)
        if not files:
            print("no .zst files")
        else:
            print(f"files: {len(files)}")
            results = Parallel(n_jobs=workers, backend="loky")(delayed(decompress_file)(f) for f in files)
            ok = 0
            for r in results:
                if r["status"] == "ok":
                    ok += 1
                    if r.get("extracted"):
                        print(f"  ✓ {Path(r['path']).name} → extracted directory")
                    else:
                        print(f"  ✓ {Path(r['path']).name} → {Path(r['dst']).name} ({fsz(r['decompressed'])})")
                elif r["status"] == "error":
                    print(f"  ✗ {Path(r.get('path', '?')).name}: {r.get('error')}")
            if ok:
                print(f"decompressed: {ok} files")

    # Final size report
    final = gsz(target)
    diff = abs(final - initial)
    if final < initial:
        print(f"\n✅ saved {fsz(diff)} ({(diff / initial) * 100:.1f}%)")
    elif final > initial:
        print(f"\n📈 grew {fsz(diff)} ({(diff / initial) * 100:.1f}%)")
    else:
        print("\n📊 no change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
