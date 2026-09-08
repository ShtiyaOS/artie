"""
Scene Rig RULE-based slot validation.

docs/03_scene_rig.md §3  — RULE column (deterministic checks)
docs/03_scene_rig.md §4  — exit predicate: all 7 slots pass RULE; accept-first

All checks here are deterministic code. No model call.
JUDGMENT runs asynchronously after the writer enters the drafting surface —
it is never a gate before drafting (Task 27).

Determinism map (§3 table):
  Pure rule (no JUDGMENT):          N01
  Referentially gated (rule only):  N02, N04, N06
  Judgment-dominant (rule = non-empty only):  N03, N05, N07

validate_rig_slot(slot_id, value) -> RuleResult
  .ok    True  → rule passes; slot may be persisted; JUDGMENT may run async
  .ok    False → rule fails; the .error message is shown to the writer
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from src.scene_rig import POSITION_VALUES, OBSTACLE_LOCUS_VALUES, SLOT_LABELS

# ---------------------------------------------------------------------------
# Result type — mirrors greenlight_rules.RuleResult
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

def _validate_n01(value: Any) -> RuleResult:
    """
    N01 Narrative Position — value ∈ X01–X12.
    docs/03_scene_rig.md §3 (pure rule; no JUDGMENT)
    """
    if not isinstance(value, str) or value.strip() not in POSITION_VALUES:
        allowed = ", ".join(sorted(POSITION_VALUES))
        return _fail(f"N01 Narrative Position must be one of: {allowed}.")
    return _OK


def _validate_n02(value: Any) -> RuleResult:
    """
    N02 Alignment Character — resolves to existing or creates new; must be non-empty name.
    docs/03_scene_rig.md §3 (resolves or instantiates)
    """
    if not isinstance(value, str) or not value.strip():
        return _fail("N02 Alignment Character must be a non-empty name.")
    return _OK


def _validate_n03(value: Any) -> RuleResult:
    """
    N03 Active Want — non-empty text.
    docs/03_scene_rig.md §3
    """
    if not isinstance(value, str) or not value.strip():
        return _fail("N03 Active Want must be a non-empty string.")
    return _OK


def _validate_n04(value: Any) -> RuleResult:
    """
    N04 Obstacle — locus ∈ enum AND text non-empty.
    docs/03_scene_rig.md §3
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return _fail("N04 Obstacle must be a structured object with 'locus' and 'text'.")
    if not isinstance(value, dict):
        return _fail("N04 Obstacle must be a structured object with 'locus' and 'text'.")
    locus = value.get("locus", "")
    text  = value.get("text", "")
    if not isinstance(locus, str) or locus.strip() not in OBSTACLE_LOCUS_VALUES:
        allowed = ", ".join(sorted(OBSTACLE_LOCUS_VALUES))
        return _fail(f"N04 Obstacle.locus must be one of: {allowed}.")
    if not isinstance(text, str) or not text.strip():
        return _fail("N04 Obstacle.text must be a non-empty string.")
    return _OK


def _validate_n05(value: Any) -> RuleResult:
    """
    N05 Scene Frame — both fields non-empty.
    docs/03_scene_rig.md §3 (entry_state non-empty; value_at_stake non-empty)
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return _fail("N05 Scene Frame must have 'entry_state' and 'value_at_stake'.")
    if not isinstance(value, dict):
        return _fail("N05 Scene Frame must have 'entry_state' and 'value_at_stake'.")
    entry_state    = value.get("entry_state", "")
    value_at_stake = value.get("value_at_stake", "")
    if not isinstance(entry_state, str) or not entry_state.strip():
        return _fail("N05 Scene Frame entry_state must be a non-empty string.")
    if not isinstance(value_at_stake, str) or not value_at_stake.strip():
        return _fail("N05 Scene Frame value_at_stake must be a non-empty string.")
    return _OK


def _validate_n06(value: Any) -> RuleResult:
    """
    N06 Location — resolves to existing or creates new; must be non-empty name.
    docs/03_scene_rig.md §3 (resolves or instantiates)
    """
    if not isinstance(value, str) or not value.strip():
        return _fail("N06 Location must be a non-empty name.")
    return _OK


def _validate_n07(value: Any) -> RuleResult:
    """
    N07 Temporal Urgency — non-empty text.
    docs/03_scene_rig.md §3
    """
    if not isinstance(value, str) or not value.strip():
        return _fail("N07 Temporal Urgency must be a non-empty string.")
    return _OK


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_VALIDATORS: dict[str, Any] = {
    "N01": _validate_n01,
    "N02": _validate_n02,
    "N03": _validate_n03,
    "N04": _validate_n04,
    "N05": _validate_n05,
    "N06": _validate_n06,
    "N07": _validate_n07,
}


def validate_rig_slot(slot_id: str, value: Any) -> RuleResult:
    """
    Run the RULE check for a Scene Rig slot.

    docs/03_scene_rig.md §3 (RULE column)
    docs/03_scene_rig.md §4 (exit predicate — RULE checks only; accept-first)

    Unknown slots pass unconditionally (genre-addition slots from §5 are
    prompted but never gating).

    Returns RuleResult(ok=True)  when the rule passes or there is no rule.
    Returns RuleResult(ok=False, error=...) when the rule fails.
    No model call is ever made.
    """
    validator = _VALIDATORS.get(slot_id)
    if validator is None:
        return _OK
    return validator(value)
