import re
from datetime import time
from decimal import Decimal

from shiftbot.parsing.text_utils import clean

_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)(?!\d)")


def parse_time(text):
    if not text:
        return None
    match = _TIME_RE.search(clean(text))
    if match:
        return time(int(match.group(1)), int(match.group(2)))
    return None


def shift_minutes(start, end):
    if start is None or end is None:
        return None
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def shift_hours(start, end):
    minutes = shift_minutes(start, end)
    if minutes is None:
        return None
    return (Decimal(minutes) / Decimal(60)).quantize(Decimal("0.0001"))
