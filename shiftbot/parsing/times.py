import re
from datetime import time
from decimal import ROUND_HALF_UP, Decimal

from shiftbot.parsing.text_utils import clean

# "14:00", "2:00", "14.00", "14-00", "14 ч 00"
_TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*[:.\-hч]\s*([0-5]\d)(?!\d)")

_BARE_HOUR_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*(?:h|ч)?(?!\d)")

# 22 and not 24: a shift that wraps past midnight is always under 24h anyway,
# so a 24h cutoff never fires and "02:00 -> 01:00" quietly becomes 23 hours
MAX_SHIFT_HOURS = Decimal(22)

_MINUTES_IN_DAY = 24 * 60


def parse_time(text: str) -> time | None:
    if not text:
        return None
    prepared = clean(text)
    match = _TIME_RE.search(prepared)
    if match:
        return time(int(match.group(1)), int(match.group(2)))

    stripped = prepared.strip(" .,;чh")
    if stripped.isdigit():
        bare = _BARE_HOUR_RE.fullmatch(stripped)
        if bare:
            return time(int(bare.group(1)), 0)
    return None


def shift_minutes(start: time | None, end: time | None) -> int | None:
    if start is None or end is None:
        return None
    delta = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
    if delta == 0:
        return None  # same start and end means unknown, not a 24h shift
    if delta < 0:
        delta += _MINUTES_IN_DAY
    if delta > MAX_SHIFT_HOURS * 60:
        return None
    return delta


def shift_hours(start: time | None, end: time | None) -> Decimal | None:
    minutes = shift_minutes(start, end)
    if minutes is None:
        return None
    return (Decimal(minutes) / Decimal(60)).quantize(Decimal("0.0001"))


def average_time(values: list[time]) -> time | None:
    # no midnight wraparound here, it is only used for average start times
    if not values:
        return None
    total = sum(v.hour * 60 + v.minute for v in values)
    avg = int(Decimal(total / len(values)).quantize(Decimal("1"), ROUND_HALF_UP))
    return time(avg // 60 % 24, avg % 60)
