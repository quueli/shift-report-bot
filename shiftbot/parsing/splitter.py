import re

from shiftbot.parsing.text_utils import fold

_SEPARATOR_RE = re.compile(r"^\s*[_\-–—=*]{3,}\s*$")


def is_separator_line(line):
    return bool(_SEPARATOR_RE.match(line))


def looks_like_report(text):
    return "отчет" in fold(text)


def split_reports(text):
    lines = text.splitlines()
    chunks = []
    current = []
    for line in lines:
        if is_separator_line(line):
            chunks.append(current)
            current = []
            continue
        current.append(line)
    chunks.append(current)
    return ["\n".join(c).strip("\n") for c in chunks if any(line.strip() for line in c)]
