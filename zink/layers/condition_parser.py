# SPDX-License-Identifier: Apache-2.0
"""
zink/layers/condition_parser.py
--------------------------------
Converts a 'when:' string into a parsed condition tree at config load time.
Never runs at request time — parse once, evaluate many times.

Grammar:
    expr     := or_expr
    or_expr  := and_expr (OR and_expr)*
    and_expr := not_expr (AND not_expr)*
    not_expr := NOT atom | atom
    atom     := field operator value

    field    := word ('.' word)*          e.g. context.hour
    operator := == != < > <= >= matches not_matches contains not_contains in not_in
    value    := number | bool | quoted_string | list | bare_word

Output:
    Leaf:     {"type": "leaf", "field": "context.hour", "operator": "<", "value": 9}
    Compound: {"type": "compound", "logic": "OR", "conditions": [...]}
"""

from typing import Any
from pyparsing import (
    CaselessKeyword,
    Group,
    Literal,
    OpAssoc,
    ParserElement,
    QuotedString,
    Regex,
    Suppress,
    infixNotation,
    pyparsing_common,
    one_of,
)

ParserElement.enablePackrat()

# ── Keywords ───────────────────────────────────────────────────────────────────
AND = CaselessKeyword("AND")
OR  = CaselessKeyword("OR")
NOT = CaselessKeyword("NOT")

# ── Field ──────────────────────────────────────────────────────────────────────
FIELD = Regex(
    r"(?!(?:AND|OR|NOT|true|false)\b)[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*"
)

# ── Operators — longer tokens before shorter prefixes ─────────────────────────
OPERATOR = one_of(
    "not_matches not_contains not_in matches contains in == != <= >= < >",
    asKeyword=False,
)

# ── Values ─────────────────────────────────────────────────────────────────────
QUOTED   = QuotedString('"') | QuotedString("'")
NUMBER   = pyparsing_common.number()
BOOL     = (
    CaselessKeyword("true").copy().setParseAction(lambda: True) |
    CaselessKeyword("false").copy().setParseAction(lambda: False)
)
_LIST_ITEM = QUOTED | NUMBER | Regex(r"[^\],\s]+")
LIST = (
    Suppress(Literal("[")) +
    Group(_LIST_ITEM + (Suppress(Literal(",")) + _LIST_ITEM)[...]) +
    Suppress(Literal("]"))
)
BARE_WORD = Regex(r"[^\s\)\]]+")
VALUE = BOOL | NUMBER | QUOTED | LIST | BARE_WORD

# ── Atom ───────────────────────────────────────────────────────────────────────
ATOM = Group(FIELD("field") + OPERATOR("operator") + VALUE("value"))


def _atom_to_leaf(tokens):
    t        = tokens[0]
    field    = t[0]
    operator = t[1]
    value    = t[2]
    if hasattr(value, "as_list"):
        value = value.as_list()
    if isinstance(value, str):
        value = _coerce(value)
    return {"type": "leaf", "field": field, "operator": operator, "value": value}


ATOM.setParseAction(_atom_to_leaf)

# ── Expression tree — NOT > AND > OR ──────────────────────────────────────────
EXPR = infixNotation(
    ATOM,
    [
        (NOT, 1, OpAssoc.RIGHT),
        (AND, 2, OpAssoc.LEFT),
        (OR,  2, OpAssoc.LEFT),
    ],
)


# ── Tree builder ───────────────────────────────────────────────────────────────
def _build_tree(node) -> dict:
    if isinstance(node, dict):
        return node

    lst = node.as_list() if hasattr(node, "as_list") else list(node)

    if len(lst) == 1:
        item = lst[0]
        return item if isinstance(item, dict) else _build_tree(item)

    if str(lst[0]).upper() == "NOT":
        return {
            "type":       "compound",
            "logic":      "NOT",
            "conditions": [_build_tree(lst[1])],
        }

    logic      = str(lst[1]).upper()
    conditions = []
    i = 0
    while i < len(lst):
        conditions.append(_build_tree(lst[i]))
        i += 2

    return {"type": "compound", "logic": logic, "conditions": conditions}


# ── Public API ─────────────────────────────────────────────────────────────────
def parse_condition(when: "str | dict") -> dict:
    """
    Entry point. Called by config loader for every 'when' value.
    Accepts a string (parse through grammar) or dict (YAML compound form).
    """
    if isinstance(when, dict):
        return _parse_yaml_compound(when)
    if isinstance(when, str):
        return _parse_string(when.strip())
    raise TypeError(f"'when' must be str or dict, got {type(when).__name__}")


def _parse_string(when: str) -> dict:
    try:
        result = EXPR.parseString(when, parseAll=True)
        return _build_tree(result[0])
    except Exception as e:
        raise SyntaxError(
            f"Invalid 'when' expression: {when!r}\n"
            f"  Reason: {e}\n"
            f"  Example: \"context.hour < 9 OR context.hour > 18\""
        ) from e


def _parse_yaml_compound(node: dict) -> dict:
    logic = node.get("logic", "").upper()
    if logic not in ("AND", "OR", "NOT"):
        raise ValueError(f"YAML compound 'logic' must be AND/OR/NOT, got {logic!r}")
    raw = node.get("conditions", [])
    if not raw:
        raise ValueError("YAML compound node has no 'conditions'")
    return {
        "type":       "compound",
        "logic":      logic,
        "conditions": [parse_condition(c) for c in raw],
    }


def _coerce(value: str) -> Any:
    low = value.lower()
    if low == "true":  return True
    if low == "false": return False
    try: return int(value)
    except ValueError: pass
    try: return float(value)
    except ValueError: pass
    return value