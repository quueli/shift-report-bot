import re
from decimal import Decimal, InvalidOperation

from shiftbot.parsing.text_utils import clean, fold

_CURRENCIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("RUB", re.compile(r"₽|\bруб(?:лей|ля|\.)?\b|\bр\.|\brub\b")),
    ("USD", re.compile(r"\$|\busd\b|\bдолл")),
    ("EUR", re.compile(r"€|\beur\b|\bевро\b")),
    ("KZT", re.compile(r"₸|\bkzt\b|\bтенге\b")),
    ("UAH", re.compile(r"₴|\buah\b|\bгрн\b")),
    ("BYN", re.compile(r"\bbyn\b|\bбел\.?\s?руб")),
)

_CURRENCY_NOISE_RE = re.compile(
    r"₽|₸|₴|€|\$|\bруб(?:лей|ля|\.)?\b|\brub\b|\busd\b|\beur\b|\bkzt\b|\buah\b|\bbyn\b",
)

DEFAULT_CURRENCY = "RUB"


def detect_currency(text: str) -> str | None:
    lowered = fold(text)
    for code, pattern in _CURRENCIES:
        if pattern.search(lowered):
            return code
    return None


# space or apostrophe as a thousands separator: "15 000", "1'000"
_GROUP_SEP_RE = re.compile("(?<=\\d)[   '’](?=\\d{3}(?!\\d))")

_NUMBER_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*")


def _normalize_groups(text: str) -> str:
    previous = None
    current = text
    # "1 000 000" needs two passes
    while previous != current:
        previous = current
        current = _GROUP_SEP_RE.sub("", current)
    return current


def to_decimal(token: str) -> Decimal | None:
    # whichever of . , comes last wins as the decimal point; a lone . before
    # exactly three digits ("1.000") is a thousands separator
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        head, _, tail = token.rpartition(",")
        if token.count(",") == 1 and 1 <= len(tail) <= 2:
            token = f"{head}.{tail}"
        else:
            token = token.replace(",", "")
    elif "." in token:
        parts = token.split(".")
        looks_grouped = len(parts) > 2 or (
            len(parts) == 2 and len(parts[1]) == 3 and 1 <= len(parts[0]) <= 3
        )
        if looks_grouped:
            token = "".join(parts)
    try:
        return Decimal(token)
    except InvalidOperation:
        return None


def strip_noise(text: str) -> str:
    return _normalize_groups(_CURRENCY_NOISE_RE.sub(" ", clean(text).lower()))


def find_numbers(text: str) -> list[Decimal]:
    prepared = strip_noise(text)
    result: list[Decimal] = []
    for token in _NUMBER_TOKEN_RE.findall(prepared):
        value = to_decimal(token)
        if value is not None:
            result.append(value)
    return result


def parse_amount(text: str) -> Decimal | None:
    numbers = find_numbers(text)
    return numbers[0] if numbers else None
