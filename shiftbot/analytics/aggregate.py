from dataclasses import dataclass, field
from decimal import Decimal

from shiftbot.domain.models import ReportKind

ZERO = Decimal(0)


@dataclass
class WorkerTotals:
    name: str
    shifts: int = 0
    amount: Decimal = ZERO


@dataclass
class DaySummary:
    key: str
    reports: int = 0
    amount: Decimal = ZERO
    workers: dict = field(default_factory=dict)


def summarize(reports):
    out = {}
    for report in reports:
        if report.kind is not ReportKind.CLOSING:
            continue
        key = report.report_date.isoformat()
        day = out.get(key)
        if day is None:
            day = DaySummary(key=key)
            out[key] = day
        day.reports += 1
        day.amount += report.total
        for shift in report.workers:
            totals = day.workers.get(shift.key)
            if totals is None:
                totals = WorkerTotals(name=shift.name)
                day.workers[shift.key] = totals
            totals.shifts += 1
            totals.amount += shift.amount
    return dict(sorted(out.items()))
