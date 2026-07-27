#!/data/data/com.termux/files/home/.local/bin/python

from __future__ import annotations

from watchfiles import watch

if __name__ == "__main__":
    for changes in watch("."):
        print(changes)
