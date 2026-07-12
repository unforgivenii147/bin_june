#!/data/data/com.termux/files/usr/bin/env python
"""
Translate Chinese characters in text files in-place.
Optimized for speed using parallel processing.
Only translates Chinese characters (not punctuation), preserving everything else.
"""

import re
import json
import logging
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from os import scandir as os_scandir
from pathlib import Path

from deep_translator import GoogleTranslator
from dh import get_nobinary
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

CHUNK_SIZE = 32768
SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+")
ZERO_DOT_THREE = 0.3
MAX_WORKERS = 10
MAX_RETRIES = 3
PROGRESS_SAVE_EVERY = 20

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

_interrupted = False


def is_binary(path: Path | str) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as f:
            chunk = f.read(CHUNK_SIZE)
        if not chunk:
            return False
        if b"\x00" in chunk:
            return True
        text_chars = bytearray(range(32, 127)) + b"\n\r\t\x08"
        nontext = sum(1 for b in chunk if b not in text_chars)
        return nontext / len(chunk) > ZERO_DOT_THREE
    except Exception:
        return True


def get_nobinary(path: str | Path) -> list[Path]:
    return [f for f in get_files(path) if not is_binary(f)]


def get_files(path: str | Path, include_hidden: bool = True, ext: list[str] | None = None) -> list[Path]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    ext = tuple(ext) if ext else None
    files = []
    stack = [path]

    while stack:
        current = stack.pop()
        try:
            with os_scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            stack.append(entry)
                    elif entry.is_file(follow_symlinks=False):
                        if not include_hidden and entry.name.startswith("."):
                            continue
                        if ext is None or entry.name.endswith(ext):
                            files.append(Path(entry.path))
        except (PermissionError, OSError):
            continue

    return sorted(files)


def _sigint_handler(sig, frame):
    global _interrupted
    print("\n⚠️  Ctrl+C caught — completing current active requests and saving progress...")
    _interrupted = True


signal.signal(signal.SIGINT, _sigint_handler)


def is_chinese_ideograph(ch: str) -> bool:
    """Check if a single character is a Chinese ideograph using regex."""
    return bool(CHINESE_PATTERN.fullmatch(ch))


def has_chinese(text: str) -> bool:
    """Check if text contains any Chinese characters."""
    return bool(CHINESE_PATTERN.search(text))


def find_chinese_segments(text: str) -> list[tuple[int, int, str]]:
    """Find all contiguous Chinese character segments with their positions."""
    segments = []
    for match in CHINESE_PATTERN.finditer(text):
        segments.append((match.start(), match.end(), match.group()))
    return segments


def reassemble_line(original: str, translations: dict[tuple[int, int], str]) -> str:
    result = []
    last_end = 0
    for (start, end), translated in sorted(translations.items()):
        result.append(original[last_end:start])
        result.append(translated)
        last_end = end
    result.append(original[last_end:])
    return "".join(result)


def read_text(path: Path) -> tuple[str, str]:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk", "cp1252"):
        try:
            return (path.read_text(encoding=enc, errors="strict"), enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return (path.read_bytes().decode("utf-8", errors="replace"), "utf-8")


class RateLimitError(Exception):
    pass


class TranslationError(Exception):
    pass


@retry(
    reraise=True,
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
    retry=retry_if_exception_type((RateLimitError, TranslationError)),
    before_sleep=before_sleep_log(log, logging.DEBUG),
)
def _translate(text: str) -> str:
    try:
        result = GoogleTranslator(source="auto", target="en").translate(text)
        if result is None:
            raise TranslationError("Translator returned None")
        if has_chinese(result):
            raise TranslationError(f"Result still contains Chinese")
        return result
    except Exception as e:
        msg = str(e).lower()
        if any((k in msg for k in ("429", "rate limit", "too many", "quota"))):
            raise RateLimitError(str(e))
        raise TranslationError(str(e))


def translate_worker(line_idx: int, start: int, end: int, text: str):
    if _interrupted:
        return (line_idx, start, end, text, False)
    try:
        return (line_idx, start, end, _translate(text), True)
    except Exception:
        return (line_idx, start, end, text, False)


def _progress_path(file_path: Path) -> Path:
    return file_path.with_suffix(file_path.suffix + ".xlprogress")


def save_progress(file_path: Path, done: dict, total: int) -> None:
    try:
        serializable_done = {}
        for line_num, segments in done.items():
            if isinstance(segments, dict):
                serializable_done[str(line_num)] = {f"{k[0]},{k[1]}": v for k, v in segments.items()}
        state = {
            "file": str(file_path),
            "saved_at": datetime.now().isoformat(),
            "total_lines": total,
            "translations": serializable_done,
        }
        _progress_path(file_path).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"   ⚠️  Could not save progress: {e}")


def load_progress(file_path: Path) -> dict:
    p = _progress_path(file_path)
    if not p.exists():
        return {}
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
        restored = {}
        for line_num_str, segments in state["translations"].items():
            line_num = int(line_num_str)
            restored_segments = {}
            for key, trans in segments.items():
                start, end = map(int, key.split(","))
                restored_segments[start, end] = trans
            restored[line_num] = restored_segments
        return restored
    except Exception:
        return {}


def drop_progress(file_path: Path) -> None:
    p = _progress_path(file_path)
    if p.exists():
        p.unlink(missing_ok=True)


def process_file(path: Path) -> bool:
    global _interrupted
    print(f"\n📄 {path}")
    try:
        text, enc = read_text(path)
    except Exception as e:
        print(f"   ❌ Cannot read file: {e}")
        return False
    lines = text.splitlines(keepends=True)
    line_segments = {}
    for i, ln in enumerate(lines):
        stripped = ln.rstrip("\r\n")
        segments = find_chinese_segments(stripped)
        if segments:
            line_segments[i] = segments
    if not line_segments:
        print(f"   ✅ No Chinese characters found — skipping")
        drop_progress(path)
        return True
    total_segments = sum((len(segs) for segs in line_segments.values()))
    done = load_progress(path)
    for line_idx in line_segments:
        if line_idx not in done:
            done[line_idx] = {}
    tasks = []
    for line_idx, segments in line_segments.items():
        for start, end, chinese_text in segments:
            if (start, end) not in done[line_idx]:
                tasks.append((line_idx, start, end, chinese_text))
    completed_segments = total_segments - len(tasks)
    if completed_segments > 0:
        print(f"   🔄 Resuming: {completed_segments}/{total_segments} segments already cached")
    if tasks:
        print(f"   ⚡ Launching {MAX_WORKERS} parallel threads for {len(tasks)} segments...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(translate_worker, l_idx, s, e, txt): (l_idx, s, e, txt) for l_idx, s, e, txt in tasks
            }
            for future in as_completed(futures):
                l_idx, s, e, result_text, success = future.result()
                done[l_idx][s, e] = result_text
                completed_segments += 1
                status = "✓" if success else "❌ Failed"
                print(f"   [{completed_segments:>4}/{total_segments}] {status} line {l_idx + 1}")
                if completed_segments % PROGRESS_SAVE_EVERY == 0 or _interrupted:
                    save_progress(path, done, len(lines))
                    if _interrupted:
                        break
    out_lines = []
    for i, line in enumerate(lines):
        if i in done and done[i]:
            eol = line[len(line.rstrip("\r\n")) :]
            stripped = line.rstrip("\r\n")
            reassembled = reassemble_line(stripped, done[i])
            out_lines.append(reassembled + eol)
        else:
            out_lines.append(line)
    tmp = path.with_suffix(path.suffix + ".xltmp")
    try:
        tmp.write_text("".join(out_lines), encoding=enc, errors="replace")
        tmp.rename(path)
    except Exception as e:
        print(f"   ❌ Failed to write output: {e}")
        return False
    finally:
        tmp.unlink(missing_ok=True)
    if not _interrupted:
        drop_progress(path)
        print(f"   ✅ Done.")
        return True
    return False


def main():
    args = sys.argv[1:]
    files = [Path(p) for p in args if Path(p).is_file()] if args else get_nobinary(Path.cwd())
    for f in files:
        if _interrupted:
            break
        process_file(f)
    if _interrupted:
        print("\n⚠️  Stopped early. Run again to resume from saved progress.")
    else:
        print("\n✅ All done processing all files.")


if __name__ == "__main__":
    main()
