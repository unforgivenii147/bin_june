#!/data/data/com.termux/files/usr/bin/env python


import sys

from googlesearch import search

if __name__ == "__main__":
    tts = sys.argv[1]
    for result in search(tts):
        print(result)
