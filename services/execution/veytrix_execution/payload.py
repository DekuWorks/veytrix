"""JSON body checks shared by the paper recorders."""

from __future__ import annotations

import json
import math
import re

from veytrix_execution.limits import MAX_BODY_BYTES, MAX_FORMULAS, MAX_NESTING, MAX_STRUCTURAL

_NUMBER = re.compile(r"(?:0|[1-9]\d*)(?:\.\d+)?$")
_STRUCTURAL = set("{}[]:,")


def media_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None
    return content_type.split(";", 1)[0].strip().lower()


def structural_count(text: str) -> int:
    count = 0
    in_string = False
    escape = False
    for character in text:
        if in_string:
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in _STRUCTURAL:
            count += 1
    return count


def depth(value: object, level: int = 0) -> int:
    if isinstance(value, dict):
        if not value:
            return level + 1
        return max(depth(item, level + 1) for item in value.values())
    if isinstance(value, list):
        if not value:
            return level + 1
        return max(depth(item, level + 1) for item in value)
    return level


def formula_count(value: object) -> int:
    if isinstance(value, str):
        return 1 if value.startswith("=") else 0
    if isinstance(value, dict):
        return sum(formula_count(item) for item in value.values())
    if isinstance(value, list):
        return sum(formula_count(item) for item in value)
    return 0


def non_negative(value: object) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return value >= 0
    if isinstance(value, float):
        return math.isfinite(value) and value >= 0
    if isinstance(value, str):
        return _NUMBER.fullmatch(value) is not None
    return False


def positive(value: object) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, float):
        return math.isfinite(value) and value > 0
    if isinstance(value, str) and _NUMBER.fullmatch(value):
        return float(value) > 0
    return False


def encode(value: object) -> bytes | None:
    try:
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        return None


def over_budget(encoded: bytes, parsed: object) -> str | None:
    if len(encoded) > MAX_BODY_BYTES:
        return "Body exceeds 16384 bytes."
    if structural_count(encoded.decode("utf-8")) > MAX_STRUCTURAL:
        return "Body exceeds the structural-character budget."
    if depth(parsed) > MAX_NESTING:
        return "Body exceeds the nesting budget."
    if formula_count(parsed) > MAX_FORMULAS:
        return "Body exceeds the formula budget. Formulas are not evaluated."
    return None
