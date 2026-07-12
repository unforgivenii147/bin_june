#!/data/data/com.termux/files/usr/bin/env python

"""
Translate fully-Vietnamese text files to English.
Output is saved as <original_filename>.en beside the source file.
Chunks text at ~5000 chars on paragraph/line boundaries to stay
under the Google Translate limit.
"""

import json
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from deep_translator import GoogleTranslator
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


# ── config ────────────────────────────────────────────────────────────────────

MAX_CHUNK_CHARS = 4800  # safely under the 5000-char API limit
DELAY_BETWEEN_CHUNKS = 1.2  # seconds between requests
DELAY_BETWEEN_FILES = 3.0
MAX_RETRIES = 5
PROGRESS_SAVE_EVERY = 5  # save after every N translated chunks

# ── logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

# ── graceful interrupt ────────────────────────────────────────────────────────

_interrupted = False


def _sigint_handler(sig, frame):
    global _interrupted
    print("\n⚠️  Ctrl+C — finishing current chunk then stopping.")
    _interrupted = True


signal.signal(signal.SIGINT, _sigint_handler)

# ── encoding-resilient reader ─────────────────────────────────────────────────


def read_text(path: Path) -> tuple[str, str]:
    for enc in ("utf-8", "utf-8-sig", "utf-16", "cp1258", "gb18030"):
        try:
            return path.read_text(encoding=enc, errors="strict"), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return path.read_bytes().decode("utf-8", errors="replace"), "utf-8"


# ── chunking ──────────────────────────────────────────────────────────────────


def split_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """
    Split text into chunks that don't exceed max_chars.
    Tries to break on double-newlines (paragraphs), then single newlines,
    then spaces — never mid-word.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text

    while len(remaining) > max_chars:
        window = remaining[:max_chars]

        # prefer paragraph boundary
        cut = window.rfind("\n\n")
        if cut == -1 or cut < max_chars // 4:
            # fall back to line boundary
            cut = window.rfind("\n")
        if cut == -1 or cut < max_chars // 4:
            # last resort: word boundary
            cut = window.rfind(" ")
        if cut == -1:
            # no whitespace at all — hard cut
            cut = max_chars

        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")  # drop leading blank lines

    if remaining:
        chunks.append(remaining)

    return chunks


# ── translation with tenacity ─────────────────────────────────────────────────


class RateLimitError(Exception):
    pass


class TranslationError(Exception):
    pass


@retry(
    reraise=True,
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential_jitter(initial=3, max=90, jitter=4),
    retry=retry_if_exception_type((RateLimitError, TranslationError)),
    before_sleep=before_sleep_log(log, logging.DEBUG),
)
def _translate_chunk(text: str) -> str:
    try:
        result = GoogleTranslator(source="vi", target="en").translate(text)
        if result is None or result.strip() == "":
            raise TranslationError("Empty result returned")
        return result
    except (RateLimitError, TranslationError):
        raise
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("429", "rate limit", "too many", "quota")):
            print("   ⏳ Rate limited — backing off…")
            raise RateLimitError(str(e))
        if any(k in msg for k in ("timeout", "timed out", "connection", "reset")):
            raise TranslationError(str(e))
        raise TranslationError(str(e))


def translate_chunk_safe(text: str, idx: int) -> tuple[str, bool]:
    """Never raises. Returns (translated, success)."""
    try:
        return _translate_chunk(text), True
    except Exception as e:
        print(f"   ❌ Chunk {idx} failed after all retries: {e}")
        return text, False  # keep original on hard failure


# ── progress persistence ──────────────────────────────────────────────────────


def _progress_path(src: Path) -> Path:
    return src.with_name(src.name + ".viprogress")


def save_progress(src: Path, done: dict[int, str], total: int) -> None:
    try:
        state = {
            "source": str(src),
            "saved_at": datetime.now().isoformat(),
            "total_chunks": total,
            "chunks": {str(k): v for k, v in done.items()},
        }
        _progress_path(src).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"   ⚠️  Could not save progress: {e}")


def load_progress(src: Path) -> dict[int, str]:
    p = _progress_path(src)
    if not p.exists():
        return {}
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
        if Path(state.get("source", "")) != src:
            return {}
        restored = {int(k): v for k, v in state["chunks"].items()}
        print(f"   🔄 Resuming: {len(restored)} chunk(s) already done")
        return restored
    except Exception:
        return {}


def drop_progress(src: Path) -> None:
    p = _progress_path(src)
    try:
        p.unlink(missing_ok=True)
    except Exception:
        pass


# ── output path ───────────────────────────────────────────────────────────────


def output_path(src: Path) -> Path:
    """foo.txt  →  foo.txt.en
    bar      →  bar.en"""
    return src.with_name(src.name + ".en")


# ── per-file processor ────────────────────────────────────────────────────────


def process_file(path: Path) -> bool:
    global _interrupted

    out = output_path(path)
    print(f"\n📄 {path.name}  →  {out.name}")

    try:
        text, _enc = read_text(path)
    except Exception as e:
        print(f"   ❌ Cannot read: {e}")
        return False

    if not text.strip():
        print("   ⚠️  File is empty — skipping")
        return True

    chunks = split_into_chunks(text)
    total = len(chunks)
    print(f"   📦 {total} chunk(s)  |  file size: {len(text):,} chars")

    done: dict[int, str] = load_progress(path)
    failed_count = 0

    for i, chunk in enumerate(chunks):
        if _interrupted:
            save_progress(path, done, total)
            print("   💾 Progress saved.")
            return False

        if i in done:
            print(f"   [{i + 1:>3}/{total}] ⏭  skipped (cached)")
            continue

        translated, ok = translate_chunk_safe(chunk, i)
        done[i] = translated

        if not ok:
            failed_count += 1

        char_preview = chunk[:40].replace("\n", "↵").strip()
        status = "✓" if ok else "✗"
        print(f"   [{i + 1:>3}/{total}] {status}  {char_preview!r}…")

        if (i + 1) % PROGRESS_SAVE_EVERY == 0:
            save_progress(path, done, total)

        if i < total - 1 and not _interrupted:
            time.sleep(DELAY_BETWEEN_CHUNKS)

    # assemble in order
    translated_text = "\n".join(done[i] for i in range(total))

    try:
        out.write_text(translated_text, encoding="utf-8")
    except Exception as e:
        print(f"   ❌ Failed to write output: {e}")
        return False

    drop_progress(path)

    if failed_count:
        print(f"   ⚠️  Done with {failed_count} chunk(s) untranslated — check {out.name}")
    else:
        print(f"   ✅ Saved → {out}")

    return True


# ── entry
