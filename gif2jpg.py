#!/data/data/com.termux/files/usr/bin/python
"""
Convert GIF files in the current directory (recursively) to JPG.
Skips near-duplicate frames where only minor motion (e.g. mouse pointer) occurred.

Dependencies:
    pip install Pillow joblib numpy
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed
from PIL import Image, UnidentifiedImageError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Root directory to search (change to a Path argument if desired)
SEARCH_ROOT = Path(".")

# JPEG quality for saved frames
JPEG_QUALITY = 90

# Similarity threshold: frames whose mean absolute pixel difference (0‒255)
# is below this value are considered "near-duplicate" and skipped.
# Tune upward if real content changes are still being skipped.
SIMILARITY_THRESHOLD = 8.0

# Minimum fraction of pixels that must differ for a frame to be kept.
# Helps catch cases where only a tiny cursor region changed.
MIN_CHANGED_PIXEL_FRACTION = 0.005  # 0.5 % of all pixels

# Number of parallel workers (-1 = all CPUs)
N_JOBS = -1

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def frames_are_similar(arr_a: np.ndarray, arr_b: np.ndarray) -> bool:
    """
    Return True when two frames are visually near-identical.

    Two independent criteria must *both* pass for a frame to be skipped:
      1. Mean absolute pixel difference is below SIMILARITY_THRESHOLD.
      2. The fraction of pixels that changed by more than 10 intensity units
         is below MIN_CHANGED_PIXEL_FRACTION.

    Using both criteria makes the filter robust: a mouse cursor creates a
    small but locally bright change that raises criterion 2 yet keeps the
    global mean (criterion 1) low.  Requiring *both* thresholds to pass
    avoids false positives on frames with subtle but real content changes.
    """
    if arr_a.shape != arr_b.shape:
        return False

    diff = np.abs(arr_a.astype(np.int16) - arr_b.astype(np.int16))
    mean_diff = diff.mean()
    changed_fraction = (diff > 10).any(axis=-1).mean()  # per-pixel, any channel

    return mean_diff < SIMILARITY_THRESHOLD and changed_fraction < MIN_CHANGED_PIXEL_FRACTION


def extract_unique_frames(gif_path: Path) -> list[np.ndarray]:
    """
    Open a GIF, composite each frame onto a white background (handles
    disposal modes / transparency), and return only frames that differ
    meaningfully from the previous kept frame.
    """
    frames: list[np.ndarray] = []

    try:
        with Image.open(gif_path) as img:
            if not hasattr(img, "n_frames"):
                # Static image treated as single-frame GIF
                canvas = Image.new("RGB", img.size, (255, 255, 255))
                canvas.paste(
                    img.convert("RGBA"), mask=img.convert("RGBA").split()[3] if img.mode in ("RGBA", "P") else None
                )
                frames.append(np.asarray(canvas))
                return frames

            # We reconstruct the full composite for every frame to correctly
            # handle GIF disposal methods (replace, restore-to-background, etc.)
            canvas = Image.new("RGB", img.size, (255, 255, 255))
            prev_frame_img: Image.Image | None = None

            for frame_idx in range(img.n_frames):
                img.seek(frame_idx)

                disposal = img.info.get("disposal", 0)

                # Restore canvas to previous state when disposal == 3
                if disposal == 3 and prev_frame_img is not None:
                    canvas = prev_frame_img.copy()
                elif disposal == 2:
                    # Restore to background colour
                    canvas = Image.new("RGB", img.size, (255, 255, 255))

                prev_frame_img = canvas.copy()

                frame = img.convert("RGBA")
                canvas.paste(frame, mask=frame.split()[3])

                arr = np.asarray(canvas.convert("RGB"))

                if frames and frames_are_similar(frames[-1], arr):
                    log.debug("  Skipping near-duplicate frame %d in %s", frame_idx, gif_path.name)
                    continue

                frames.append(arr)

    except (UnidentifiedImageError, OSError) as exc:
        log.error("Cannot open %s: %s", gif_path, exc)

    return frames


def convert_gif(gif_path: Path) -> tuple[Path, int, int]:
    """
    Convert a single GIF to one or more JPG files next to the source.
    Returns (gif_path, total_frames, saved_frames).
    """
    frames = extract_unique_frames(gif_path)
    if not frames:
        log.warning("No usable frames in %s", gif_path)
        return gif_path, 0, 0

    total_in_gif = 0
    try:
        with Image.open(gif_path) as probe:
            total_in_gif = getattr(probe, "n_frames", 1)
    except OSError:
        pass

    stem = gif_path.stem
    out_dir = gif_path.parent
    zero_pad = len(str(len(frames)))  # pad frame numbers consistently

    saved = 0
    for idx, arr in enumerate(frames):
        if len(frames) == 1:
            out_path = out_dir / f"{stem}.jpg"
        else:
            out_path = out_dir / f"{stem}_frame{idx:0{zero_pad}d}.jpg"

        # Skip if already up-to-date (re-run safety)
        if out_path.exists() and out_path.stat().st_mtime >= gif_path.stat().st_mtime:
            log.debug("  Up-to-date, skipping: %s", out_path.name)
            saved += 1
            continue

        img = Image.fromarray(arr, mode="RGB")
        try:
            img.save(out_path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            saved += 1
        except OSError as exc:
            log.error("Failed to save %s: %s", out_path, exc)

    log.info("%-50s  %d/%d frames kept → %d JPG(s)", str(gif_path), len(frames), total_in_gif, saved)
    return gif_path, total_in_gif, saved


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    gif_files = sorted(SEARCH_ROOT.rglob("*.gif"))
    # Also catch upper-case extensions on case-sensitive filesystems
    gif_files += sorted(SEARCH_ROOT.rglob("*.GIF"))
    # Deduplicate (resolve handles symlinks + normalises path on all OSes)
    seen: set[Path] = set()
    unique_gifs: list[Path] = []
    for p in gif_files:
        r = p.resolve()
        if r not in seen:
            seen.add(r)
            unique_gifs.append(p)

    if not unique_gifs:
        log.info("No GIF files found under %s", SEARCH_ROOT.resolve())
        return

    log.info(
        "Found %d GIF file(s). Starting conversion with %s workers…",
        len(unique_gifs),
        "all CPUs" if N_JOBS == -1 else str(N_JOBS),
    )

    results = Parallel(n_jobs=N_JOBS, backend="loky", verbose=0)(delayed(convert_gif)(p) for p in unique_gifs)

    total_gifs = len(results)
    total_frames = sum(r[1] for r in results)
    total_saved = sum(r[2] for r in results)
    log.info("Done. %d GIF(s) processed — %d/%d frames saved as JPG.", total_gifs, total_saved, total_frames)


if __name__ == "__main__":
    main()
