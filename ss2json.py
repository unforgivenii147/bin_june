#!/data/data/com.termux/files/usr/bin/env python


import sys
from pathlib import Path

import pandas as pd

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


fn = Path(sys.argv[1])
df = pd.read_csv(str(fn))
df_sorted = df.sort_values(by="score", ascending=False)
outfile = fn.with_suffix(".json")
df_sorted.to_json(str(outfile))
