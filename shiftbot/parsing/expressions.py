import re
from dataclasses import dataclass
from decimal import Decimal

from shiftbot.parsing.numbers import detect_currency, parse_amount, strip_noise, to_decimal
from shiftbot.parsing.text_utils import clean, fold

_SIGNED_TERM_RE = re.compile(r"([+\-]?)\s*(\d+(?:\.\d+)?)")
_PARENS_RE = re.compile(r"\(([^)]*)\)")

# the expression is the longest run of digits and operators; whatever falls
# outside it is a comment. without that boundary "0+6900 for 07.01" computes
# 6901.07 - the date gets added in as another term
_EXPRESSION_RE = re.compile(r"[\d+\-=.,\s]*\d[\d+\-=.,\s]*")

# two numbers with only a space between them: group separators are stripped by
# now, so "10000 07.01" is an amount and a date, not 10007.01
_BARE_GAP_RE = re.compile(r"(?<=\d)\s+(?=[\d.,])")


@dataclass(frozen=True, slots=True)
class MoneyExpression:
    amount: Decimal | None
    terms: tuple[Decimal, ...] = ()
    computed: Decimal | None = None
    stated: Decimal | None = None
    transactions: int = 0
    note: str | None = None
    currency: str | None = None
    mismatch: bool = False

    @property
    def is_empty(self) -> bool:
        return self.amount is None


def parse_expression(text: str, *, prefer_stated: bool = False) -> MoneyExpression:
    # prefer_stated trusts the number after "="; by default the addends win,
    # a hand-typed total is the thing people get wrong
    raw = clean(text)
    if not raw:
        return MoneyExpression(amount=None)

    currency = detect_currency(raw)

    note_chunks = [c.strip() for c in _PARENS_RE.findall(raw) if c.strip()]
    without_parens = _PARENS_RE.sub(" ", raw)

    prepared = strip_noise(without_parens).replace(",", ".")

    span = _EXPRESSION_RE.search(prepared)
    if span is None:
        return MoneyExpression(amount=None, note=_join_note(note_chunks), currency=currency)

    expression = span.group(0)
    gap = _BARE_GAP_RE.search(expression)
    if gap:
        expression, tail = expression[: gap.start()], expression[gap.start() :]
        if tail.strip():
            note_chunks.append(tail.strip())
    for residual in (prepared[: span.start()], prepared[span.end() :]):
        if residual.strip():
            note_chunks.append(residual.strip())

    if "=" in expression:
        lhs, _, rhs = expression.rpartition("=")
    else:
        lhs, rhs = expression, ""

    terms: list[Decimal] = []
    for sign, token in _SIGNED_TERM_RE.findall(lhs):
        value = to_decimal(token)
        if value is None:
            continue
        terms.append(-value if sign == "-" else value)

    computed = sum(terms) if terms else None
    stated = parse_amount(rhs) if rhs.strip() else None

    if computed is None and stated is None:
        return MoneyExpression(amount=None, note=_join_note(note_chunks), currency=currency)

    mismatch = computed is not None and stated is not None and computed != stated
    if stated is not None and (prefer_stated or computed is None):
        amount = stated
    else:
        amount = computed if computed is not None else stated

    return MoneyExpression(
        amount=amount,
        terms=tuple(terms),
        computed=computed,
        stated=stated,
        transactions=sum(1 for t in terms if t > 0),
        note=_join_note(note_chunks),
        currency=currency,
        mismatch=mismatch,
    )


def _join_note(chunks: list[str]) -> str | None:
    return "; ".join(dict.fromkeys(chunks)) or None


# order matters, "неоплаченная поездка" must land in taxi and not in expense
# through "оплат"
_EXTRA_KINDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("taxi", ("такси", "поездк")),
    ("transfer", ("перевод",)),
    ("debt", ("долг", "остаток")),
    ("fine", ("штраф", "удержан")),
    ("bonus", ("бонус", "преми")),
    ("expense", ("расход", "покупк", "оплат", "закуп")),
)

def classify_extra(text: str) -> tuple[str, Decimal | None, str]:
    lowered = fold(text)
    kind = "note"
    for candidate, markers in _EXTRA_KINDS:
        if any(marker in lowered for marker in markers):
            kind = candidate
            break
    expression = parse_expression(text)
    return kind, expression.amount, clean(text)
