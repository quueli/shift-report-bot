from datetime import datetime
from decimal import Decimal
from pathlib import Path

from shiftbot.domain.models import ReportKind
from shiftbot.parsing.parser import parse_report

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "sample_reports.txt"
REF = datetime(2026, 2, 16, 3, 0)


def test_closing_report_kind():
    report = parse_report(SAMPLE.read_text(encoding="utf-8"), posted_at=REF)
    assert report.kind is ReportKind.CLOSING


def test_worker_amounts():
    report = parse_report(SAMPLE.read_text(encoding="utf-8"), posted_at=REF)
    by_name = {w.name: w for w in report.workers}
    assert by_name["Алиса"].amount == Decimal("12000")


def test_hours():
    report = parse_report(SAMPLE.read_text(encoding="utf-8"), posted_at=REF)
    by_name = {w.name: w for w in report.workers}
    assert by_name["Алиса"].hours == Decimal("8")
