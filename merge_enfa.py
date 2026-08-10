#!/data/data/com.termux/files/home/.local/bin/python
import json
import re
from pathlib import Path


def merge_translation_files(base_dir=".", output_file="dic.json", failed_file="failed.txt"):
    base_path = Path(base_dir)
    base_files = {f for f in base_path.iterdir() if f.is_file() and re.match(r"^\d+$", f.name)}
    dictionary = {}
    failed_entries = []
    for en_file in sorted(base_files, key=lambda x: int(x.name)):
        fa_file = base_path / f"{en_file.name}_fa"
        if not fa_file.exists():
            print(f"⚠️  Warning: Missing {fa_file.name} for {en_file.name}")
            continue
        with open(en_file, "r", encoding="utf-8") as f_en, open(fa_file, "r", encoding="utf-8") as f_fa:
            en_lines = [line.strip() for line in f_en if line.strip()]
            fa_lines = [line.strip() for line in f_fa if line.strip()]
            if len(en_lines) != len(fa_lines):
                print(
                    f"⚠️  Mismatch: {en_file.name} has {len(en_lines)} lines, {fa_file.name} has {len(fa_lines)} lines"
                )
            for en_word, fa_word in zip(en_lines, fa_lines):
                if en_word.lower() == fa_word.lower():
                    failed_entries.append(en_word)
                else:
                    dictionary[en_word] = fa_word
    with open(base_path / output_file, "w", encoding="utf-8") as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=2)
    with open(base_path / failed_file, "w", encoding="utf-8") as f:
        f.write("\n".join(failed_entries))
    print(f"✅ Merged {len(dictionary)} entries → {output_file}")
    print(f"⚠️  Skipped {len(failed_entries)} untranslated entries → {failed_file}")
    return dictionary, failed_entries


if __name__ == "__main__":
    merge_translation_files()
