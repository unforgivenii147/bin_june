#!/data/data/com.termux/files/usr/bin/python

import contextlib
import os

import matplotlib.pyplot as plt

current_dir = os.getcwd()
subdir_sizes = {}
total_size = 0
for dirpath, dirnames, filenames in os.walk(current_dir):
    dir_size = 0
    for f in filenames:
        fp = os.path.join(dirpath, f)
        with contextlib.suppress(OSError):
            dir_size += os.path.getsize(fp)
    if dirpath != current_dir:
        subdir_sizes[dirpath] = dir_size
        total_size += dir_size
    else:
        for f in filenames:
            fp = os.path.join(dirpath, f)
            with contextlib.suppress(OSError):
                total_size += os.path.getsize(fp)
subdir_percentages = {}
for subdir, size in subdir_sizes.items():
    if total_size > 0:
        percentage = size / total_size * 100
        subdir_percentages[os.path.basename(subdir)] = percentage
    else:
        subdir_percentages[os.path.basename(subdir)] = 0
labels = list(subdir_percentages.keys())
sizes = list(subdir_percentages.values())
reshaped_labels = []
for label in labels:
    reshaped_labels.append(label)
fig, ax = plt.subplots(figsize=(10, 10))
ax.pie(sizes, labels=reshaped_labels, autopct="%1.1f%%beding", startangle=140)
ax.axis("equal")
title = "subdirs sizes"
plt.title(title)
output_filename = "size.png"
plt.savefig(output_filename, bbox_inches="tight")
print(f"saved '{output_filename}'")
print(f"size: {total_size}")
