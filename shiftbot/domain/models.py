from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum

from shiftbot.parsing.text_utils import name_key
from shiftbot.parsing.times import shift_hours

ZERO = Decimal(0)


class ReportKind(str, Enum):
    OPENING = "opening"
    CLOSING = "closing"


class IssueLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Issue:
    level: IssueLevel
    message: str

    def __str__(self):
        return f"[{self.level.value.upper()}] {self.message}"


@dataclass(frozen=True)
class WorkerShift:
    name: str
    started_at: time | None = None
    ended_at: time | None = None
    amount: Decimal = ZERO

    @property
    def key(self):
        return name_key(self.name)

    @property
    def hours(self):
        return shift_hours(self.started_at, self.ended_at)


@dataclass(frozen=True)
class ShiftReport:
    kind: ReportKind
    report_date: date
    operator: str | None = None
    workers: tuple[WorkerShift, ...] = ()
    total_stated: Decimal | None = None
    payroll: Decimal | None = None
    issues: tuple[Issue, ...] = ()
    posted_at: datetime | None = None
    raw_text: str = ""

    @property
    def workers_amount(self):
        return sum((w.amount for w in self.workers), ZERO)

    @property
    def total(self):
        return self.workers_amount
