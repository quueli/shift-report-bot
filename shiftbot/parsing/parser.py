import re
from datetime import date
from decimal import Decimal

from shiftbot.domain.models import Issue, IssueLevel, ReportKind, ShiftReport, WorkerShift
from shiftbot.parsing.labels import Field, match_label
from shiftbot.parsing.numbers import parse_amount
from shiftbot.parsing.text_utils import clean, clean_name, fold, has_digit
from shiftbot.parsing.times import parse_time

_DATE_RE = re.compile(r"(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?")
_KIND_RE = re.compile(r"(закрыт|открыт)")


class ReportParseError(ValueError):
    pass


def _is_name(line):
    text = clean_name(line)
    if not text or has_digit(text) or ":" in text:
        return False
    return len(text.split()) <= 3 and text[:1].isupper()


def parse_report(text, posted_at=None):
    lines = text.splitlines()
    today = posted_at.date() if posted_at else date.today()
    header = fold(" ".join(lines[:2]))
    if "отчет" not in header:
        raise ReportParseError("not a report")

    kind_match = _KIND_RE.search(header)
    kind = ReportKind.CLOSING
    if kind_match and kind_match.group(1) == "открыт":
        kind = ReportKind.OPENING

    report_date = today
    date_match = _DATE_RE.search(header)
    if date_match:
        day, month, year = date_match.groups()
        report_date = date(int(year) if year else today.year, int(month), int(day))

    workers = []
    issues = []
    name = None
    started = ended = amount = None
    total_stated = payroll = None

    for raw in lines[2:]:
        line = clean(raw)
        if not line:
            continue
        label = match_label(line)
        if label is None:
            if _is_name(line):
                if name is not None:
                    workers.append(WorkerShift(name, started, ended, amount or Decimal(0)))
                    started = ended = amount = None
                name = clean_name(line)
            continue
        fld, value = label
        if fld is Field.SHIFT_START:
            started = parse_time(value)
        elif fld is Field.SHIFT_END:
            ended = parse_time(value)
        elif fld is Field.AMOUNT:
            amount = parse_amount(value)
        elif fld is Field.TOTAL:
            total_stated = parse_amount(value)
        elif fld is Field.PAYROLL:
            payroll = parse_amount(value)

    if name is not None:
        workers.append(WorkerShift(name, started, ended, amount or Decimal(0)))

    if kind is ReportKind.CLOSING and not workers:
        issues.append(Issue(IssueLevel.ERROR, "Closing report has no worker blocks"))

    return ShiftReport(
        kind=kind,
        report_date=report_date,
        workers=tuple(workers),
        total_stated=total_stated,
        payroll=payroll,
        issues=tuple(issues),
        posted_at=posted_at,
        raw_text=text,
    )
