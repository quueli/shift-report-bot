import re

_SPACE_LIKE = "    "
_TRANSLATION = {ord(c): " " for c in _SPACE_LIKE}

_MULTISPACE_RE = re.compile(r"[ \t]+")
_NON_KEY_RE = re.compile(r"[^0-9a-zа-я]+")
_DIGIT_RE = re.compile(r"\d")
_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)


def clean(text):
    if not text:
        return ""
    return _MULTISPACE_RE.sub(" ", text.translate(_TRANSLATION)).strip()


def fold(text):
    return clean(text).lower().replace("ё", "е")


def key(text):
    return _NON_KEY_RE.sub("", fold(text))


def has_digit(text):
    return bool(_DIGIT_RE.search(text))


def has_letter(text):
    return bool(_LETTER_RE.search(text))


def clean_name(text):
    return clean(text).strip(" .,;:!?-_\"'()")


def name_key(name):
    return key(name)
