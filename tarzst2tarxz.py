#!/data/data/com.termux/files/usr/bin/env python


from __future__ import annotations
import lzma
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import zstandard as zstd

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def human_bytes(n: int) -> str:
    sign = "-" if n < 0 else ""
    n = abs(n)
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    return f"{sign}{n:.2f} {units[i]}" if units[i] != "B" else f"{sign}{int(n)} B"


def dir_files_total_bytes(p: Path) -> int:
    total = 0
    for x in p.iterdir():
        if x.is_file():
            total += x.stat().st_size
    return total


def convert_one(src: str) -> tuple[str, int, bool, str]:
    src_path = Path(src)
    dst_xz = src_path.with_suffix("")
    dst_xz = Path(str(dst_xz) + ".xz")
    if dst_xz.exists():
        return (src, 0, True, f"skipped (exists): {dst_xz.name}")
    try:
        dctx = zstd.ZstdDecompressor()
        with src_path.open("rb") as f_in:
            with dctx.stream_reader(f_in) as zreader:
                comp = lzma.LZMACompressor(format=lzma.FORMAT_XZ, check=-1, preset=9)
                with dst_xz.open("wb") as f_out:
                    while True:
                        chunk = zreader.read(1024 * 1024)
                        if not chunk:
                            break
                        out = comp.compress(chunk)
                        if out:
                            f_out.write(out)
                    tail = comp.flush()
                    if tail:
                        f_out.write(tail)
        src_size_before = src_path.stat().st_size
        dst_size_after = dst_xz.stat().st_size
        src_path.unlink()
        return (src, dst_size_after - src_size_before, True, f"converted -> {dst_xz.name}, removed original")
    except Exception as e:
        try:
            if dst_xz.exists():
                dst_xz.unlink()
        except Exception:
            pass
        return (src, 0, False, f"error: {e}")


def main() -> None:
    cwd = Path(".").resolve()
    tar_zst_files = sorted(cwd.glob("*.tar.zst"))
    if not tar_zst_files:
        print("No .tar.zst files found in current directory.")
        return
    initial_bytes = dir_files_total_bytes(cwd)
    max_workers = max(1, min(os.cpu_count() or 1, len(tar_zst_files)))
    results: list[tuple[str, int, bool, str]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(convert_one, str(p)) for p in tar_zst_files]
        for f in as_completed(futures):
            results.append(f.result())
    final_bytes = dir_files_total_bytes(cwd)
    delta = final_bytes - initial_bytes
    ok_count = sum((1 for _, _, ok, _ in results if ok))
    fail_count = len(results) - ok_count
    print(f"Found: {len(tar_zst_files)}; Converted OK: {ok_count}; Failed/Skipped: {fail_count}")
    for src, _, ok, msg in sorted(results, key=lambda x: x[0]):
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {Path(src).name}: {msg}")
    print(f"Disk usage (files in cwd) initial: {human_bytes(initial_bytes)}")
    print(f"Disk usage (files in cwd) final:   {human_bytes(final_bytes)}")
    if delta < 0:
        print(f"Saved: {human_bytes(-delta)}")
    elif delta > 0:
        print(f"Extra used: {human_bytes(delta)}")
    else:
        print("No disk usage change (by summed file sizes in cwd).")


if __name__ == "__main__":
    main()
