import logging
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

from shiftbot.domain.models import ReportKind, ShiftReport
from shiftbot.parsing.closing import parse_closing
from shiftbot.parsing.header import ReportParseError, parse_header
from shiftbot.parsing.numbers import DEFAULT_CURRENCY, detect_currency
from shiftbot.parsing.opening import parse_opening
from shiftbot.parsing.splitter import split_reports
from shiftbot.parsing.validate import check_report

log = logging.getLogger(__name__)

DEFAULT_PAYROLL_RATE = Decimal("0.10")


class ReportParser:
    def __init__(
        self,
        *,
        payroll_rate: Decimal = DEFAULT_PAYROLL_RATE,
        default_currency: str = DEFAULT_CURRENCY,
    ):
        self.payroll_rate = payroll_rate
        self.default_currency = default_currency

    def _currency(self, text: str, extras) -> str:
        # only the money fields decide the currency. a "$" on a free-form line
        # is someone else's money (a taxi, a transfer) and used to turn the
        # whole report into USD
        money_text = text
        for extra in extras:
            money_text = money_text.replace(extra.text, " ")
        return detect_currency(money_text) or self.default_currency

    def parse(
        self,
        text: str,
        *,
        posted_at: datetime | None = None,
        operator: str | None = None,
        source: str | None = None,
    ) -> ShiftReport:
        """Parse one report; raises ReportParseError if the text isn't one."""
        lines = text.splitlines()
        today = posted_at.date() if posted_at else date.today()
        header = parse_header(lines, today)
        body = lines[header.body_start :]

        issues = list(header.issues)

        if header.kind is ReportKind.OPENING:
            opening, extras, text_operator, more = parse_opening(body)
            workers = ()
            total_stated = payroll = None
        else:
            workers, total_stated, payroll, extras, text_operator, more = parse_closing(body)
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
            issues=(),
            currency=self._currency(text, extras),
            posted_at=posted_at,
            source=source,
            raw_text=text,
        )
        issues.extend(check_report(report, self.payroll_rate))
        return replace(report, issues=tuple(issues))


_DEFAULT_PARSER = ReportParser()


def parse_report(text: str, **kwargs) -> ShiftReport:
    return _DEFAULT_PARSER.parse(text, **kwargs)


def parse_text(
    text: str,
    *,
    parser: ReportParser | None = None,
    posted_at: datetime | None = None,
    operator: str | None = None,
    strict: bool = False,
) -> list[ShiftReport]:
    """Parse text holding any number of reports; chunks that aren't reports are skipped."""
    active = parser or _DEFAULT_PARSER
    reports: list[ShiftReport] = []
    for index, chunk in enumerate(split_reports(text)):
        try:
            reports.append(
                active.parse(chunk, posted_at=posted_at, operator=operator, source=f"chunk:{index}")
            )
        except ReportParseError:
            if strict:
                raise
            log.debug("Chunk %s is not a report", index)
    return reports
