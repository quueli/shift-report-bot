import re
from typing import Iterable

from shiftbot.domain.models import CheckResult, ExtraEntry, Issue, IssueLevel, OpeningInfo
from shiftbot.parsing.expressions import classify_extra
from shiftbot.parsing.labels import Field, match_label, value_fits
from shiftbot.parsing.names import is_name_line
from shiftbot.parsing.text_utils import clean, clean_name, fold
from shiftbot.parsing.times import parse_time

_NEGATIVE_RE = re.compile(r"не\s*успешн|неуспешн|провал|ошибк|\bнет\b|\bне\b")
_POSITIVE = {"да", "ок", "ok", "+"}


def parse_check(value: str) -> CheckResult:
    folded = fold(value)
    if _NEGATIVE_RE.search(folded):
        success = False
    elif "успешн" in folded or folded.strip() in _POSITIVE:
        success = True
    else:
        success = None
    return CheckResult(success=success, at=parse_time(value))


def parse_opening(
    body: Iterable[str],
) -> tuple[OpeningInfo, list[ExtraEntry], str | None, list[Issue]]:
    worker: str | None = None
    operator: str | None = None
    system_check: CheckResult | None = None
    verification_call: CheckResult | None = None
    extras: list[ExtraEntry] = []
    issues: list[Issue] = []
    pending: Field | None = None

    def assign(fld: Field, value: str) -> None:
        nonlocal system_check, verification_call, operator
        value = clean(value)
        if fld is Field.SYSTEM_CHECK:
            system_check = parse_check(value) if value else CheckResult(None, None)
        elif fld is Field.VERIFICATION_CALL:
            verification_call = parse_check(value) if value else CheckResult(None, None)
        elif fld is Field.OPERATOR:
            operator = clean_name(value) or None
        elif value:
            extras.append(ExtraEntry(*classify_extra(value)))

    for raw_line in body:
        line = clean(raw_line)
        if not line:
            continue

        label = match_label(line)
        if label is not None:
            fld, inline_value = label
            if pending is not None:
                assign(pending, "")
                pending = None
            if inline_value:
                assign(fld, inline_value)
            else:
                pending = fld
            continue

        if pending is not None:
            if value_fits(pending, line):
                assign(pending, line)
                pending = None
                continue
            assign(pending, "")
            pending = None

        if worker is None and is_name_line(line):
            worker = clean_name(line)
            continue

        extras.append(ExtraEntry(*classify_extra(line)))

    if pending is not None:
        assign(pending, "")
    if worker is None:
        issues.append(Issue(IssueLevel.WARNING, "No worker name found in the opening report"))

    return OpeningInfo(worker, system_check, verification_call), extras, operator, issues
