import logging
import re
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from shiftbot.domain.models import (
    CheckResult,
    ExtraEntry,
    Issue,
    IssueLevel,
    OpeningInfo,
    ReportKind,
    ShiftReport,
    WorkerShift,
)
from shiftbot.parsing.expressions import classify_extra, parse_expression
from shiftbot.parsing.labels import STOPWORDS, Field, lookup_exact, match_label
from shiftbot.parsing.numbers import DEFAULT_CURRENCY, detect_currency
from shiftbot.parsing.splitter import is_report_anchor, split_reports
from shiftbot.parsing.text_utils import clean, clean_name, fold, has_digit, has_letter, key
from shiftbot.parsing.times import parse_time

log = logging.getLogger(__name__)

_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[.\-/]+(\d{1,2})(?:[.\-/]+(\d{2,4}))?(?!\d)")
_KIND_RE = re.compile(r"(закрыт|открыт)")
_SHIFT_WORD_RE = re.compile(r"смен")
_MAX_HEADER_LINES = 5

DEFAULT_PAYROLL_RATE = Decimal("0.10")

_WORKER_FIELDS = (Field.SHIFT_START, Field.SHIFT_END, Field.AMOUNT)
_DIGIT_FIELDS = (Field.SHIFT_START, Field.SHIFT_END, Field.AMOUNT, Field.TOTAL, Field.PAYROLL)


class ReportParseError(ValueError):
    pass


def _value_fits(fld, text):
    return has_digit(text) if fld in _DIGIT_FIELDS else has_letter(text)


def is_name_line(line):
    text = clean_name(line)
    if not text or has_digit(text) or ":" in text or not has_letter(text):
        return False
    words = text.split()
    if not 1 <= len(words) <= 4 or any(len(w) > 24 for w in words):
        return False
    if not any(w[:1].isupper() for w in words):
        return False
    canonical = key(text)
    return canonical not in STOPWORDS and lookup_exact(canonical) is None


def _parse_check(value):
    folded = fold(value)
    if re.search(r"не\s*успешн|неуспешн|провал|ошибк|\bнет\b", folded):
        success = False
    elif "успешн" in folded or folded.strip() in {"да", "ок", "ok"}:
        success = True
    else:
        success = None
    return CheckResult(success=success, at=parse_time(value))


@dataclass(frozen=True)
class _Header:
    kind: ReportKind
    report_date: date | None
    body_start: int
    issues: tuple = ()


def _parse_header(lines, today):
    anchor = next((i for i, line in enumerate(lines[:6]) if is_report_anchor(line)), None)
    if anchor is None:
        raise ReportParseError('no "отчёт от" anchor found')

    buffer = []
    last = anchor
    for index in range(anchor, min(anchor + _MAX_HEADER_LINES, len(lines))):
        if index > anchor and not lines[index].strip():
            break
        buffer.append(lines[index])
        last = index
        joined = fold(" ".join(buffer))
        if _KIND_RE.search(joined) and _SHIFT_WORD_RE.search(joined):
            break

    header_text = " ".join(buffer)
    folded = fold(header_text)
    issues = []

    kind_match = _KIND_RE.search(folded)
    if kind_match:
        kind = ReportKind.CLOSING if kind_match.group(1) == "закрыт" else ReportKind.OPENING
    else:
        body = fold("\n".join(lines[last + 1 :]))
        kind = ReportKind.OPENING if "проверка связи" in body else ReportKind.CLOSING
        issues.append(Issue(IssueLevel.WARNING, "Report kind inferred from body text"))

    report_date = None
    date_match = _DATE_RE.search(header_text)
    if date_match:
        day, month, raw_year = date_match.groups()
        year = today.year
        if raw_year:
            year = int(raw_year)
            if year < 100:
                year += 2000
        try:
            report_date = date(year, int(month), int(day))
        except ValueError:
            issues.append(Issue(IssueLevel.ERROR, f"Invalid date: {date_match.group(0)}"))
    else:
        issues.append(Issue(IssueLevel.WARNING, "No date found in the header"))

    return _Header(kind, report_date, last + 1, tuple(issues))


@dataclass
class _Draft:
    name: str | None = None
    started_at: object = None
    ended_at: object = None
    amount: Decimal | None = None
    transactions: int = 0
    note: str | None = None
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


class ReportParser:
    def __init__(self, payroll_rate=DEFAULT_PAYROLL_RATE, default_currency=DEFAULT_CURRENCY):
        self.payroll_rate = payroll_rate
        self.default_currency = default_currency

    def parse(self, text, posted_at=None, operator=None, source=None):
        lines = text.splitlines()
        today = posted_at.date() if posted_at else date.today()
        header = _parse_header(lines, today)
        body = lines[header.body_start :]
        issues = list(header.issues)

        if header.kind is ReportKind.OPENING:
            opening, extras, text_operator, more = self._parse_opening(body)
            workers = ()
            total_stated = payroll = None
        else:
            workers, total_stated, payroll, extras, text_operator, more = self._parse_closing(body)
            opening = None
        issues.extend(more)

        report = ShiftReport(
            kind=header.kind,
            report_date=header.report_date or today,
            operator=text_operator or operator,
            workers=workers,
            opening=opening,
            total_stated=total_stated,
            payroll=payroll,
            extras=tuple(extras),
            currency=detect_currency(text) or self.default_currency,
            posted_at=posted_at,
            source=source,
            raw_text=text,
        )
        issues.extend(self._validate(report))
        return replace(report, issues=tuple(issues))

    def _parse_closing(self, body):
        drafts = []
        current = None
        pending = None
        total_stated = payroll = operator = None
        extras = []
        issues = []

        def flush():
            nonlocal current
            if current is not None and current.has_data():
                drafts.append(current)
            current = None

        def assign(fld, value):
            nonlocal current, total_stated, payroll, operator
            value = clean(value)
            if fld in _WORKER_FIELDS:
                if current is None:
                    current = _Draft()
                if fld is Field.SHIFT_START:
                    current.start_seen = True
                    current.started_at = parse_time(value)
                elif fld is Field.SHIFT_END:
                    current.end_seen = True
                    current.ended_at = parse_time(value)
                else:
                    current.amount_seen = True
                    expression = parse_expression(value)
                    current.amount = expression.amount
                    current.transactions = expression.transactions
                    current.note = expression.note
                return
            if fld is Field.TOTAL:
                total_stated = parse_expression(value).amount
            elif fld is Field.PAYROLL:
                payroll = parse_expression(value).amount
            elif fld is Field.OPERATOR:
                operator = clean_name(value) or None
            elif value:
                extras.append(ExtraEntry("note", None, f"{fld.value}: {value}"))

        for raw_line in body:
            line = clean(raw_line)
            if not line:
                continue
            label = match_label(line)
            if label is not None:
                fld, inline_value = label
                if pending is not None:
                    assign(pending, "")
                    pending = None
                if fld in _WORKER_FIELDS:
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

            if pending is not None and _value_fits(pending, line):
                assign(pending, line)
                pending = None
                continue

            if is_name_line(line):
                if current is not None and current.name is None:
                    current.name = clean_name(line)
                else:
                    flush()
                    current = _Draft(name=clean_name(line))
                continue

            extras.append(ExtraEntry(*classify_extra(line)))

        flush()
        workers = tuple(
            WorkerShift(
                name=d.name or "Unnamed",
                started_at=d.started_at,
                ended_at=d.ended_at,
                amount=d.amount if d.amount is not None else Decimal(0),
                transactions=d.transactions,
                note=d.note,
            )
            for d in drafts
        )
        return workers, total_stated, payroll, extras, operator, issues

    def _parse_opening(self, body):
        worker = operator = None
        system_check = verification_call = None
        extras = []
        issues = []

        for raw_line in body:
            line = clean(raw_line)
            if not line:
                continue
            label = match_label(line)
            if label is None:
                if worker is None and is_name_line(line):
                    worker = clean_name(line)
                else:
                    extras.append(ExtraEntry(*classify_extra(line)))
                continue
            fld, value = label
            if fld is Field.SYSTEM_CHECK:
                system_check = _parse_check(value)
            elif fld is Field.VERIFICATION_CALL:
                verification_call = _parse_check(value)
            elif fld is Field.OPERATOR:
                operator = clean_name(value) or None

        if worker is None:
            issues.append(Issue(IssueLevel.WARNING, "No worker name found in the opening report"))
        return OpeningInfo(worker, system_check, verification_call), extras, operator, issues

    def _validate(self, report):
        issues = []
        if report.kind is not ReportKind.CLOSING:
            return issues
        if not report.workers:
            issues.append(Issue(IssueLevel.ERROR, "Closing report has no worker blocks"))
        if report.total_stated is None:
            issues.append(Issue(IssueLevel.INFO, 'No "Total" stated'))
        elif report.total_stated != report.workers_amount:
            issues.append(Issue(IssueLevel.WARNING, "Stated total does not match the worker blocks"))
        if report.payroll is None and report.workers_amount:
            issues.append(Issue(IssueLevel.WARNING, "No payroll stated"))
        return issues


_DEFAULT_PARSER = ReportParser()


def parse_report(text, **kwargs):
    return _DEFAULT_PARSER.parse(text, **kwargs)


def parse_text(text, parser=None, posted_at=None, operator=None, strict=False):
    active = parser or _DEFAULT_PARSER
    reports = []
    for index, chunk in enumerate(split_reports(text)):
        try:
            reports.append(active.parse(chunk, posted_at=posted_at, operator=operator, source=f"chunk:{index}"))
        except ReportParseError:
            if strict:
                raise
            log.debug("Chunk %s is not a report", index)
    return reports
