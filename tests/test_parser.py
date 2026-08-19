from datetime import datetime
from decimal import Decimal
from pathlib import Path

from shiftbot.domain.models import ReportKind
from shiftbot.parsing.parser import parse_report, parse_text

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_reports.txt"
REF = datetime(2026, 2, 16, 3, 0)


def parsed():
    return parse_text(SAMPLE.read_text(encoding="utf-8"), posted_at=REF)


def test_splits_into_three_reports():
    reports = parsed()
    assert len(reports) == 3
    assert [r.kind for r in reports] == [ReportKind.CLOSING, ReportKind.CLOSING, ReportKind.OPENING]


def test_worker_amounts_and_hours():
    first = parsed()[0]
    by_name = {w.name: w for w in first.workers}
    assert by_name["Алиса"].amount == Decimal("12000")
    assert by_name["Алиса"].hours == Decimal("8")
    assert by_name["Борис"].hours == Decimal("8.5")


def test_shift_past_midnight_counts_forward():
    second = parsed()[1]
    boris = {w.name: w for w in second.workers}["Борис"]
    assert boris.hours == Decimal("8.5")


def test_opening_report_has_worker_and_checks():
    opening = parsed()[2]
    assert opening.opening is not None
    assert opening.opening.worker == "Алиса"
    assert opening.opening.system_check.success is True


def test_line_order_does_not_matter():
    a = parse_report(
        "Отчёт от 14.02\nЗакрытие смены\n\nАлиса\nНачало работы: 14:00\n"
        "Конец работы: 22:00\nФинансовый отчёт: 12000\n",
        posted_at=REF,
    )
    b = parse_report(
        "Отчёт от 14.02\nЗакрытие смены\n\nАлиса\nФинансовый отчёт: 12000\n"
        "Конец работы: 22:00\nНачало работы: 14:00\n",
        posted_at=REF,
    )
    assert a.workers[0].amount == b.workers[0].amount
    assert a.workers[0].hours == b.workers[0].hours


def test_name_line_with_digits_is_not_a_worker():
    from shiftbot.parsing.names import is_name_line

    assert is_name_line("Алиса") is True
    assert is_name_line("Алиса такси 400") is False
