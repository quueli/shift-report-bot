import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from shiftbot.parsing.text_utils import clean, fold

_CURRENCIES = (
    ("RUB", re.compile(r"₽|\bруб(?:лей|ля|\.)?\b|\brub\b")),
    ("USD", re.compile(r"\$|\busd\b|\bдолл")),
    ("EUR", re.compile(r"€|\beur\b|\bевро\b")),
    ("KZT", re.compile(r"₸|\bkzt\b|\bтенге\b")),
)

DEFAULT_CURRENCY = "RUB"

_GROUP_SEP_RE = re.compile(r"(?<=\d)\s(?=\d{3}(?!\d))")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_SIGNED_TERM_RE = re.compile(r"([+\-]?)\s*(\d+(?:\.\d+)?)")
_PARENS_RE = re.compile(r"\(([^)]*)\)")


def detect_currency(text):
    lowered = fold(text)
    for code, pattern in _CURRENCIES:
        if pattern.search(lowered):
            return code
    return None


def _prepare(text):
    return _GROUP_SEP_RE.sub("", clean(text).lower())


def find_numbers(text):
    out = []
    for token in _NUMBER_RE.findall(_prepare(text)):
        try:
            out.append(Decimal(token.replace(",", ".")))
        except InvalidOperation:
            continue
    return out


def parse_amount(text):
    numbers = find_numbers(text)
    return numbers[0] if numbers else None


@dataclass(frozen=True)
class MoneyExpression:
    amount: Decimal | None
    terms: tuple = ()
    computed: Decimal | None = None
    stated: Decimal | None = None
    transactions: int = 0
    note: str | None = None
    currency: str | None = None
    mismatch: bool = False

    @property
    def is_empty(self):
        return self.amount is None


def parse_expression(text):
    raw = clean(text)
    if not raw:
        return MoneyExpression(amount=None)

    note = "; ".join(c.strip() for c in _PARENS_RE.findall(raw) if c.strip()) or None
    prepared = _prepare(_PARENS_RE.sub(" ", raw)).replace(",", ".")

    if "=" in prepared:
        lhs, _, rhs = prepared.rpartition("=")
    else:
        lhs, rhs = prepared, ""

    terms = []
    for sign, token in _SIGNED_TERM_RE.findall(lhs):
        try:
            value = Decimal(token)
        except InvalidOperation:
            continue
        terms.append(-value if sign == "-" else value)

    computed = sum(terms) if terms else None
    stated = parse_amount(rhs) if rhs.strip() else None
    if computed is None and stated is None:
        return MoneyExpression(amount=None, note=note)

    amount = computed if computed is not None else stated
    return MoneyExpression(
        amount=amount,
        terms=tuple(terms),
        computed=computed,
        stated=stated,
        transactions=sum(1 for t in terms if t > 0),
        note=note,
        currency=detect_currency(raw),
        mismatch=computed is not None and stated is not None and computed != stated,
    )


_EXTRA_KINDS = (
    ("taxi", ("такси", "поездк")),
    ("transfer", ("перевод",)),
    ("debt", ("долг", "остаток")),
    ("expense", ("расход", "покупк", "оплат")),
)


def classify_extra(text):
    lowered = fold(text)
    kind = "note"
    for candidate, markers in _EXTRA_KINDS:
        if any(marker in lowered for marker in markers):
            kind = candidate
            break
    return kind, parse_expression(text).amount, clean(text)
