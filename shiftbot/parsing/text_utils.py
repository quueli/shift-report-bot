import re

# what telegram and copy-paste send instead of a plain space, and the
# zero-width junk that rides along with emoji (4️⃣, ⚡️)
_SPACE_LIKE = "      ⁠᠎　  "
_INVISIBLE ="️︎​‌‍﻿⁦⁧⁨⁩؜"

_TRANSLATION = {ord(c): " " for c in _SPACE_LIKE}
_TRANSLATION.update({ord(c): None for c in _INVISIBLE})

# a run of punctuation people use as a divider between reports
_SEPARATOR_RE = re.compile(r"^\s*[_\-–—=*·•~]{3,}\s*$")

_MULTISPACE_RE = re.compile(r"[ \t]+")
_NON_KEY_RE = re.compile(r"[^0-9a-zа-я]+")
_DIGIT_RE = re.compile(r"\d")
_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)

_EMOJI_RE = re.compile(
    "["
    "\U0001f000-\U0001faff"
    "☀-➿"
    "⬀-⯿"
    "←-⇿"
    "⤀-⥿"
    "㊗㊙〽©®"
    "]"
)

_NAME_EDGE_CHARS = " \t.,;:!?·•*-–—_\"'«»()[]"


def clean(text: str) -> str:
    if not text:
        return ""
    return _MULTISPACE_RE.sub(" ", text.translate(_TRANSLATION)).strip()


def fold(text: str) -> str:
    return clean(text).lower().replace("ё", "е")


def key(text: str) -> str:
    # "З / П" -> "зп"
    return _NON_KEY_RE.sub("", fold(text))


def has_digit(text: str) -> bool:
    return bool(_DIGIT_RE.search(text))


def has_letter(text: str) -> bool:
    return bool(_LETTER_RE.search(text))


def is_separator_line(line: str) -> bool:
    return bool(_SEPARATOR_RE.match(line))


def strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub(" ", text)


def clean_name(text: str) -> str:
    return clean(strip_emoji(text)).strip(_NAME_EDGE_CHARS)


# a single letter in front of a name as a role tag: "М Мария", "Д Евгения"
_NAME_PREFIX_RE = re.compile(r"^[^\W\d_]\s+(?=\S)", re.UNICODE)


def person_name(raw: str | None) -> str | None:
    # same treatment for live messages and for the bulk import, otherwise
    # "М Мария" and "Мария" become two different people
    if not raw:
        return None
    name = clean_name(raw)
    if not name:
        return None
    return _NAME_PREFIX_RE.sub("", name, count=1) or name


def name_key(name: str) -> str:
    return key(name)
