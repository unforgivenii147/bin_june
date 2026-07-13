#!/data/data/com.termux/files/usr/bin/env python
"""
Advanced script to download English subtitles with multiple providers.
"""

import os
import sys
import logging
from pathlib import Path
from subliminal import download_best_subtitles, save_subtitles
from subliminal.video import scan_video
from subliminal.core import ProviderPool
from subliminal.providers.opensubtitles import OpenSubtitlesProvider
import babelfish

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def download_subtitles_advanced(mkv_path, output_dir=None):
    """
    Advanced subtitle download with multiple providers.
    """
    mkv_path = Path(mkv_path)

    if not mkv_path.exists():
        logger.error(f"File not found: {mkv_path}")
        return False

    if output_dir is None:
        output_dir = mkv_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    # Scan video
    try:
        video = scan_video(mkv_path)
        logger.info(f"Processing: {video.name}")
    except Exception as e:
        logger.error(f"Error scanning: {e}")
        return False

    # Set up providers with priority order
    providers = ["opensubtitles", "podnapisi", "addic7ed", "tvsubtitles"]

    # Download subtitles
    language = babelfish.Language("eng")

    try:
        subtitles = download_best_subtitles([video], {language}, providers=providers)

        video_subtitles = subtitles.get(video, {})

        if not video_subtitles:
            logger.warning(f"No English subtitles found")
            return False

        # Save as SRT
        subtitle_path = output_dir / f"{mkv_path.stem}.en.srt"
        save_subtitles(video, video_subtitles, single=True, path=subtitle_path)
        logger.info(f"✓ Subtitles saved: {subtitle_path}")

        return True

    except Exception as e:
        logger.error(f"Error: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python subtitle_downloader.py <movie.mkv> [output_dir]")
        sys.exit(1)

    success = download_subtitles_advanced(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    sys.exit(0 if success else 1)
