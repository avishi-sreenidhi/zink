# SPDX-License-Identifier: Apache-2.0
"""
zink/layers/condition_evaluator.py
------------------------------------
Evaluates a parsed condition tree against a request dict.
Called on every request — must be fast, no parsing here.

Field resolution:
    "context.hour" → request["context"]["hour"]
    Raises EvaluationError if key missing (strict) or returns False (lenient).

Verdict logic:
    Walk policies in order.
    First block wins. Flags accumulate. Allow short-circuits.
    Returns a verdict dict: {verdict, rule, reason, flags}
"""

import fnmatch
from typing import Any


class EvaluationError(Exception):
    pass


# ── Field resolution ───────────────────────────────────────────────────────────
def _resolve_field(request: dict, field: str) -> Any:
    parts   = field.split(".")
    current = request
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            raise EvaluationError(
                f"Field '{field}' not found in request (missing key '{part}')"
            )
        current = current[part]
    return current


# ── Leaf evaluation ────────────────────────────────────────────────────────────
def _eval_leaf(condition: dict, request: dict) -> bool:
    field    = condition["field"]
    operator = condition["operator"]
    expected = condition["value"]
    actual   = _resolve_field(request, field)

    if operator == "==":           return actual == expected
    if operator == "!=":           return actual != expected
    if operator == "<":            return _num(actual, field) < _num(expected, field)
    if operator == ">":            return _num(actual, field) > _num(expected, field)
    if operator == "<=":           return _num(actual, field) <= _num(expected, field)
    if operator == ">=":           return _num(actual, field) >= _num(expected, field)
    if operator == "matches":      return fnmatch.fnmatch(str(actual), str(expected))
    if operator == "not_matches":  return not fnmatch.fnmatch(str(actual), str(expected))
    if operator == "contains":     return expected in actual
    if operator == "not_contains": return expected not in actual
    if operator == "in":
        if not isinstance(expected, list):
            raise EvaluationError(f"'in' requires a list value (field: '{field}')")
        return actual in expected
    if operator == "not_in":
        if not isinstance(expected, list):
            raise EvaluationError(f"'not_in' requires a list value (field: '{field}')")
        return actual not in expected

    raise EvaluationError(f"Unknown operator: {operator!r}")


def _num(value, field: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        raise EvaluationError(
            f"Cannot compare non-numeric value {value!r} (field: '{field}')"
        )


# ── Condition tree evaluation ──────────────────────────────────────────────────
def _eval_condition(condition: dict, request: dict) -> bool:
    ctype = condition.get("type")

    if ctype == "leaf":
        return _eval_leaf(condition, request)

    if ctype == "compound":
        logic      = condition["logic"]
        conditions = condition["conditions"]
        if logic == "AND":
            return all(_eval_condition(c, request) for c in conditions)
        if logic == "OR":
            return any(_eval_condition(c, request) for c in conditions)
        if logic == "NOT":
            return not _eval_condition(conditions[0], request)
        raise EvaluationError(f"Unknown compound logic: {logic!r}")

    raise EvaluationError(f"Unknown condition type: {ctype!r}")


# ── Denied list ────────────────────────────────────────────────────────────────
def check_denied(request: dict, denied: list) -> "dict | None":
    """
    Returns a BLOCKED verdict on first denied match, None if clean.
    denied is a list of DeniedEntry objects — uses .action and .resource.
    """
    action   = str(request.get("action",   ""))
    resource = str(request.get("resource", ""))
    for entry in denied:
        if (fnmatch.fnmatch(action, entry.action) and
                fnmatch.fnmatch(resource, entry.resource)):
            return {
                "verdict": "BLOCKED",
                "rule":    "denied",
                "reason":  f"Denied: {entry.action} {entry.resource}",
                "flags":   [],
            }
    return None


# ── Policy evaluation ──────────────────────────────────────────────────────────
def evaluate_policies(
    request:  dict,
    policies: tuple,
    strict:   bool = False,
) -> dict:
    """
    Walk parsed policy tuple. Returns verdict dict.
    policies is a tuple of dicts: {rule, when, then, reason}
    """
    flags = []

    for policy in policies:
        rule   = policy["rule"]
        then   = policy["then"]
        reason = policy["reason"]
        when   = policy["when"]

        try:
            condition_met = _eval_condition(when, request)
        except EvaluationError:
            if strict:
                raise
            condition_met = False   # lenient: missing field = not met

        if not condition_met:
            continue

        if then == "block":
            return {"verdict": "BLOCKED", "rule": rule, "reason": reason, "flags": flags}
        if then == "flag":
            flags.append({"rule": rule, "reason": reason})
        if then == "allow":
            return {"verdict": "PASS", "rule": rule, "reason": reason, "flags": flags}

    verdict = "FLAGGED" if flags else "PASS"
    return {"verdict": verdict, "rule": None, "reason": None, "flags": flags}