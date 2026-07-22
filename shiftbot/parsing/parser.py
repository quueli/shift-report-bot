import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from shiftbot.domain.models import Issue, IssueLevel, ReportKind, ShiftReport, WorkerShift
from shiftbot.parsing.labels import Field, match_label
from shiftbot.parsing.numbers import parse_expression
from shiftbot.parsing.splitter import looks_like_report, split_reports
from shiftbot.parsing.text_utils import clean, clean_name, fold, has_digit, has_letter
from shiftbot.parsing.times import parse_time

_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[.\-/]+(\d{1,2})(?:[.\-/]+(\d{2,4}))?(?!\d)")
_KIND_RE = re.compile(r"(закрыт|открыт)")

DEFAULT_PAYROLL_RATE = Decimal("0.10")


class ReportParseError(ValueError):
    pass


@dataclass
class _Draft:
    name: str | None = None
    started_at: object = None
    ended_at: object = None
    amount: Decimal | None = None
    start_seen: bool = False
    end_seen: bool = False
    amount_seen: bool = False

    def has_data(self):
        return self.start_seen or self.end_seen or self.amount_seen

    def field_seen(self, fld):
        if fld is Field.SHIFT_START:
            return self.start_seen
        if fld is Field.SHIFT_END:
            return self.end_seen
        return self.amount_seen


def is_name_line(line):
    text = clean_name(line)
    if not text or has_digit(text) or ":" in text or not has_letter(text):
        return False
    words = text.split()
    return 1 <= len(words) <= 4 and any(w[:1].isupper() for w in words)


def _parse_header(lines, today):
    header = fold(" ".join(lines[:3]))
    if "отчет" not in header:
        raise ReportParseError("not a report")

    kind_match = _KIND_RE.search(header)
    kind = ReportKind.OPENING if kind_match and kind_match.group(1) == "открыт" else ReportKind.CLOSING

    report_date = None
    date_match = _DATE_RE.search(header)
    if date_match:
        day, month, year = date_match.groups()
        report_date = date(int(year) if year else today.year, int(month), int(day))
    return kind, report_date


def parse_report(text, posted_at=None, operator=None):
    lines = text.splitlines()
    today = posted_at.date() if posted_at else date.today()
    kind, report_date = _parse_header(lines, today)

    drafts = []
    current = None
    total_stated = payroll = None
    issues = []

    def flush():
        nonlocal current
        if current is not None and current.has_data():
            drafts.append(current)
        current = None

    for raw in lines[2:]:
        line = clean(raw)
        if not line:
            continue
        label = match_label(line)
        if label is None:
            if is_name_line(line):
                flush()
                current = _Draft(name=clean_name(line))
            continue

        fld, value = label
        if fld in (Field.SHIFT_START, Field.SHIFT_END, Field.AMOUNT):
            if current is None:
                current = _Draft()
            elif current.field_seen(fld):
                flush()
                current = _Draft()
            if fld is Field.SHIFT_START:
                current.start_seen = True
                current.started_at = parse_time(value)
            elif fld is Field.SHIFT_END:
                current.end_seen = True
                current.ended_at = parse_time(value)
            else:
                current.amount_seen = True
                current.amount = parse_expression(value).amount
        elif fld is Field.TOTAL:
            total_stated = parse_expression(value).amount
        elif fld is Field.PAYROLL:
            payroll = parse_expression(value).amount
        elif fld is Field.OPERATOR:
            operator = clean_name(value) or operator

    flush()

    workers = tuple(
        WorkerShift(
            name=d.name or "Unnamed",
            started_at=d.started_at,
            ended_at=d.ended_at,
            amount=d.amount if d.amount is not None else Decimal(0),
        )
        for d in drafts
    )
    if kind is ReportKind.CLOSING and not workers:
        issues.append(Issue(IssueLevel.ERROR, "Closing report has no worker blocks"))
    if total_stated is not None and total_stated != sum((w.amount for w in workers), Decimal(0)):
        issues.append(Issue(IssueLevel.WARNING, "Stated total does not match the worker blocks"))

    return ShiftReport(
        kind=kind,
        report_date=report_date or today,
        operator=operator,
        workers=workers,
        total_stated=total_stated,
        payroll=payroll,
        issues=tuple(issues),
        posted_at=posted_at,
        raw_text=text,
    )


def parse_text(text, posted_at=None, operator=None):
    reports = []
    for chunk in split_reports(text):
        if not looks_like_report(chunk):
            continue
        try:
            reports.append(parse_report(chunk, posted_at=posted_at, operator=operator))
        except ReportParseError:
            continue
    return reports
