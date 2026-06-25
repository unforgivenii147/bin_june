#!/data/data/com.termux/files/usr/bin/python
import cv2
import numpy as np
from pathlib import Path
from multiprocessing import Pool, cpu_count
from typing import Tuple, Dict, List
import shutil
from tqdm import tqdm


class ImageSimilarityOrganizer:
    def __init__(self, root_dir: str, similarity_threshold: float = 0.95, hash_size: int = 8):
        """
        Initialize the image organizer.

        Args:
            root_dir: Root directory to search for images recursively
            similarity_threshold: Threshold for considering images similar (0-1)
            hash_size: Size for perceptual hash (8, 16, 32, etc.)
        """
        self.root_dir = Path(root_dir)
        self.similarity_threshold = similarity_threshold
        self.hash_size = hash_size
        self.supported_formats = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif"}
        print(f"[INIT] Root directory: {self.root_dir}")
        print(f"[INIT] Similarity threshold: {similarity_threshold}")
        print(f"[INIT] Hash size: {hash_size}x{hash_size}")

    def get_all_images(self) -> List[Path]:
        """Recursively find all image files in the root directory."""
        print("\n[SCAN] Scanning for image files...")
        image_files = []
        for fmt in self.supported_formats:
            image_files.extend(self.root_dir.rglob(f"*{fmt}"))
            image_files.extend(self.root_dir.rglob(f"*{fmt.upper()}"))

        image_files = list(set(image_files))  # Remove duplicates
        print(f"[SCAN] Found {len(image_files)} image(s)")
        return sorted(image_files)

    @staticmethod
    def compute_perceptual_hash(image_path: Path, hash_size: int = 8) -> Tuple[Path, np.ndarray]:
        """
        Compute perceptual hash of an image using average hash method.

        Args:
            image_path: Path to the image
            hash_size: Size of the hash

        Returns:
            Tuple of (image_path, hash_array)
        """
        try:
            # Read image in grayscale
            img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                return image_path, None

            # Resize to hash_size x hash_size
            img_resized = cv2.resize(img, (hash_size, hash_size))

            # Compute average pixel value
            avg = img_resized.mean()

            # Create hash: 1 if pixel > avg, 0 otherwise
            hash_array = (img_resized > avg).flatten().astype(int)

            return image_path, hash_array
        except Exception as e:
            print(f"[ERROR] Failed to hash {image_path}: {str(e)}")
            return image_path, None

    def compute_hashes(self, image_paths: List[Path]) -> Dict[Path, np.ndarray]:
        """
        Compute perceptual hashes for all images using multiprocessing.

        Args:
            image_paths: List of image paths

        Returns:
            Dictionary mapping image paths to their hashes
        """
        print(f"\n[HASH] Computing perceptual hashes using {cpu_count()} processes...")

        hashes = {}
        with Pool(processes=cpu_count()) as pool:
            # Create partial function with hash_size parameter
            from functools import partial

            compute_func = partial(self.compute_perceptual_hash, hash_size=self.hash_size)

            # Process images with progress bar
            results = list(
                tqdm(
                    pool.imap_unordered(compute_func, image_paths),
                    total=len(image_paths),
                    desc="Hashing images",
                    unit="img",
                )
            )

        # Store valid hashes
        for image_path, hash_array in results:
            if hash_array is not None:
                hashes[image_path] = hash_array

        print(f"[HASH] Successfully hashed {len(hashes)} image(s)")
        return hashes

    @staticmethod
    def hamming_distance(hash1: np.ndarray, hash2: np.ndarray) -> int:
        """
        Calculate Hamming distance between two hashes.
        Lower distance = more similar images.
        """
        return np.sum(hash1 != hash2)

    def find_similar_images(self, hashes: Dict[Path, np.ndarray]) -> Dict[int, List[Path]]:
        """
        Group similar images together.

        Args:
            hashes: Dictionary of image paths to their hashes

        Returns:
            Dictionary of group_id to list of similar image paths
        """
        print(f"\n[GROUP] Grouping similar images (threshold: {self.similarity_threshold})...")

        image_list = list(hashes.keys())
        groups = {}
        group_id = 0
        assigned = set()
        max_distance = int((1 - self.similarity_threshold) * len(hashes[image_list[0]]))

        print(f"[GROUP] Max allowed hamming distance: {max_distance}")

        for i, img_path in enumerate(tqdm(image_list, desc="Grouping images", unit="img")):
            if img_path in assigned:
                continue

            # Start a new group
            groups[group_id] = [img_path]
            assigned.add(img_path)

            # Find all similar images
            for j, other_path in enumerate(image_list):
                if i >= j or other_path in assigned:
                    continue

                distance = self.hamming_distance(hashes[img_path], hashes[other_path])
                similarity = 1 - (distance / len(hashes[img_path]))

                if similarity >= self.similarity_threshold:
                    groups[group_id].append(other_path)
                    assigned.add(other_path)

            group_id += 1

        print(f"[GROUP] Created {len(groups)} group(s)")
        return groups

    def organize_images(self, groups: Dict[int, List[Path]]) -> None:
        """
        Create folders and move similar images into them.

        Args:
            groups: Dictionary of group_id to list of image paths
        """
        print(f"\n[ORGANIZE] Creating folders and organizing images...")

        for group_id, image_paths in tqdm(groups.items(), desc="Organizing", unit="group"):
            if len(image_paths) == 1:
                continue  # Skip single-image groups

            # Create group folder
            group_folder = self.root_dir / f"similar_group_{group_id:04d}"
            group_folder.mkdir(exist_ok=True)

            # Move images to group folder
            for img_path in image_paths:
                try:
                    dest_path = group_folder / img_path.name

                    # Handle filename conflicts
                    counter = 1
                    while dest_path.exists():
                        stem = img_path.stem
                        suffix = img_path.suffix
                        dest_path = group_folder / f"{stem}_{counter}{suffix}"
                        counter += 1

                    shutil.move(str(img_path), str(dest_path))
                except Exception as e:
                    print(f"[ERROR] Failed to move {img_path}: {str(e)}")

        print(f"[ORGANIZE] Done! Check {self.root_dir} for organized groups")

    def run(self) -> None:
        """Execute the full pipeline."""
        print("=" * 60)
        print("IMAGE SIMILARITY ORGANIZER")
        print("=" * 60)

        # Get all images
        image_paths = self.get_all_images()

        if not image_paths:
            print("[WARN] No images found!")
            return

        # Compute hashes
        hashes = self.compute_hashes(image_paths)

        if not hashes:
            print("[ERROR] Could not hash any images!")
            return

        # Group similar images
        groups = self.find_similar_images(hashes)

        # Organize into folders
        self.organize_images(groups)

        print("\n" + "=" * 60)
        print("PROCESS COMPLETE")
        print("=" * 60)


if __name__ == "__main__":
    # Configuration
    ROOT_DIRECTORY = Path.cwd()
    SIMILARITY_THRESHOLD = 0.90  # 0-1, higher = more strict matching

    organizer = ImageSimilarityOrganizer(
        root_dir=ROOT_DIRECTORY,
        similarity_threshold=SIMILARITY_THRESHOLD,
        hash_size=16,  # Increase for more accuracy but slower processing
    )
    organizer.run()
