#!/data/data/com.termux/files/usr/bin/env python
"""
Script to download English subtitles for an MKV movie using Subliminal.
"""

import os
import sys
import logging
from pathlib import Path
from subliminal import download_best_subtitles, save_subtitles
from subliminal.video import scan_video
from subliminal.providers import ProviderError
import babelfish

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_english_subtitles(mkv_path, output_dir=None):
    """
    Download English subtitles for an MKV file.

    Args:
        mkv_path (str): Path to the MKV file
        output_dir (str, optional): Directory to save subtitles.
                                   If None, saves to the same directory as the MKV.

    Returns:
        bool: True if subtitles were downloaded successfully, False otherwise.
    """
    mkv_path = Path(mkv_path)

    # Check if file exists
    if not mkv_path.exists():
        logger.error(f"File not found: {mkv_path}")
        return False

    # Check if it's an MKV file
    if mkv_path.suffix.lower() != ".mkv":
        logger.warning(f"File is not an MKV: {mkv_path}")

    # Set output directory
    if output_dir is None:
        output_dir = mkv_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    # Scan the video file
    logger.info(f"Scanning video: {mkv_path}")
    try:
        video = scan_video(mkv_path)
        logger.info(f"Found video: {video.name}")
        logger.info(f"  - Size: {video.size} bytes")
        logger.info(f"  - Duration: {video.duration:.2f} seconds")
        logger.info(f"  - Hashes: {video.hashes}")
    except Exception as e:
        logger.error(f"Error scanning video: {e}")
        return False

    # Language to download
    language = babelfish.Language("eng")

    # Download subtitles
    logger.info(f"Searching for English subtitles...")
    try:
        subtitles = download_best_subtitles(
            [video], {language}, providers=["opensubtitles", "podnapisi", "addic7ed", "tvsubtitles"]
        )

        # Get subtitles for this video
        video_subtitles = subtitles.get(video, {})

        if not video_subtitles:
            logger.warning(f"No English subtitles found for {mkv_path.name}")
            return False

        # Save subtitles
        subtitle_path = output_dir / f"{mkv_path.stem}.srt"
        save_subtitles(video, video_subtitles, single=True, path=subtitle_path)
        logger.info(f"Subtitles saved to: {subtitle_path}")

        return True

    except ProviderError as e:
        logger.error(f"Provider error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error downloading subtitles: {e}")
        return False


def main():
    """Main function with command-line interface."""
    if len(sys.argv) < 2:
        print("Usage: python subtitle_downloader.py <path_to_mkv_file> [output_directory]")
        print("Example: python subtitle_downloader.py movie.mkv")
        print("Example: python subtitle_downloader.py /path/to/movie.mkv /path/to/subtitles/")
        sys.exit(1)

    mkv_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    success = get_english_subtitles(mkv_path, output_dir)

    if success:
        print("✓ Subtitles downloaded successfully!")
    else:
        print("✗ Failed to download subtitles.")
        sys.exit(1)


if __name__ == "__main__":
    main()
