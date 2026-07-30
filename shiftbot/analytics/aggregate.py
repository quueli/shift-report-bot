from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Iterable

from shiftbot.domain.models import ReportKind, ShiftReport

ZERO = Decimal(0)


class Period(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


def period_key(day: date, period: Period) -> str:
    if period is Period.WEEK:
        year, week, _ = day.isocalendar()
        return f"{year}-W{week:02d}"
    if period is Period.MONTH:
        return f"{day.year}-{day.month:02d}"
    return day.isoformat()


@dataclass
class WorkerTotals:
    name: str
    shifts: int = 0
    amount: Decimal = ZERO
    hours: Decimal = ZERO

    @property
    def efficiency(self) -> Decimal | None:
        return self.amount / self.hours if self.hours else None

    @property
    def avg_shift(self) -> Decimal | None:
        return self.amount / self.shifts if self.shifts else None


@dataclass
class PeriodSummary:
    key: str
    reports: int = 0
    amount: Decimal = ZERO
    hours: Decimal = ZERO
    workers: dict[str, WorkerTotals] = field(default_factory=dict)

    @property
    def efficiency(self) -> Decimal | None:
        return self.amount / self.hours if self.hours else None

    def top_workers(self, limit: int = 5) -> list[WorkerTotals]:
        return sorted(self.workers.values(), key=lambda w: w.amount, reverse=True)[:limit]


def _fold_worker(bucket: dict[str, WorkerTotals], report: ShiftReport) -> None:
    for shift in report.workers:
        wt = bucket.get(shift.key)
        if wt is None:
            wt = WorkerTotals(name=shift.name)
            bucket[shift.key] = wt
        wt.shifts += 1
        wt.amount += shift.amount
        hours = shift.hours
        if hours:
            wt.hours += hours


def summarize(reports: Iterable[ShiftReport], period: Period = Period.DAY) -> dict[str, PeriodSummary]:
    # opening reports carry no money or hours, they are skipped everywhere here
    out: dict[str, PeriodSummary] = {}
    for report in reports:
        if report.kind is not ReportKind.CLOSING:
            continue
        pkey = period_key(report.report_date, period)
        summary = out.get(pkey)
        if summary is None:
            summary = PeriodSummary(key=pkey)
            out[pkey] = summary
        summary.reports += 1
        summary.amount += report.total
        for shift in report.workers:
            if shift.hours:
                summary.hours += shift.hours
        _fold_worker(summary.workers, report)
    return dict(sorted(out.items()))


def worker_totals(reports: Iterable[ShiftReport]) -> list[WorkerTotals]:
    bucket: dict[str, WorkerTotals] = {}
    for report in reports:
        if report.kind is ReportKind.CLOSING:
            _fold_worker(bucket, report)
    return sorted(bucket.values(), key=lambda w: w.amount, reverse=True)


def operator_totals(reports: Iterable[ShiftReport]) -> dict[str, Decimal]:
    out: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for report in reports:
        if report.kind is ReportKind.CLOSING and report.operator:
            out[report.operator] += report.total
    return dict(out)
