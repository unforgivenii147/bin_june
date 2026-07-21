#!/data/data/com.termux/files/usr/bin/env python

"""Module for hejri.py."""
from dh import georgian_to_hijri
import datetime


def get_current_ymd():
    """
    Returns the current year, month, and day as a tuple of integers (year, month, day).
    """
    today = datetime.date.today()
    return (today.year, today.month, today.day)


# Example usage:
current_year, current_month, current_day = get_current_ymd()
print(georgian_to_hijri(current_year, current_month, current_day))
