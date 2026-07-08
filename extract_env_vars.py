#!/data/data/com.termux/files/usr/bin/env python


import builtins
import re
from pathlib import Path

env_vars = set()
env_var_pattern = re.compile("^([A-Z_0-9]+)=")
for filepath in Path().rglob("*"):
    if ".git" in path.parts:
        continue
    if filepath.is_file():
        try:
            with builtins.open(filepath, encoding="utf-8") as f:
                for line in f:
                    match = env_var_pattern.match(line)
                    if match:
                        env_vars.add(match.group(1))
        except Exception as e:
            print(f"Could not process file {filepath}: {e}")
output_filename = "env_vars.txt"
try:
    with builtins.open(output_filename, "w", encoding="utf-8") as f:
        f.writelines(var + "\n" for var in sorted(env_vars))
    print(f"Found {len(env_vars)} unique environment variable names. Saved to {output_filename}")
except Exception as e:
    print(f"Could not write to output file {output_filename}: {e}")
