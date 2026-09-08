"""
Greenlight RULE-based slot validation.

docs/02_greenlight.md §3  — new slots S13, S14, S15
docs/02_greenlight.md §8  — determinism map (pure-rule vs. structured/judged)
docs/03_scene_rig.md  §5  — genre enum (class → genre list)

All checks here are deterministic code. No model call.

Determinism map (§8):
  Pure rule (no JUDGMENT):          S09, S13, S15
  Structurally gated (rule only):   S05, S06, S07, S10, S11, S14

validate_slot(slot_id, value) -> RuleResult
  .ok    True  → rule passes; persist and let JUDGMENT run (if any)
  .ok    False → rule fails; the .error message is shown to the writer
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# S09 Genre — enum membership
# docs/03_scene_rig.md §5 (genre class table)
# ---------------------------------------------------------------------------

GENRE_VALUES: frozenset[str] = frozenset({
    # Baseline
    "Drama", "Historical", "War", "Western",
    # Speculative
    "SF", "Fantasy", "Supernatural Horror",
    # Information-state
    "Mystery", "Thriller", "Crime",
    # Comedic
    "Comedy", "Comedy-Drama",
    # Relational
    "Romance", "Romantic Comedy",
    # Kinetic
    "Action", "Adventure",
})

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuleResult:
    ok: bool
    error: str = ""   # non-empty only when ok is False


_OK = RuleResult(ok=True)


def _fail(msg: str) -> RuleResult:
    return RuleResult(ok=False, error=msg)


# ---------------------------------------------------------------------------
# Individual slot validators
# ---------------------------------------------------------------------------

def _validate_s09(value: Any) -> RuleResult:
    """
    S09 Genre — enum membership.
    docs/02_greenlight.md §8 (pure rule)
    docs/03_scene_rig.md §5
    """
    if not isinstance(value, str) or not value.strip():
        return _fail("S09 Genre must be a non-empty string.")
    if value.strip() not in GENRE_VALUES:
        allowed = ", ".join(sorted(GENRE_VALUES))
        return _fail(
            f"S09 Genre '{value}' is not a recognised genre. "
            f"Allowed values: {allowed}."
        )
    return _OK


def _validate_s13(value: Any) -> RuleResult:
    """
    S13 Working Title — non-empty; ≤ 15 words.
    docs/02_greenlight.md §3
    """
    if not isinstance(value, str) or not value.strip():
        return _fail("S13 Working Title must be a non-empty string.")
    word_count = len(value.strip().split())
    if word_count > 15:
        return _fail(
            f"S13 Working Title is {word_count} words; the maximum is 15."
        )
    return _OK


def _validate_s14(value: Any) -> RuleResult:
    """
    S14 Principal Characters — list; 1–8 entries; every entry has all three
    fields (name, role, description) non-empty; role in allowed enum.
    docs/02_greenlight.md §3
    """
    ROLE_VALUES = frozenset({"PROTAGONIST", "ANTAGONIST", "PRINCIPAL"})

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return _fail("S14 Principal Characters must be a list.")

    if not isinstance(value, list):
        return _fail("S14 Principal Characters must be a list.")
    if len(value) < 1:
        return _fail("S14 Principal Characters must have at least 1 entry.")
    if len(value) > 8:
        return _fail(
            f"S14 Principal Characters has {len(value)} entries; the maximum is 8."
        )

    for i, entry in enumerate(value):
        if not isinstance(entry, dict):
            return _fail(f"S14 entry [{i}] must be an object.")
        for field in ("name", "role", "description"):
            v = entry.get(field, "")
            if not isinstance(v, str) or not v.strip():
                return _fail(
                    f"S14 entry [{i}] field '{field}' must be a non-empty string."
                )
        role = entry.get("role", "").strip()
        if role not in ROLE_VALUES:
            return _fail(
                f"S14 entry [{i}] role '{role}' is not valid. "
                f"Allowed: PROTAGONIST, ANTAGONIST, PRINCIPAL."
            )

    return _OK


def _validate_s15(value: Any) -> RuleResult:
    """
    S15 Target Scene Count — integer, 20 ≤ n ≤ 200.
    docs/02_greenlight.md §3
    """
    # Accept int or a string that parses to int
    if isinstance(value, float) and value == int(value):
        value = int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if re.fullmatch(r"-?\d+", stripped):
            value = int(stripped)
        else:
            return _fail("S15 Target Scene Count must be an integer.")
    if not isinstance(value, int) or isinstance(value, bool):
        return _fail("S15 Target Scene Count must be an integer.")
    if value < 20:
        return _fail(
            f"S15 Target Scene Count is {value}; the minimum is 20."
        )
    if value > 200:
        return _fail(
            f"S15 Target Scene Count is {value}; the maximum is 200."
        )
    return _OK


# ---------------------------------------------------------------------------
# Structured-slot rule gates (rule only, JUDGMENT follows separately)
# These return _OK when the value is structurally acceptable for persistence.
# ---------------------------------------------------------------------------

def _validate_s05(value: Any) -> RuleResult:
    """
    S05 Antagonism — must be a dict with a non-empty 'locus' field.
    docs/02_greenlight.md §2 (structured form unchanged from v1.1 §3)
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return _fail("S05 Antagonism must be a structured object.")
    if not isinstance(value, dict):
        return _fail("S05 Antagonism must be a structured object.")
    locus = value.get("locus", "")
    if not isinstance(locus, str) or not locus.strip():
        return _fail("S05 Antagonism requires a non-empty 'locus' field.")
    return _OK


def _validate_s06(value: Any) -> RuleResult:
    """
    S06 Thematic Proposition — non-empty string (structured form v1.1 §3).
    """
    if not isinstance(value, str) or not value.strip():
        return _fail("S06 Thematic Proposition must be a non-empty string.")
    return _OK


def _validate_s07(value: Any) -> RuleResult:
    """
    S07 Status Quo Baseline — non-empty string or non-empty dict.
    """
    if isinstance(value, dict):
        if not any(v for v in value.values() if v):
            return _fail("S07 Status Quo Baseline must not be empty.")
        return _OK
    if not isinstance(value, str) or not value.strip():
        return _fail("S07 Status Quo Baseline must be a non-empty string.")
    return _OK


def _validate_s10(value: Any) -> RuleResult:
    """
    S10 Ending Shape Hypothesis — non-empty string or non-empty dict.
    """
    if isinstance(value, dict):
        if not any(v for v in value.values() if v):
            return _fail("S10 Ending Shape Hypothesis must not be empty.")
        return _OK
    if not isinstance(value, str) or not value.strip():
        return _fail("S10 Ending Shape Hypothesis must be a non-empty string.")
    return _OK


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_VALIDATORS: dict[str, Any] = {
    "S05": _validate_s05,
    "S06": _validate_s06,
    "S07": _validate_s07,
    "S09": _validate_s09,
    "S10": _validate_s10,
    "S13": _validate_s13,
    "S14": _validate_s14,
    "S15": _validate_s15,
}


def validate_slot(slot_id: str, value: Any) -> RuleResult:
    """
    Run the RULE check for slot_id against value.

    Slots with no rule entry pass unconditionally (JUDGMENT-dominant slots
    such as S02, S03, S04, S08 have no deterministic rule gate).

    Returns RuleResult(ok=True) when the rule passes or there is no rule.
    Returns RuleResult(ok=False, error=...) when the rule fails.
    No model call is ever made.
    """
    validator = _VALIDATORS.get(slot_id)
    if validator is None:
        return _OK
    return validator(value)
