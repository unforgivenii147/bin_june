#!/data/data/com.termux/files/usr/bin/env python


import datetime
from dh import georgian_to_hijri
from faprint import faprint


def get_current_ymd() -> tuple[int, int, int]:
    today = datetime.date.today()
    return today.year, today.month, today.day


y, m, d = get_current_ymd()
faprint(f"{georgian_to_hijri(y, m, d)}")
