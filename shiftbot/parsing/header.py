import re
from dataclasses import dataclass
from datetime import date

from shiftbot.domain.models import Issue, IssueLevel, ReportKind
from shiftbot.parsing.splitter import is_report_anchor
from shiftbot.parsing.text_utils import fold

_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[.\-/]+(\d{1,2})(?:[.\-/]+(\d{2,4}))?(?!\d)")
_KIND_RE = re.compile(r"(закрыт|открыт)")
_SHIFT_WORD_RE = re.compile(r"смен")

# the header can wrap over a few lines ("отчёт о\nзакрытии смены")
_MAX_HEADER_LINES = 5

_CLOSING_EMOJI = "\U0001f534"
_OPENING_EMOJI = "\U0001f7e2"


class ReportParseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Header:
    kind: ReportKind
    report_date: date | None
    body_start: int
    issues: tuple[Issue, ...] = ()


def _resolve_year(raw_year: str | None, fallback: date) -> int:
    if not raw_year:
        return fallback.year
    year = int(raw_year)
    if year < 100:
        year += 2000
    return year


def parse_header(lines: list[str], today: date) -> Header:
    anchor = next((i for i, line in enumerate(lines[:6]) if is_report_anchor(line)), None)
    if anchor is None:
        raise ReportParseError('no "отчёт от" anchor found')

    buffer: list[str] = []
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
    issues: list[Issue] = []

    kind_match = _KIND_RE.search(folded)
    if kind_match:
        kind = ReportKind.CLOSING if kind_match.group(1) == "закрыт" else ReportKind.OPENING
    elif _CLOSING_EMOJI in header_text:
        kind = ReportKind.CLOSING
    elif _OPENING_EMOJI in header_text:
        kind = ReportKind.OPENING
    else:
        body = fold("\n".join(lines[last + 1 :]))
        kind = ReportKind.OPENING if "проверка связи" in body else ReportKind.CLOSING
        issues.append(Issue(IssueLevel.WARNING, "Report kind inferred from body text"))

    date_match = _DATE_RE.search(header_text)
    report_date: date | None = None
    if date_match:
        day, month, raw_year = date_match.groups()
        try:
            report_date = date(_resolve_year(raw_year, today), int(month), int(day))
        except ValueError:
            issues.append(Issue(IssueLevel.ERROR, f"Invalid date: {date_match.group(0)}"))
    else:
        issues.append(Issue(IssueLevel.WARNING, "No date found in the header"))

    return Header(kind=kind, report_date=report_date, body_start=last + 1, issues=tuple(issues))
