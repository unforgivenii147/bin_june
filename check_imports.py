#!/data/data/com.termux/files/usr/bin/env python

from __future__ import annotations

import random
import string
import sys
import traceback
from importlib.machinery import SourceFileLoader

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})

if __name__ == "__main__":
    files = sys.argv[1:]
    has_failure = False
    for file in files:
        try:
            module_name = "".join(random.choice(string.ascii_letters) for _ in range(20))
            SourceFileLoader(module_name, file).load_module()
        except Exception:
            has_failure = True
            print(file)
            traceback.print_exc()
            print()
    sys.exit(1 if has_failure else 0)
