#!/data/data/com.termux/files/usr/bin/python

from dh import runcmd

cmd = ["cleancss", "-O2", "removeDuplicateRules:on", "*.css", "-o", "merged.css"]
runcmd(cmd, show_output=True)
