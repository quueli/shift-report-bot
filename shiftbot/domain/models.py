from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any

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


@dataclass(frozen=True, slots=True)
class Issue:
    level: IssueLevel
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"level": self.level.value, "message": self.message}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Issue:
        return cls(IssueLevel(data["level"]), data["message"])

    def __str__(self) -> str:
        return f"[{self.level.value.upper()}] {self.message}"


@dataclass(frozen=True, slots=True)
class ExtraEntry:
    kind: str
    amount: Decimal | None
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "amount": str(self.amount) if self.amount is not None else None,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtraEntry:
        amount = data.get("amount")
        return cls(data["kind"], Decimal(amount) if amount is not None else None, data["text"])


@dataclass(frozen=True, slots=True)
class WorkerShift:
    name: str
    started_at: time | None = None
    ended_at: time | None = None
    amount: Decimal = ZERO
    transactions: int = 0
    note: str | None = None

    @property
    def key(self) -> str:
        return name_key(self.name)

    @property
    def hours(self) -> Decimal | None:
        return shift_hours(self.started_at, self.ended_at)

    @property
    def efficiency(self) -> Decimal | None:
        hours = self.hours
        if not hours:
            return None
        return self.amount / hours

    @property
    def avg_check(self) -> Decimal | None:
        if not self.transactions:
            return None
        return self.amount / self.transactions

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "amount": str(self.amount),
            "transactions": self.transactions,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkerShift:
        return cls(
            name=data["name"],
            started_at=_time_from(data.get("started_at")),
            ended_at=_time_from(data.get("ended_at")),
            amount=Decimal(data.get("amount", "0")),
            transactions=int(data.get("transactions", 0)),
            note=data.get("note"),
        )


@dataclass(frozen=True, slots=True)
class CheckResult:
    success: bool | None
    at: time | None

    def to_dict(self) -> dict[str, Any]:
        return {"success": self.success, "at": self.at.isoformat() if self.at else None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckResult:
        return cls(data.get("success"), _time_from(data.get("at")))


@dataclass(frozen=True, slots=True)
class OpeningInfo:
    worker: str | None
    system_check: CheckResult | None = None
    verification_call: CheckResult | None = None

    @property
    def key(self) -> str:
        return name_key(self.worker or "")

    @property
    def opened_at(self) -> time | None:
        stamps = [c.at for c in (self.system_check, self.verification_call) if c and c.at]
        return min(stamps) if stamps else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker": self.worker,
            "system_check": self.system_check.to_dict() if self.system_check else None,
            "verification_call": self.verification_call.to_dict() if self.verification_call else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpeningInfo:
        check = data.get("system_check")
        call = data.get("verification_call")
        return cls(
            worker=data.get("worker"),
            system_check=CheckResult.from_dict(check) if check else None,
            verification_call=CheckResult.from_dict(call) if call else None,
        )


@dataclass(frozen=True, slots=True)
class ShiftReport:
    kind: ReportKind
    # the shift's start date, analytics groups by it: a report posted at 02:40
    # belongs to the previous day
    report_date: date
    operator: str | None = None
    workers: tuple[WorkerShift, ...] = ()
    opening: OpeningInfo | None = None
    total_stated: Decimal | None = None
    payroll: Decimal | None = None
    extras: tuple[ExtraEntry, ...] = ()
    issues: tuple[Issue, ...] = ()
    currency: str = "RUB"
    posted_at: datetime | None = None
    source: str | None = None
    raw_text: str = ""

    @property
    def workers_amount(self) -> Decimal:
        return sum((w.amount for w in self.workers), ZERO)

    @property
    def total(self) -> Decimal:
        # the stated "Итого" is only a cross-check, the blocks are the truth
        return self.workers_amount

    @property
    def operator_key(self) -> str | None:
        return name_key(self.operator) if self.operator else None

    @property
    def has_total_mismatch(self) -> bool:
        return self.total_stated is not None and self.total_stated != self.workers_amount

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "report_date": self.report_date.isoformat(),
            "operator": self.operator,
            "workers": [w.to_dict() for w in self.workers],
            "opening": self.opening.to_dict() if self.opening else None,
            "total_stated": str(self.total_stated) if self.total_stated is not None else None,
            "payroll": str(self.payroll) if self.payroll is not None else None,
            "extras": [e.to_dict() for e in self.extras],
            "issues": [i.to_dict() for i in self.issues],
            "currency": self.currency,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, raw_text: str = "") -> ShiftReport:
        opening = data.get("opening")
        posted = data.get("posted_at")
        return cls(
            kind=ReportKind(data["kind"]),
            report_date=date.fromisoformat(data["report_date"]),
            operator=data.get("operator"),
            workers=tuple(WorkerShift.from_dict(w) for w in data.get("workers", ())),
            opening=OpeningInfo.from_dict(opening) if opening else None,
            total_stated=_decimal_from(data.get("total_stated")),
            payroll=_decimal_from(data.get("payroll")),
            extras=tuple(ExtraEntry.from_dict(e) for e in data.get("extras", ())),
            issues=tuple(Issue.from_dict(i) for i in data.get("issues", ())),
            currency=data.get("currency", "RUB"),
            posted_at=datetime.fromisoformat(posted) if posted else None,
            source=data.get("source"),
            raw_text=raw_text,
        )


def _time_from(value: str | None) -> time | None:
    return time.fromisoformat(value) if value else None


def _decimal_from(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None
