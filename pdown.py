#!/data/data/com.termux/files/usr/bin/python

from subprocess import CompletedProcess
import subprocess
import sys


def process_pkg(pk: str) -> CompletedProcess[bytes]:
    return subprocess.run(["pip", "download", "--no-deps", pk], check=False)


def main() -> None:
    pkgname = sys.argv[1]
    process_pkg(pkgname)


if __name__ == "__main__":
    sys.exit(main())
