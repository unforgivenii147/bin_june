#!/data/data/com.termux/files/home/.local/bin/python
"""
Video Content Filter: Remove +16 rated content from videos.
Detects and removes inappropriate frames, saving cleaned output.

Usage:
    python video_filter.py <input_video> [-a] [--threshold 0.5] [--resume]
"""

import sys
import os
import argparse
import signal
import json
import pickle
from pathlib import Path
import cv2
import numpy as np
from datetime import datetime
from collections import deque

# Try importing optional dependencies
try:
    from ultralytics import YOLO

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: YOLO not available. Install with: pip install ultralytics")
    print("Using basic nudity detection as fallback.")

try:
    import tensorflow as tf

    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False

# Global flag for interrupt handling
interrupted = False
checkpoint_data = None


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global interrupted
    interrupted = True
    print("\n\n⚠️  Interrupt received! Saving progress...")
    print("Press Ctrl+C again to force quit (may corrupt files)")


class ContentFilter:
    def __init__(self, threshold=0.5, use_nsfw_model=True):
        self.threshold = threshold
        self.use_nsfw_model = use_nsfw_model
        self.model = None
        self.nsfw_detector = None
        self._initialize_models()

    def _initialize_models(self):
        """Initialize detection models"""
        if YOLO_AVAILABLE:
            try:
                # Load YOLO model for person/body part detection
                self.model = YOLO("yolov8n.pt")
                print("✓ YOLO model loaded")
            except Exception as e:
                print(f"⚠️  Could not load YOLO: {e}")
                self.model = None

        # Try to load NSFW detection model
        if self.use_nsfw_model:
            try:
                # Using a simple CNN-based approach
                self._init_nsfw_detector()
            except Exception as e:
                print(f"⚠️  Could not initialize NSFW detector: {e}")
                print("Will use heuristic-based detection")

    def _init_nsfw_detector(self):
        """Initialize simple NSFW detection using OpenCV"""
        # Simple skin color detection parameters
        self.skin_lower = np.array([0, 48, 80], dtype=np.uint8)
        self.skin_upper = np.array([20, 255, 255], dtype=np.uint8)

    def detect_inappropriate_content(self, frame):
        """
        Detect +16 content in a frame using multiple methods

        Returns: (is_inappropriate, confidence_score)
        """
        scores = []

        # Method 1: YOLO-based body part detection
        if self.model is not None:
            yolo_score = self._yolo_detection(frame)
            scores.append(yolo_score)

        # Method 2: Skin color ratio detection
        skin_score = self._skin_detection(frame)
        scores.append(skin_score)

        # Method 3: Texture/edge analysis for suggestive content
        texture_score = self._texture_analysis(frame)
        scores.append(texture_score)

        # Combine scores
        if scores:
            final_score = np.mean(scores)
            return final_score > self.threshold, final_score
        return False, 0.0

    def _yolo_detection(self, frame):
        """Use YOLO to detect potentially inappropriate body parts"""
        try:
            results = self.model(frame, verbose=False)
            inappropriate_count = 0

            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        cls = int(box.cls[0])
                        # Check for persons and specific body-related classes
                        if cls == 0:  # person class
                            confidence = float(box.conf[0])
                            # High confidence person detection might indicate nudity
                            if confidence > 0.7:
                                inappropriate_count += 1

            # Normalize score
            frame_area = frame.shape[0] * frame.shape[1]
            score = min(inappropriate_count / 10, 1.0)
            return score
        except Exception as e:
            return 0.0

    def _skin_detection(self, frame):
        """Detect skin color ratio in frame"""
        try:
            # Convert to HSV for better skin detection
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # Create skin mask
            skin_mask = cv2.inRange(hsv, self.skin_lower, self.skin_upper)

            # Apply morphological operations to clean mask
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)
            skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)

            # Calculate skin ratio
            total_pixels = skin_mask.shape[0] * skin_mask.shape[1]
            skin_pixels = cv2.countNonZero(skin_mask)
            skin_ratio = skin_pixels / total_pixels

            # High skin ratio might indicate nudity
            score = min(skin_ratio * 3, 1.0)  # Adjust multiplier as needed
            return score
        except Exception as e:
            return 0.0

    def _texture_analysis(self, frame):
        """Analyze texture patterns for inappropriate content"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Edge detection
            edges = cv2.Canny(gray, 50, 150)

            # Calculate edge density
            edge_density = np.mean(edges) / 255

            # Low edge density combined with other factors might indicate skin
            score = max(0, 1 - edge_density * 2)
            return score
        except:
            return 0.0


class VideoProcessor:
    def __init__(self, input_path, output_clean="cleaned.mp4", output_flagged="plus16.mp4", threshold=0.5):
        self.input_path = input_path
        self.output_clean = output_clean
        self.output_flagged = output_flagged
        self.threshold = threshold
        self.filter = ContentFilter(threshold=threshold)

        # Processing state
        self.cap = None
        self.writer_clean = None
        self.writer_flagged = None
        self.total_frames = 0
        self.processed_frames = 0
        self.flagged_frames = 0
        self.fps = 0
        self.frame_width = 0
        self.frame_height = 0

        # Checkpoint file
        self.checkpoint_file = f"{Path(input_path).stem}_checkpoint.json"

    def save_checkpoint(self, frame_number):
        """Save processing progress"""
        checkpoint = {
            "input_path": self.input_path,
            "processed_frames": frame_number,
            "total_frames": self.total_frames,
            "flagged_frames": self.flagged_frames,
            "timestamp": datetime.now().isoformat(),
            "fps": self.fps,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
        }

        try:
            with open(self.checkpoint_file, "w") as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            print(f"⚠️  Could not save checkpoint: {e}")

    def load_checkpoint(self):
        """Load previous processing state"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r") as f:
                    checkpoint = json.load(f)
                print(f"✓ Found checkpoint from {checkpoint['timestamp']}")
                print(f"  Progress: {checkpoint['processed_frames']}/{checkpoint['total_frames']} frames")
                return checkpoint
            except Exception as e:
                print(f"⚠️  Could not load checkpoint: {e}")
        return None

    def initialize_video(self):
        """Open video and get properties"""
        self.cap = cv2.VideoCapture(self.input_path)

        if not self.cap.isOpened():
            raise ValueError(f"Cannot open video: {self.input_path}")

        # Get video properties
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"📹 Video: {self.input_path}")
        print(f"   Resolution: {self.frame_width}x{self.frame_height}")
        print(f"   FPS: {self.fps}")
        print(f"   Total frames: {self.total_frames}")

    def initialize_writers(self, append=False):
        """Initialize video writers"""
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        # For clean output
        mode = "a" if append else "w"
        self.writer_clean = cv2.VideoWriter(self.output_clean, fourcc, self.fps, (self.frame_width, self.frame_height))

        # For flagged frames
        self.writer_flagged = cv2.VideoWriter(
            self.output_flagged, fourcc, self.fps, (self.frame_width, self.frame_height)
        )

    def process_video(self, resume=False):
        """Main video processing loop"""
        checkpoint = None
        start_frame = 0

        if resume:
            checkpoint = self.load_checkpoint()
            if checkpoint:
                start_frame = checkpoint["processed_frames"]
                self.flagged_frames = checkpoint.get("flagged_frames", 0)

        # Initialize video capture
        self.initialize_video()
        self.initialize_writers(append=(start_frame > 0))

        # Seek to checkpoint position if resuming
        if start_frame > 0:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            print(f"⏩ Resuming from frame {start_frame}")

        # Signal handler for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)

        print(f"\n🎬 Processing video...")
        print(f"   Output clean: {self.output_clean}")
        print(f"   Output flagged: {self.output_flagged}")
        print(f"   Threshold: {self.threshold}")
        print("\n⏸️  Press Ctrl+C to pause and save progress\n")

        # Process frames
        frame_buffer = deque(maxlen=5)  # Buffer for context-aware processing
        frame_number = start_frame

        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    break

                if interrupted:
                    print(f"\n💾 Saving progress at frame {frame_number}...")
                    self.save_checkpoint(frame_number)
                    break

                # Add frame to buffer
                frame_buffer.append(frame)

                # Detect inappropriate content
                is_inappropriate, confidence = self.filter.detect_inappropriate_content(frame)

                if is_inappropriate:
                    # Frame contains +16 content, skip it from clean output
                    self.writer_flagged.write(frame)
                    self.flagged_frames += 1

                    # Optional: Apply blur to frame before writing to clean
                    # This is an alternative to completely removing the frame
                    # blurred = cv2.GaussianBlur(frame, (99, 99), 30)
                    # self.writer_clean.write(blurred)
                else:
                    # Frame is clean
                    self.writer_clean.write(frame)

                self.processed_frames += 1
                frame_number += 1

                # Progress update
                if frame_number % 30 == 0:  # Update every 30 frames
                    progress = (frame_number / self.total_frames) * 100
                    flagged_pct = (self.flagged_frames / frame_number) * 100 if frame_number > 0 else 0

                    print(
                        f"\r⏳ Progress: {progress:.1f}% ({frame_number}/{self.total_frames}) "
                        f"| Flagged: {self.flagged_frames} ({flagged_pct:.1f}%) "
                        f"| Confidence: {confidence:.2f}",
                        end="",
                    )

                    # Auto-save checkpoint periodically
                    if frame_number % 300 == 0:  # Every 300 frames
                        self.save_checkpoint(frame_number)

        except Exception as e:
            print(f"\n❌ Error during processing: {e}")
            self.save_checkpoint(frame_number)
            raise

        finally:
            self.cleanup()

            if not interrupted:
                # Remove checkpoint on successful completion
                if os.path.exists(self.checkpoint_file):
                    os.remove(self.checkpoint_file)

        # Final summary
        print(f"\n\n✅ Processing complete!")
        print(f"   Total frames processed: {self.processed_frames}")
        print(
            f"   Flagged frames: {self.flagged_frames} ({(self.flagged_frames / self.processed_frames * 100):.1f}%)"
            if self.processed_frames > 0
            else ""
        )
        print(f"   Clean video saved to: {self.output_clean}")
        print(f"   Flagged frames saved to: {self.output_flagged}")

    def cleanup(self):
        """Release resources"""
        if self.cap is not None:
            self.cap.release()
        if self.writer_clean is not None:
            self.writer_clean.release()
        if self.writer_flagged is not None:
            self.writer_flagged.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        description="Remove +16 content from videos with checkpoint/resume support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python video_filter.py input.mp4
  
  # Save flagged frames to separate video
  python video_filter.py input.mp4 -a
  
  # Resume from checkpoint
  python video_filter.py input.mp4 -a --resume
  
  # Adjust detection threshold (0.0-1.0)
  python video_filter.py input.mp4 -a --threshold 0.7
        """,
    )

    parser.add_argument("input", help="Input video file path")
    parser.add_argument("-a", "--save-flagged", action="store_true", help="Save flagged frames to plus16.mp4")
    parser.add_argument("--threshold", type=float, default=0.5, help="Detection threshold (0.0-1.0, default: 0.5)")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument(
        "--output-clean", default="cleaned.mp4", help="Output filename for clean video (default: cleaned.mp4)"
    )
    parser.add_argument(
        "--output-flagged", default="plus16.mp4", help="Output filename for flagged frames (default: plus16.mp4)"
    )

    args = parser.parse_args()

    # Check if input file exists
    if not os.path.exists(args.input):
        print(f"❌ Error: Input file not found: {args.input}")
        sys.exit(1)

    # Validate threshold
    if not 0 <= args.threshold <= 1:
        print("❌ Error: Threshold must be between 0.0 and 1.0")
        sys.exit(1)

    try:
        # Initialize processor
        processor = VideoProcessor(
            input_path=args.input,
            output_clean=args.output_clean,
            output_flagged=args.output_flagged if args.save_flagged else None,
            threshold=args.threshold,
        )

        # Process video
        processor.process_video(resume=args.resume)

    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user")
        if "processor" in locals():
            processor.save_checkpoint(processor.processed_frames)
        print("Progress saved. Use --resume to continue later.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
