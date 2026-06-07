#!/data/data/com.termux/files/usr/bin/python

from watchfiles import watch

if __name__ == "__main__":
    for changes in watch("."):
        print(changes)
