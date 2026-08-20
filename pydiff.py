#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from dh import cprint, read_lines_mmap


def count_lines(path: Path) -> int:
    return path.read_bytes().count(b"\n") + 1


def read_lines(path: Path, use_mmap: bool = False, ke: bool = True) -> list[str]:
    if use_mmap:
        return read_lines_mmap(path, ke)
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines(keepends=ke)
    if lines and not lines[-1].endswith(("\n", "\r\n", "\r")) and data.endswith(b"\n"):
        lines.append("")
    return lines


def read_file_task(path: Path, use_mmap: bool) -> tuple[Path, list[str]]:
    lines = read_lines(path, use_mmap=use_mmap)
    return path, lines


def filter_diff_chunk(
    chunk: list[str], exclude_set: frozenset[str], mode: str
) -> list[str]:
    if mode == "only_in_first":
        return [p for p in chunk if p not in exclude_set]
    else:
        return [p for p in chunk if p in exclude_set]


def process_files_parallel(path1: Path, path2: Path, num_workers: int = 2) -> None:
    lines1_count = count_lines(path1)
    lines2_count = count_lines(path2)
    use_mmap1 = lines1_count > 5000
    use_mmap2 = lines2_count > 5000
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future1 = executor.submit(read_file_task, path1, use_mmap1)
        future2 = executor.submit(read_file_task, path2, use_mmap2)
        _, lines1 = future1.result()
        _, lines2 = future2.result()
    set1 = set(lines1)
    set2 = set(lines2)
    if lines1_count > 10000 and lines2_count > 10000:
        chunk_size = max(1000, len(lines1) // num_workers)
        chunks = [lines1[i : i + chunk_size] for i in range(0, len(lines1), chunk_size)]
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(
                    filter_diff_chunk, chunk, frozenset(set2), "only_in_first"
                )
                for chunk in chunks
            ]
            only_in_first = []
            for future in as_completed(futures):
                only_in_first.extend(future.result())
    else:
        only_in_first = [p for p in lines1 if p not in set2]
    only_in_second = [p for p in lines2 if p not in set1]
    common_count = len(set1 & set2)
    if only_in_first:
        cprint(f"only in {path1.name}:", "cyan")
        for line in only_in_first:
            cprint(f"  - {line}", "green")
    if only_in_second:
        cprint(f"only in {path2.name}:", "cyan")
        for line in only_in_second:
            cprint(f"  - {line}", "yellow")
    cprint(
        f"common lines: {common_count}\nonly in {path1.name}: {len(only_in_first)}\nonly in {path2.name}: {len(only_in_second)}",
        "blue",
    )


if __name__ == "__main__":
    f1 = Path(sys.argv[1])
    f2 = Path(sys.argv[2])
    process_files_parallel(f1, f2)
