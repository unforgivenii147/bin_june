#!/data/data/com.termux/files/usr/bin/python

import datetime

from dh import georgian_to_hijri
from print_persian import print_persian as pp


def get_current_ymd() -> tuple[int, int, int]:
    today = datetime.date.today()
    return (today.year, today.month, today.day)


y, m, d = get_current_ymd()
print(pp(f"{georgian_to_hijri(y, m, d)}"))
