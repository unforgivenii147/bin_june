#!/data/data/com.termux/files/usr/bin/env python

from secrets import randbelow

SKIP_DIRS = frozenset({"lazy", ".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"})


def show_random_color() -> None:
    red = randbelow(256)
    green = randbelow(256)
    blue = randbelow(256)
    print(f"\x1b[48;2;{red};{green};{blue}m        \x1b[0m {red!s} {green!s} {blue!s}")


if __name__ == "__main__":
    for i in range(1, randbelow(1000)):
        show_random_color()
