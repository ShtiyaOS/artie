"""
Tests for Scene Rig RULE-based slot validation.

docs/03_scene_rig.md §3  — RULE column (deterministic checks per slot)
docs/03_scene_rig.md §4  — exit predicate: RULE checks only; accept-first
                            No model call may block the writer.

Task 26 acceptance criterion:
    The writer can proceed to the editor as soon as all 7 Scene Rig slots
    pass their RULE checks, without waiting for JUDGMENT validation.

All checks are deterministic (no mocks needed, no network).

Run with: python -m pytest tests/test_scene_rig_rules.py -v
"""

import json
import pytest

from src.scene_rig_rules import RuleResult, validate_rig_slot
from src.scene_rig import POSITION_VALUES, OBSTACLE_LOCUS_VALUES


# ---------------------------------------------------------------------------
# RuleResult type
# ---------------------------------------------------------------------------

class TestRuleResult:
    def test_ok_result_has_empty_error(self):
        r = RuleResult(ok=True)
        assert r.error == ""

    def test_fail_result_has_error(self):
        r = RuleResult(ok=False, error="something failed")
        assert not r.ok
        assert r.error == "something failed"

    def test_immutable(self):
        r = RuleResult(ok=True)
        with pytest.raises((AttributeError, TypeError)):
            r.ok = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# N01 — Narrative Position (pure rule; no JUDGMENT)
# docs/03_scene_rig.md §3
# ---------------------------------------------------------------------------

class TestN01:
    def test_valid_x01_passes(self):
        r = validate_rig_slot("N01", "X01")
        assert r.ok

    def test_valid_x12_passes(self):
        r = validate_rig_slot("N01", "X12")
        assert r.ok

    def test_all_twelve_positions_pass(self):
        for pos in POSITION_VALUES:
            r = validate_rig_slot("N01", pos)
            assert r.ok, f"{pos} should pass: {r.error}"

    def test_x13_fails(self):
        r = validate_rig_slot("N01", "X13")
        assert not r.ok

    def test_x00_fails(self):
        r = validate_rig_slot("N01", "X00")
        assert not r.ok

    def test_lowercase_x01_fails(self):
        r = validate_rig_slot("N01", "x01")
        assert not r.ok

    def test_empty_string_fails(self):
        r = validate_rig_slot("N01", "")
        assert not r.ok

    def test_none_fails(self):
        r = validate_rig_slot("N01", None)
        assert not r.ok

    def test_integer_fails(self):
        r = validate_rig_slot("N01", 1)
        assert not r.ok

    def test_error_lists_x01(self):
        r = validate_rig_slot("N01", "BAD")
        assert "X01" in r.error

    def test_error_lists_x12(self):
        r = validate_rig_slot("N01", "BAD")
        assert "X12" in r.error


# ---------------------------------------------------------------------------
# N02 — Alignment Character (resolves or instantiates; non-empty name)
# docs/03_scene_rig.md §3
# ---------------------------------------------------------------------------

class TestN02:
    def test_non_empty_name_passes(self):
        r = validate_rig_slot("N02", "Alice")
        assert r.ok

    def test_name_with_spaces_passes(self):
        r = validate_rig_slot("N02", "Victor Ruiz")
        assert r.ok

    def test_empty_string_fails(self):
        r = validate_rig_slot("N02", "")
        assert not r.ok

    def test_whitespace_only_fails(self):
        r = validate_rig_slot("N02", "   ")
        assert not r.ok

    def test_none_fails(self):
        r = validate_rig_slot("N02", None)
        assert not r.ok

    def test_integer_fails(self):
        r = validate_rig_slot("N02", 42)
        assert not r.ok

    def test_error_message_non_empty(self):
        r = validate_rig_slot("N02", "")
        assert r.error

    def test_no_model_call_needed(self):
        """RULE for N02 is structural (non-empty name); JUDGMENT is async."""
        # Passes without any external calls — deterministic check only
        r = validate_rig_slot("N02", "Any Name Works Here")
        assert r.ok


# ---------------------------------------------------------------------------
# N03 — Active Want (non-empty text)
# docs/03_scene_rig.md §3
# ---------------------------------------------------------------------------

class TestN03:
    def test_non_empty_text_passes(self):
        r = validate_rig_slot("N03", "Secure the confession before the hearing")
        assert r.ok

    def test_single_word_passes(self):
        r = validate_rig_slot("N03", "Escape")
        assert r.ok

    def test_empty_string_fails(self):
        r = validate_rig_slot("N03", "")
        assert not r.ok

    def test_whitespace_only_fails(self):
        r = validate_rig_slot("N03", "  \t  ")
        assert not r.ok

    def test_none_fails(self):
        r = validate_rig_slot("N03", None)
        assert not r.ok

    def test_integer_fails(self):
        r = validate_rig_slot("N03", 0)
        assert not r.ok

    def test_error_message_non_empty(self):
        r = validate_rig_slot("N03", "")
        assert r.error


# ---------------------------------------------------------------------------
# N04 — Obstacle (locus ∈ enum AND text non-empty)
# docs/03_scene_rig.md §3
# ---------------------------------------------------------------------------

class TestN04:
    def _valid(self, locus="AGENT", text="Victor refuses to cooperate"):
        return {"locus": locus, "text": text}

    def test_valid_dict_passes(self):
        r = validate_rig_slot("N04", self._valid())
        assert r.ok

    def test_all_locus_values_pass(self):
        for locus in OBSTACLE_LOCUS_VALUES:
            r = validate_rig_slot("N04", self._valid(locus=locus))
            assert r.ok, f"locus={locus} should pass: {r.error}"

    def test_invalid_locus_fails(self):
        r = validate_rig_slot("N04", {"locus": "SUPERNATURAL", "text": "A ghost"})
        assert not r.ok

    def test_empty_locus_fails(self):
        r = validate_rig_slot("N04", {"locus": "", "text": "Something"})
        assert not r.ok

    def test_empty_text_fails(self):
        r = validate_rig_slot("N04", {"locus": "AGENT", "text": ""})
        assert not r.ok

    def test_whitespace_text_fails(self):
        r = validate_rig_slot("N04", {"locus": "AGENT", "text": "   "})
        assert not r.ok

    def test_missing_text_key_fails(self):
        r = validate_rig_slot("N04", {"locus": "AGENT"})
        assert not r.ok

    def test_missing_locus_key_fails(self):
        r = validate_rig_slot("N04", {"text": "Something"})
        assert not r.ok

    def test_non_dict_fails(self):
        r = validate_rig_slot("N04", "AGENT: Victor refuses")
        assert not r.ok

    def test_json_string_parsed_and_passes(self):
        v = json.dumps({"locus": "INTERNAL", "text": "She cannot admit fear"})
        r = validate_rig_slot("N04", v)
        assert r.ok

    def test_invalid_json_string_fails(self):
        r = validate_rig_slot("N04", "not json at all")
        assert not r.ok

    def test_error_mentions_locus_or_allowed(self):
        r = validate_rig_slot("N04", {"locus": "BAD", "text": "x"})
        assert "locus" in r.error.lower() or "AGENT" in r.error

    def test_error_mentions_text(self):
        r = validate_rig_slot("N04", {"locus": "AGENT", "text": ""})
        assert "text" in r.error.lower() or "non-empty" in r.error.lower()


# ---------------------------------------------------------------------------
# N05 — Scene Frame (entry_state non-empty AND value_at_stake non-empty)
# docs/03_scene_rig.md §3
# The RULE enforces structural intent/execution separation at the field level.
# JUDGMENT (async Task 27) checks that entry_state describes OPENING not OUTCOME.
# ---------------------------------------------------------------------------

class TestN05:
    def _valid(self):
        return {"entry_state": "Partners are aligned", "value_at_stake": "The partnership itself"}

    def test_valid_dict_passes(self):
        r = validate_rig_slot("N05", self._valid())
        assert r.ok

    def test_empty_entry_state_fails(self):
        r = validate_rig_slot("N05", {"entry_state": "", "value_at_stake": "trust"})
        assert not r.ok

    def test_whitespace_entry_state_fails(self):
        r = validate_rig_slot("N05", {"entry_state": "  ", "value_at_stake": "trust"})
        assert not r.ok

    def test_empty_value_at_stake_fails(self):
        r = validate_rig_slot("N05", {"entry_state": "Trust is intact", "value_at_stake": ""})
        assert not r.ok

    def test_whitespace_value_at_stake_fails(self):
        r = validate_rig_slot("N05", {"entry_state": "x", "value_at_stake": "   "})
        assert not r.ok

    def test_missing_entry_state_fails(self):
        r = validate_rig_slot("N05", {"value_at_stake": "trust"})
        assert not r.ok

    def test_missing_value_at_stake_fails(self):
        r = validate_rig_slot("N05", {"entry_state": "trust is intact"})
        assert not r.ok

    def test_non_dict_fails(self):
        r = validate_rig_slot("N05", "entry: open")
        assert not r.ok

    def test_none_fails(self):
        r = validate_rig_slot("N05", None)
        assert not r.ok

    def test_json_string_parsed_and_passes(self):
        v = json.dumps({"entry_state": "Tension is high", "value_at_stake": "Her freedom"})
        r = validate_rig_slot("N05", v)
        assert r.ok

    def test_invalid_json_string_fails(self):
        r = validate_rig_slot("N05", "not valid json")
        assert not r.ok

    def test_error_mentions_entry_state(self):
        r = validate_rig_slot("N05", {"value_at_stake": "trust"})
        assert "entry_state" in r.error

    def test_error_mentions_value_at_stake(self):
        r = validate_rig_slot("N05", {"entry_state": "x"})
        assert "value_at_stake" in r.error

    def test_rule_does_not_judge_outcome_leakage(self):
        """
        The RULE does not check whether entry_state describes an outcome —
        that is JUDGMENT's job (async, Task 27).  A structurally valid but
        semantically bad value must still pass the RULE gate.
        """
        outcome_as_intent = {
            "entry_state": "Their marriage, which ends here",
            "value_at_stake": "The relationship they already destroyed",
        }
        r = validate_rig_slot("N05", outcome_as_intent)
        assert r.ok, (
            "RULE must not block outcome-leaking values; that is JUDGMENT's job."
        )


# ---------------------------------------------------------------------------
# N06 — Location (resolves or instantiates; non-empty name)
# docs/03_scene_rig.md §3
# ---------------------------------------------------------------------------

class TestN06:
    def test_non_empty_name_passes(self):
        r = validate_rig_slot("N06", "Police precinct")
        assert r.ok

    def test_single_word_passes(self):
        r = validate_rig_slot("N06", "Rooftop")
        assert r.ok

    def test_empty_string_fails(self):
        r = validate_rig_slot("N06", "")
        assert not r.ok

    def test_whitespace_only_fails(self):
        r = validate_rig_slot("N06", "   ")
        assert not r.ok

    def test_none_fails(self):
        r = validate_rig_slot("N06", None)
        assert not r.ok

    def test_error_message_non_empty(self):
        r = validate_rig_slot("N06", "")
        assert r.error


# ---------------------------------------------------------------------------
# N07 — Temporal Urgency (non-empty text)
# docs/03_scene_rig.md §3
# ---------------------------------------------------------------------------

class TestN07:
    def test_non_empty_text_passes(self):
        r = validate_rig_slot("N07", "Hearing begins in two hours")
        assert r.ok

    def test_single_word_passes(self):
        r = validate_rig_slot("N07", "Now")
        assert r.ok

    def test_empty_string_fails(self):
        r = validate_rig_slot("N07", "")
        assert not r.ok

    def test_whitespace_only_fails(self):
        r = validate_rig_slot("N07", "  \n  ")
        assert not r.ok

    def test_none_fails(self):
        r = validate_rig_slot("N07", None)
        assert not r.ok

    def test_error_message_non_empty(self):
        r = validate_rig_slot("N07", "")
        assert r.error


# ---------------------------------------------------------------------------
# Genre additions — unknown slots pass unconditionally (never gating)
# docs/03_scene_rig.md §5 — "genre additions are prompted but never gating"
# docs/03_scene_rig.md §4 — exit predicate names only N01–N07
# ---------------------------------------------------------------------------

class TestGenreAdditionSlotsNeverGating:
    """
    Genre-addition slots (e.g., a Speculative or Comedy slot) are outside
    the N01–N07 exit predicate and must never block the writer.
    """

    def test_unknown_slot_passes(self):
        r = validate_rig_slot("G01", "Any value")
        assert r.ok
        assert r.error == ""

    def test_unknown_slot_none_passes(self):
        r = validate_rig_slot("G01", None)
        assert r.ok

    def test_speculative_slot_passes(self):
        r = validate_rig_slot("SPEC_RULE", "World rule: magic depletes with use")
        assert r.ok

    def test_comedy_slot_passes(self):
        r = validate_rig_slot("COM_INCONGRUITY", "Deadpan detective in absurd situation")
        assert r.ok

    def test_romance_slot_passes(self):
        r = validate_rig_slot("ROM_VULNERABILITY", "She cannot admit she still loves him")
        assert r.ok

    def test_mystery_slot_passes(self):
        r = validate_rig_slot("INFO_DELTA", "Detective knows; suspect does not")
        assert r.ok

    def test_kinetic_slot_passes(self):
        r = validate_rig_slot("KIN_ESCALATION", "Car chase into tunnel")
        assert r.ok

    def test_nine_slots_for_speculative_comedy_all_clear(self):
        """
        A Speculative Comedy would otherwise put nine questions in front of
        every scene.  The genre-addition slots must never block drafting.
        """
        extras = {
            "SPEC_WORLD_RULE": "Magic is exhaustible",
            "COM_INCONGRUITY": "Protagonist is a vampire who hates the sight of blood",
        }
        for slot_id, value in extras.items():
            r = validate_rig_slot(slot_id, value)
            assert r.ok, f"Genre slot {slot_id} must not gate: {r.error}"


# ---------------------------------------------------------------------------
# Accept-first: all 7 RULE checks, no model call
# docs/03_scene_rig.md §4 — "All deterministic. All instant. No model call
#                             blocks the writer."
# ---------------------------------------------------------------------------

class TestAcceptFirstPredicate:
    """
    Verify that validate_rig_slot covers all 7 required slots and that the
    predicate is purely deterministic — no mocks, no I/O, no model calls.
    """

    VALID_VALUES = {
        "N01": "X05",
        "N02": "Alice",
        "N03": "Secure the confession before the hearing",
        "N04": {"locus": "AGENT", "text": "The suspect refuses to talk"},
        "N05": {"entry_state": "Partners aligned", "value_at_stake": "The partnership"},
        "N06": "Police precinct",
        "N07": "Hearing begins in two hours",
    }

    def test_all_seven_pass_with_valid_values(self):
        for slot_id, value in self.VALID_VALUES.items():
            r = validate_rig_slot(slot_id, value)
            assert r.ok, f"{slot_id} should pass: {r.error}"

    def test_each_slot_fails_on_empty_string(self):
        """Every N0x slot rejects an empty string — the gate is real."""
        slots_that_take_string = ["N02", "N03", "N06", "N07"]
        for slot_id in slots_that_take_string:
            r = validate_rig_slot(slot_id, "")
            assert not r.ok, f"{slot_id} should reject empty string"

    def test_n01_rejects_out_of_range(self):
        r = validate_rig_slot("N01", "X99")
        assert not r.ok

    def test_n04_rejects_unknown_locus(self):
        r = validate_rig_slot("N04", {"locus": "MAGIC", "text": "spell fails"})
        assert not r.ok

    def test_n05_rejects_missing_both_fields(self):
        r = validate_rig_slot("N05", {})
        assert not r.ok

    def test_rule_returns_immediately_no_io(self):
        """
        RULE checks are synchronous and instant — they must not block.
        Calling all 7 in sequence completes without any I/O.
        This test is its own evidence: if it calls a model it would hang.
        """
        import time
        start = time.monotonic()
        for slot_id, value in self.VALID_VALUES.items():
            validate_rig_slot(slot_id, value)
        elapsed = time.monotonic() - start
        assert elapsed < 0.1, f"RULE checks took {elapsed:.3f}s — should be instant"
