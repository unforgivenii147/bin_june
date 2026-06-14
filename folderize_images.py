#!/data/data/com.termux/files/usr/bin/python

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

import imagehash
from PIL import Image

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}


@dataclass(frozen=True)
class HashedImage:
    path: Path
    h: imagehash.ImageHash


def iter_image_paths(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            yield p


def compute_hash(path: Path, hash_func: str, hash_size: int) -> HashedImage | None:
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            if hash_func == "phash":
                h = imagehash.phash(img, hash_size=hash_size)
            elif hash_func == "dhash":
                h = imagehash.dhash(img, hash_size=hash_size)
            elif hash_func == "ahash":
                h = imagehash.average_hash(img, hash_size=hash_size)
            else:
                raise ValueError(msg)
            return HashedImage(path=path, h=h)
    except Exception as e:
        print(f"[WARN] Skipping {path} ({e})")
        return None


def hash_distance(h1: imagehash.ImageHash, h2: imagehash.ImageHash) -> int:
    return int(h1 - h2)


def folderize_by_similarity(
    root: Path,
    out_dir_name: str,
    hash_func: str,
    hash_size: int,
    threshold: int,
    move: bool,
    copy_duplicates_to_group_only: bool,
) -> None:
    out_dir = root / out_dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    images: list[HashedImage] = []
    for p in iter_image_paths(root):
        if out_dir_name in p.parts:
            continue
        hashed = compute_hash(p, hash_func=hash_func, hash_size=hash_size)
        if hashed is not None:
            images.append(hashed)
    if not images:
        print("No images found.")
        return
    groups: list[dict] = []
    for item in images:
        placed = False
        for g in groups:
            d = hash_distance(item.h, g["rep"])
            if d <= threshold:
                g["members"].append(item)
                placed = True
                break
        if not placed:
            groups.append({"rep": item.h, "members": [item]})
    group_idx = 0
    moved_or_copied = 0
    for g in groups:
        members = g["members"]
        if len(members) < 2:
            continue
        group_idx += 1
        group_folder = out_dir / f"group_{group_idx:06d}"
        group_folder.mkdir(parents=True, exist_ok=True)
        for mi, member in enumerate(members):
            dest = group_folder / member.path.name
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                k = 1
                while True:
                    dest2 = group_folder / f"{stem}_{k}{suffix}"
                    if not dest2.exists():
                        dest = dest2
                        break
                    k += 1
            if move:
                shutil.move(str(member.path), str(dest))
            else:
                shutil.copy2(str(member.path), str(dest))
            moved_or_copied += 1
    print(f"Found {len(groups)} groups (including singletons).")
    print(f"Action complete: {moved_or_copied} files {('moved' if move else 'copied')} into {out_dir}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Folderize images by similarity using imagehash.")
    parser.add_argument("--root", type=str, default=".", help="Root directory to scan (default: current dir)")
    parser.add_argument("--out", type=str, default="_similar_groups", help="Output folder name")
    parser.add_argument("--hash-func", type=str, default="phash", choices=["phash", "dhash", "ahash"])
    parser.add_argument("--hash-size", type=int, default=16, help="Hash size (bigger = more sensitive).")
    parser.add_argument("--threshold", type=int, default=8, help="Max Hamming distance to consider similar.")
    parser.add_argument("--move", action="store_true", help="Move files instead of copying")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    folderize_by_similarity(
        root=root,
        out_dir_name=args.out,
        hash_func=args.hash_func,
        hash_size=args.hash_size,
        threshold=args.threshold,
        move=args.move,
        copy_duplicates_to_group_only=False,
    )


if __name__ == "__main__":
    main()
