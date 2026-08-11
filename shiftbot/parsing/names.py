import re

from shiftbot.parsing.labels import lookup_exact
from shiftbot.parsing.text_utils import clean_name, has_digit, has_letter, key

_MAX_NAME_WORDS = 4
_MAX_WORD_LEN = 24

# never a worker or an operator name
STOPWORDS = frozenset(
    {
        "успешно",
        "неуспешно",
        "провалено",
        "ошибка",
        "да",
        "нет",
        "ок",
        "ok",
        "итого",
        "всего",
        "отчет",
        "смена",
        "смены",
        "смену",
        "пропущенныйдень",
        "связь",
        "звонок",
    }
)


def is_name_line(line: str) -> bool:
    # "Алиса такси 400" starts with a name but is a spending line, that is what
    # the no-digits rule is for
    text = clean_name(line)
    if not text or has_digit(text) or ":" in text or not has_letter(text):
        return False
    words = text.split()
    if not 1 <= len(words) <= _MAX_NAME_WORDS:
        return False
    if any(len(word) > _MAX_WORD_LEN for word in words):
        return False
    if not re.match(r"[^\W\d_]", text, re.UNICODE):
        return False
    if not any(word[:1].isupper() for word in words):
        return False
    canonical = key(text)
    return canonical not in STOPWORDS and lookup_exact(canonical) is None
