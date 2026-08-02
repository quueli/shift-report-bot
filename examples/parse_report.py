from datetime import datetime
from pathlib import Path

from shiftbot.analytics.aggregate import Period, summarize, worker_totals
from shiftbot.parsing.parser import parse_text

SAMPLE = Path(__file__).with_name("sample_reports.txt")


def main():
    text = SAMPLE.read_text(encoding="utf-8")
    # pinned so the sample dates don't get flagged as months late
    reports = parse_text(text, posted_at=datetime(2026, 2, 16, 3, 0))

    print(f"parsed {len(reports)} reports\n")
    for r in reports:
        head = f"{r.report_date} {r.kind.value}"
        if r.operator:
            head += f" (operator {r.operator})"
        print(head)
        for w in r.workers:
            print(f"    {w.name:8} {w.started_at}-{w.ended_at}  {w.amount} over {w.hours}h")
        if r.opening and r.opening.worker:
            print(f"    {r.opening.worker} opened at {r.opening.opened_at}")
        for issue in r.issues:
            print(f"    ! {issue}")
        print()

    print("per-worker totals")
    for w in worker_totals(reports):
        eff = f"{w.efficiency:.0f}/h" if w.efficiency is not None else "n/a"
        print(f"    {w.name:8} {w.shifts} shifts  {w.amount}  ({eff})")

    print("\nby day")
    for key, day in summarize(reports, Period.DAY).items():
        print(f"    {key}: {day.amount} over {day.hours}h from {day.reports} report(s)")


if __name__ == "__main__":
    main()
