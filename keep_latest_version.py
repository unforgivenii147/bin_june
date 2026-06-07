#!/data/data/com.termux/files/usr/bin/python

import operator
import re
from pathlib import Path

from dh import get_files
from packaging.version import Version


def cdeb(fp):
    name = fp.stem
    if "_" in name:
        indx = name.index("_")
        return name[:indx]
    return name


if __name__ == "__main__":
    cwd = Path.cwd()
    wheel_pattern = re.compile(r"(?P<name>.+)-(?P<version>\d+(\.\d+)+).*\.(whl|deb|metadata|tar.gz|zip|tar.xz)")
    files = get_files(cwd, ext=[".metadata", ".whl", ".deb",".zip",".tar.gz",".tar.xz"])
    print(f"{len(files)} files found.")
    packages = {}
    seen = set()
    pkgs = []
    for f in files:
        match1 = wheel_pattern.match(f.name)

        if match1:
            name = match1.group("name")
            version = Version(match1.group("version"))
        if name not in packages:
            packages[name] = []
            packages[name].append((version, f))
    for name, versions in packages.items():
        versions.sort(reverse=True, key=operator.itemgetter(0))
        latest = versions[0]
        old = versions[1:]
        for _v, filename in old:
            print(f"remove {filename}",end=" ")
            ans=input("(y/n)?")
            if ans=="y":
                Path(filename).unlink()
