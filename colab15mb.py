#!/data/data/com.termux/files/usr/bin/python

import os
import site
import tarfile
from pathlib import Path

from google.colab import files


def gsz(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if Path(fp).is_file():
                total += Path(fp).stat().st_size
    return total


def compress_small_site_packages(max_size_mb: int = 15) -> None:
    site_packages_dir = site.getsitepackages()[0]
    output_file = "site-packages-small.tar.gz"
    with tarfile.open(output_file, "w:gz") as tar:
        for item in os.listdir(site_packages_dir):
            item_path = os.path.join(site_packages_dir, item)
            if Path(item_path).is_dir():
                get_size_mb = gsz(item_path) / (1024 * 1024)
                if get_size_mb <= max_size_mb:
                    print(f"Including folder {item} ({get_size_mb:.2f} MB)")
                    for root, _dirs, files_list in os.walk(item_path):
                        for f in files_list:
                            if not f.endswith(".pyc"):
                                full_path = os.path.join(root, f)
                                arcname = os.path.relpath(full_path, site_packages_dir)
                                tar.add(full_path, arcname=arcname)
            elif Path(item_path).is_file():
                get_size_mb = Path(item_path).stat().st_size / (1024 * 1024)
                if get_size_mb <= max_size_mb and (not item.endswith(".pyc")):
                    print(f"Including file {item} ({get_size_mb:.2f} MB)")
                    arcname = os.path.relpath(item_path, site_packages_dir)
                    tar.add(item_path, arcname=arcname)
    print(f"Archive created: {output_file}")
    files.download(output_file)


compress_small_site_packages(max_size_mb=15)
