import difflib
from enum import Enum

from shiftbot.parsing.text_utils import has_digit, has_letter, key


class Field(str, Enum):
    SHIFT_START = "shift_start"
    SHIFT_END = "shift_end"
    AMOUNT = "amount"
    TOTAL = "total"
    PAYROLL = "payroll"
    SYSTEM_CHECK = "system_check"
    VERIFICATION_CALL = "verification_call"
    OPERATOR = "operator"
    TRANSFER = "transfer"
    COMMENT = "comment"


# synonyms, already run through text_utils.key()
ALIASES = {
    Field.SHIFT_START: (
        "началоработы",
        "началосмены",
        "началорабочегодня",
        "открытиесмены",
        "начало",
        "старт",
    ),
    Field.SHIFT_END: (
        "закрытиесмены",
        "окончаниесмены",
        "завершениесмены",
        "конецсмены",
        "конецработы",
        "конец",
        "финиш",
    ),
    Field.AMOUNT: (
        "финансовыйотчет",
        "финансовыйрезультат",
        "финотчет",
        "финансы",
        "выручка",
        "заработок",
    ),
    Field.TOTAL: (
        "общаясумма",
        "общийитог",
        "итогоприход",
        "итогозасмену",
        "итого",
        "всегозасмену",
    ),
    Field.PAYROLL: (
        "зп",
        "зпл",
        "зарплата",
        "заработнаяплата",
        "оплатаоператора",
    ),
    Field.SYSTEM_CHECK: (
        "проверкасвязи",
        "проверкасистемы",
        "связь",
    ),
    Field.VERIFICATION_CALL: (
        "контрольныйзвонок",
        "контрользвонка",
        "контрольныйобзвон",
    ),
    Field.OPERATOR: (
        "оператор",
        "администратор",
        "ответственный",
        "админ",
    ),
    Field.TRANSFER: (
        "переводвофис",
        "переводофису",
        "переводнакарту",
    ),
    Field.COMMENT: (
        "комментарий",
        "примечание",
        "заметка",
    ),
}

ALIAS_TO_FIELD: dict[str, Field] = {
    alias: fld for fld, aliases in ALIASES.items() for alias in aliases
}

_ALIASES_BY_LENGTH = tuple(sorted(ALIAS_TO_FIELD, key=len, reverse=True))

_MIN_PREFIX_LEN = 5
_FUZZY_CUTOFF = 0.82
_MAX_HEAD_LEN = 42

# fields whose value has to contain a digit; everything else wants a letter.
# keeps an empty label from swallowing the next worker's name
_NUMERIC_FIELDS = frozenset(
    {
        Field.SHIFT_START,
        Field.SHIFT_END,
        Field.AMOUNT,
        Field.TOTAL,
        Field.PAYROLL,
        Field.TRANSFER,
    }
)


def value_fits(fld: Field, text: str) -> bool:
    return has_digit(text) if fld in _NUMERIC_FIELDS else has_letter(text)


def lookup_exact(canonical_key: str) -> Field | None:
    return ALIAS_TO_FIELD.get(canonical_key)


def lookup(canonical_key: str, *, fuzzy: bool = True) -> Field | None:
    if not canonical_key:
        return None

    field = ALIAS_TO_FIELD.get(canonical_key)
    if field is not None:
        return field

    for alias in _ALIASES_BY_LENGTH:
        if len(alias) >= _MIN_PREFIX_LEN and canonical_key.startswith(alias):
            return ALIAS_TO_FIELD[alias]

    if fuzzy and len(canonical_key) >= 4:
        matches = difflib.get_close_matches(
            canonical_key, _ALIASES_BY_LENGTH, n=1, cutoff=_FUZZY_CUTOFF
        )
        if matches:
            return ALIAS_TO_FIELD[matches[0]]
    return None


def match_label(line: str) -> tuple[Field, str] | None:
    # "Успешно 13:00" is not a label - a real one never carries digits, the
    # colon there belongs to the time
    if ":" in line:
        head, _, tail = line.partition(":")
        if len(head) <= _MAX_HEAD_LEN and not has_digit(head):
            field = lookup(key(head))
            if field is not None:
                return field, tail.strip()

    # no colon ("Начало работы 14:00") - exact matches only here, or a name
    # starts being read as a label
    words = line.split()
    for count in range(1, min(4, len(words)) + 1):
        field = lookup_exact(key(" ".join(words[:count])))
        if field is not None:
            return field, " ".join(words[count:]).strip()
    return None
