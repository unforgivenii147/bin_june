#!/data/data/com.termux/files/home/.local/bin/python
from __future__ import annotations

import json
import os
from pathlib import Path


def merge_translations(src_dir="."):
    translations = {}
    failed = []
    processed = set()
    all_files = sorted([f for f in os.listdir(src_dir) if f.endswith(".txt")])
    for fa_file in all_files:
        if fa_file in processed or fa_file.endswith("_en.txt"):
            continue
        base_name = fa_file[:-4]
        en_file = f"{base_name}_en.txt"
        fa_path = Path(src_dir) / fa_file
        en_path = Path(src_dir) / en_file
        if not en_path.exists():
            print(f"⚠️  Skipping {fa_file}: {en_file} not found")
            continue
        try:
            with open(fa_path, "r", encoding="utf-8") as f_fa, open(en_path, "r", encoding="utf-8") as f_en:
                fa_lines = [line.strip() for line in f_fa if line.strip()]
                en_lines = [line.strip() for line in f_en if line.strip()]
            if len(fa_lines) != len(en_lines):
                print(f"⚠️  Line count mismatch: {fa_file} ({len(fa_lines)}) vs {en_file} ({len(en_lines)})")
            for fa_word, en_word in zip(fa_lines, en_lines, strict=False):
                if fa_word == en_word:
                    failed.append(fa_word)
                else:
                    translations[fa_word] = en_word
            print(f"✓ Processed {fa_file} + {en_file}")
            processed.add(fa_file)
            processed.add(en_file)
        except Exception as e:
            print(f"❌ Error processing {fa_file}: {e}")
    with open("dic.json", "w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, indent=2)
    with open("failed_fa.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(failed))
    print(f"\n✓ {len(translations)} translations → dic.json")
    print(f"✓ {len(failed)} failed → failed_fa.txt")


if __name__ == "__main__":
    merge_translations()
