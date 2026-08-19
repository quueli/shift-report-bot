from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from typing import Iterable

from shiftbot.domain.models import ExtraEntry, Issue, IssueLevel, WorkerShift
from shiftbot.parsing.expressions import classify_extra, parse_expression
from shiftbot.parsing.labels import Field, match_label, value_fits
from shiftbot.parsing.names import is_name_line
from shiftbot.parsing.text_utils import clean, clean_name, has_digit, has_letter
from shiftbot.parsing.times import parse_time

WORKER_FIELDS = (Field.SHIFT_START, Field.SHIFT_END, Field.AMOUNT)


@dataclass
class _Draft:
    name: str | None = None
    started_at: time | None = None
    ended_at: time | None = None
    amount: Decimal | None = None
    transactions: int = 0
    note: str | None = None
    amount_seen: bool = False
    start_seen: bool = False
    end_seen: bool = False

    def has_data(self) -> bool:
        return self.start_seen or self.end_seen or self.amount_seen

    def field_seen(self, fld: Field) -> bool:
        if fld is Field.SHIFT_START:
            return self.start_seen
        if fld is Field.SHIFT_END:
            return self.end_seen
        return self.amount_seen


def _join_wrapped_math(body: Iterable[str]) -> list[str]:
    # a long sum typed on a phone wraps: "6000+6000+12000" then "+4000=34 000".
    # glue the tail back on, but only when it is pure arithmetic and follows
    # immediately - "-100" after a blank line is a note, not part of the sum
    joined: list[str] = []
    previous_blank = True
    for raw in body:
        stripped = raw.strip()
        if not stripped:
            previous_blank = True
            joined.append(raw)
            continue
        previous = joined[-1].rstrip() if joined else ""
        is_tail = (
            not previous_blank
            and previous
            and not has_letter(stripped)
            and has_digit(stripped)
            and has_digit(previous)
            and (stripped[:1] in {"+", "-", "="} or previous[-1:] in {"+", "-", "="})
        )
        if is_tail:
            joined[-1] = f"{previous}{stripped}"
        else:
            joined.append(raw)
        previous_blank = False
    return joined


def parse_closing(
    body: Iterable[str],
) -> tuple[
    tuple[WorkerShift, ...],
    Decimal | None,
    Decimal | None,
    list[ExtraEntry],
    str | None,
    list[Issue],
]:
    drafts: list[_Draft] = []
    current: _Draft | None = None
    pending: Field | None = None

    total_stated: Decimal | None = None
    payroll: Decimal | None = None
    operator: str | None = None
    extras: list[ExtraEntry] = []
    issues: list[Issue] = []
    source_line = ""

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        if current.has_data():
            if current.name is None:
                issues.append(Issue(IssueLevel.WARNING, "Shift data with no worker name"))
            drafts.append(current)
        elif current.name:
            # a name with nothing under it is usually a stray remark
            extras.append(ExtraEntry("note", None, current.name))
        current = None

    def assign(fld: Field, value: str) -> None:
        nonlocal current, total_stated, payroll, operator
        value = clean(value)

        if fld in WORKER_FIELDS:
            if current is None:
                current = _Draft()
            if fld is Field.SHIFT_START:
                current.start_seen = True
                current.started_at = parse_time(value)
                if value and current.started_at is None:
                    issues.append(Issue(IssueLevel.INFO, f"Could not parse shift start: {value!r}"))
            elif fld is Field.SHIFT_END:
                current.end_seen = True
                current.ended_at = parse_time(value)
                if value and current.ended_at is None:
                    issues.append(Issue(IssueLevel.INFO, f"Could not parse shift end: {value!r}"))
            else:
                current.amount_seen = True
                expression = parse_expression(value)
                current.amount = expression.amount
                current.transactions = expression.transactions
                current.note = expression.note
                if expression.mismatch:
                    issues.append(
                        Issue(
                            IssueLevel.WARNING,
                            f"Sum of addends ({expression.computed}) doesn't match "
                            f"the stated total ({expression.stated}) in \"{value}\"",
                        )
                    )
            return

        if fld is Field.TOTAL:
            amount = parse_expression(value).amount
            if amount is None:
                return
            if total_stated is not None and total_stated != amount:
                issues.append(
                    Issue(IssueLevel.WARNING, f"Repeated \"Total\": {amount} (was {total_stated})")
                )
                return
            total_stated = amount
        elif fld is Field.PAYROLL:
            payroll = parse_expression(value).amount
        elif fld is Field.OPERATOR:
            operator = clean_name(value) or None
        elif fld is Field.TRANSFER:
            amount = parse_expression(value).amount
            extras.append(ExtraEntry("transfer", amount, source_line if value else "Office transfer"))
        elif value:
            extras.append(ExtraEntry("note", None, f"{fld.value}: {value}"))

    for raw_line in _join_wrapped_math(body):
        line = clean(raw_line)
        if not line:
            continue  # a blank line does not clear pending
        source_line = line

        label = match_label(line)
        if label is not None:
            fld, inline_value = label
            if pending is not None:
                assign(pending, "")
                pending = None
            if fld in WORKER_FIELDS:
                if current is None:
                    current = _Draft()
                elif current.field_seen(fld):
                    flush()
                    current = _Draft()
            if inline_value:
                assign(fld, inline_value)
            else:
                pending = fld
            continue

        if pending is not None:
            if value_fits(pending, line):
                assign(pending, line)
                pending = None
                continue
            assign(pending, "")
            pending = None

        if is_name_line(line):
            if current is not None and current.name is None:
                current.name = clean_name(line)
            else:
                flush()
                current = _Draft(name=clean_name(line))
            continue

        extras.append(ExtraEntry(*classify_extra(line)))

    if pending is not None:
        assign(pending, "")
    flush()

    workers = tuple(
        WorkerShift(
            name=draft.name or "Unnamed",
            started_at=draft.started_at,
            ended_at=draft.ended_at,
            amount=draft.amount if draft.amount is not None else Decimal(0),
            transactions=draft.transactions,
            note=draft.note,
        )
        for draft in drafts
    )
    return workers, total_stated, payroll, extras, operator, issues
