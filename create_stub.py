#!/data/data/com.termux/files/usr/bin/env python


import sys
from dh import STDLIB, mpf3, runcmd


def process_pkg(pkg) -> None:
    print(f"creating stubs for {pkg}")
    cmd = ["pyright", "--createstub", str(pkg)]
    _, _, _ = runcmd(cmd, show_output=True)


def main() -> None:
    std_pkgs = list(STDLIB)
    mpf3(process_pkg, std_pkgs)


if __name__ == "__main__":
    sys.exit(main())
