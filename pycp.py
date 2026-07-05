#!/data/data/com.termux/files/usr/bin/python


import shutil
import sys
from pathlib import Path

src = Path(sys.argv[1].strip())
dest = Path("/data/data/com.termux/files/usr")
shutil.copy2(str(src), dest)
print("done")
