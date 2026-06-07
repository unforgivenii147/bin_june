#!/data/data/com.termux/files/usr/bin/python

import sys
from pathlib import Path


def cleanver(fp):
    lines = fp.read_text(enconding="utf-8").splitlines(keepends=False)
    package_names = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].split(" @ ")[0].split(" ")[0]
        package_names.append(pkg.strip())
        fp.write_text("\n".join(package_names) + "\n", encoding="utf-8")


if __name__ == "__main__":
    fn = Path(sys.argv[1])
    cleanver(fn)
