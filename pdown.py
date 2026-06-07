#!/data/data/com.termux/files/usr/bin/python

import subprocess
import sys


def process_pkg(pk):
    return subprocess.run(["pip", "download", "--no-deps", pk], check=False)


def main():
    pkgname = sys.argv[1]
    process_pkg(pkgname)


if __name__ == "__main__":
    sys.exit(main())
