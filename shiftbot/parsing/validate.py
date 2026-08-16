from decimal import Decimal

from shiftbot.domain.models import Issue, IssueLevel, ReportKind, ShiftReport

# payroll above rate * (1 + this) is a typo rather than a top-up. modest
# overpayment happens all the time; restating the whole amount is the mistake
# worth shouting about
PAYROLL_ALARM_RATIO = Decimal("1.5")


def check_report(report: ShiftReport, payroll_rate: Decimal) -> list[Issue]:
    issues: list[Issue] = []
    if report.kind is not ReportKind.CLOSING:
        opening = report.opening
        if opening and opening.system_check and opening.system_check.success is False:
            issues.append(Issue(IssueLevel.INFO, f"System check failed: {opening.worker}"))
        return issues

    if not report.workers:
        issues.append(Issue(IssueLevel.ERROR, "Closing report has no worker blocks"))

    if report.total_stated is None:
        # INFO, not WARNING: the worker blocks already carry the money, and a
        # warning here would show up on half the reports
        issues.append(Issue(IssueLevel.INFO, 'No "Total" stated'))
    elif report.total_stated != report.workers_amount:
        issues.append(
            Issue(
                IssueLevel.WARNING,
                f"Stated total ({report.total_stated}) does not match the sum "
                f"of worker blocks ({report.workers_amount}); analytics uses the "
                f"worker-block sum",
            )
        )

    if report.workers_amount:
        expected = report.workers_amount * payroll_rate
        if report.payroll is None:
            issues.append(
                Issue(
                    IssueLevel.WARNING,
                    f"No payroll stated for an amount of {report.workers_amount} - "
                    f"expected roughly {expected.quantize(Decimal('1'))} ({payroll_rate:.0%})",
                )
            )
        elif abs(report.payroll - expected) > 1:
            gross = bool(expected) and report.payroll > expected * (1 + PAYROLL_ALARM_RATIO)
            issues.append(
                Issue(
                    IssueLevel.WARNING if gross else IssueLevel.INFO,
                    f"Payroll {report.payroll} differs from the expected "
                    f"{expected.quantize(Decimal('1'))} ({payroll_rate:.0%})"
                    + (" - looks like a typo, please check" if gross else ""),
                )
            )

    for shift in report.workers:
        if shift.hours is None and (shift.started_at or shift.ended_at):
            issues.append(
                Issue(IssueLevel.INFO, f'Shift duration could not be computed for "{shift.name}"')
            )
    return issues
