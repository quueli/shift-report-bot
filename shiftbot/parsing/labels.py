from enum import Enum

from shiftbot.parsing.text_utils import has_digit, key


class Field(str, Enum):
    SHIFT_START = "shift_start"
    SHIFT_END = "shift_end"
    AMOUNT = "amount"
    TOTAL = "total"
    PAYROLL = "payroll"
    OPERATOR = "operator"


ALIASES = {
    Field.SHIFT_START: ("началоработы", "началосмены"),
    Field.SHIFT_END: ("конецработы", "конецсмены", "закрытиесмены"),
    Field.AMOUNT: ("финансовыйотчет", "финотчет", "выручка"),
    Field.TOTAL: ("итого", "общаясумма"),
    Field.PAYROLL: ("зп", "зарплата"),
    Field.OPERATOR: ("оператор", "администратор"),
}

ALIAS_TO_FIELD = {alias: fld for fld, aliases in ALIASES.items() for alias in aliases}

_MAX_HEAD_LEN = 42


def lookup_exact(canonical_key):
    return ALIAS_TO_FIELD.get(canonical_key)


def match_label(line):
    if ":" not in line:
        return None
    head, _, tail = line.partition(":")
    if len(head) > _MAX_HEAD_LEN or has_digit(head):
        return None
    field = lookup_exact(key(head))
    if field is None:
        return None
    return field, tail.strip()
