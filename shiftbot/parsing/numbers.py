import re
from decimal import Decimal, InvalidOperation

from shiftbot.parsing.text_utils import clean, fold

_CURRENCIES = (
    ("RUB", re.compile(r"₽|\bруб")),
    ("USD", re.compile(r"\$|\busd\b")),
    ("EUR", re.compile(r"€|\beur\b")),
)

DEFAULT_CURRENCY = "RUB"

_GROUP_SEP_RE = re.compile(r"(?<=\d)\s(?=\d{3}(?!\d))")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def detect_currency(text):
    lowered = fold(text)
    for code, pattern in _CURRENCIES:
        if pattern.search(lowered):
            return code
    return None


def find_numbers(text):
    prepared = _GROUP_SEP_RE.sub("", clean(text))
    out = []
    for token in _NUMBER_RE.findall(prepared):
        try:
            out.append(Decimal(token.replace(",", ".")))
        except InvalidOperation:
            continue
    return out


def parse_amount(text):
    numbers = find_numbers(text)
    return numbers[0] if numbers else None
