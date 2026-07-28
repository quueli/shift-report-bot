from datetime import datetime
from decimal import Decimal
from pathlib import Path

from shiftbot.analytics.aggregate import Period, operator_totals, summarize, worker_totals
from shiftbot.parsing.parser import parse_text

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_reports.txt"


def parsed():
    return parse_text(SAMPLE.read_text(encoding="utf-8"), posted_at=datetime(2026, 2, 16, 3, 0))


def test_worker_totals_sum_across_reports():
    totals = {w.name: w for w in worker_totals(parsed())}
    assert totals["Алиса"].shifts == 2
    assert totals["Алиса"].amount == Decimal("21500")
    assert totals["Борис"].amount == Decimal("19000")


def test_worker_totals_sorted_by_amount():
    rows = worker_totals(parsed())
    assert [w.name for w in rows] == ["Алиса", "Борис"]


def test_daily_summary_groups_by_report_date():
    days = summarize(parsed(), Period.DAY)
    assert set(days) == {"2026-02-14", "2026-02-15"}
    assert days["2026-02-14"].amount == Decimal("20000")
    assert days["2026-02-15"].amount == Decimal("20500")


def test_monthly_summary_merges_both_days():
    months = summarize(parsed(), Period.MONTH)
    assert set(months) == {"2026-02"}
    assert months["2026-02"].amount == Decimal("40500")


def test_opening_reports_do_not_count_toward_money():
    days = summarize(parsed(), Period.DAY)
    assert sum(d.reports for d in days.values()) == 2


def test_operator_totals():
    assert operator_totals(parsed()) == {"Виктор": Decimal("40500")}
