#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations
import lzma
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import zstandard as zstd
from dh import fsz, gsz
def convert_one(src: str) -> tuple[str, int, bool, str]:
    src_path = Path(src)
    dst_xz = src_path.with_suffix("")
    dst_xz = Path(str(dst_xz) + ".xz")
    if dst_xz.exists():
        return (src, 0, True, f"skipped (exists): {dst_xz.name}")
    try:
        dctx = zstd.ZstdDecompressor()
        with src_path.open("rb") as f_in, dctx.stream_reader(f_in) as zreader:
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
    before = gsz(cwd)
    max_workers = max(1, min(os.cpu_count() or 1, len(tar_zst_files)))
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(convert_one, str(p)) for p in tar_zst_files]
        for f in as_completed(futures):
            results.append(f.result())
    after = gsz(cwd)
    delta = after - before
    ok_count = sum((1 for _, _, ok, _ in results if ok))
    fail_count = len(results) - ok_count
    print(f"Found: {len(tar_zst_files)}; Converted OK: {ok_count}; Failed/Skipped: {fail_count}")
    for src, _, ok, msg in sorted(results, key=lambda x: x[0]):
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {Path(src).name}: {msg}")
    print(f"Disk usage (files in cwd) initial: {fsz(before)}")
    print(f"Disk usage (files in cwd) final:   {fsz(after)}")
    if delta < 0:
        print(f"Saved: {fsz(-delta)}")
    elif delta > 0:
        print(f"Extra used: {fsz(delta)}")
    else:
        print("No disk usage change (by summed file sizes in cwd).")
if __name__ == "__main__":
    main()
