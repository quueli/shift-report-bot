import re

from shiftbot.parsing.text_utils import fold, is_separator_line

# the line a report opens with, on purpose not tied to an emoji or a kind
_ANCHOR_RE = re.compile(r"отчет\s*от\b")


def is_report_anchor(line: str) -> bool:
    return bool(_ANCHOR_RE.search(fold(line)))


def looks_like_report(text: str) -> bool:
    folded = fold(text)
    if _ANCHOR_RE.search(folded):
        return True
    return "смен" in folded and any(
        marker in folded for marker in ("общая сумма", "проверка связи", "финансовый отчет")
    )


def _split_by_anchor(lines: list[str]) -> list[list[str]]:
    anchors = [i for i, line in enumerate(lines) if is_report_anchor(line)]
    if len(anchors) <= 1:
        return [lines]
    bounds = anchors + [len(lines)]
    chunks = []
    if anchors[0] > 0:
        chunks.append(lines[: anchors[0]])  # preamble, dropped later as "not a report"
    chunks.extend(lines[a:b] for a, b in zip(bounds, bounds[1:]))
    return chunks


def split_reports(text: str) -> list[str]:
    lines = text.splitlines()
    separators = [i for i, line in enumerate(lines) if is_separator_line(line)]

    raw_chunks: list[list[str]] = []
    if separators:
        bounds = [-1, *separators, len(lines)]
        for start, end in zip(bounds, bounds[1:]):
            block = lines[start + 1 : end]
            if any(line.strip() for line in block):
                raw_chunks.extend(_split_by_anchor(block))
    else:
        raw_chunks = _split_by_anchor(lines)

    return [
        "\n".join(chunk).strip("\n")
        for chunk in raw_chunks
        if any(line.strip() for line in chunk)
    ]
