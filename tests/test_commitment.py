"""
Tests for the Greenlight commitment state machine.

docs/02_greenlight.md §4 — SKEPTICAL → COMMITTED transition
docs/02_greenlight.md §5 — register gating

Acceptance criterion (Task 23):
    projects.commitment_state transitions from SKEPTICAL to COMMITTED when all
    12 required slots are filled and at least 10 of those 12 have
    input_conf = VALIDATED. Optional slots S11 and TP1 do not affect the
    transition. The transition is one-way. COMMITMENT_CHANGED is emitted to
    Confluent on transition. Register gating is exposed for the voice layer.

All Supabase and Confluent calls are patched. No network I/O.

Run with: python -m pytest tests/test_commitment.py -v
"""

import pytest
from unittest.mock import MagicMock, patch, call

from src.greenlight import (
    REQUIRED_SLOTS,
    exit_predicate_met,
    validated_slot_count,
    unfilled_required_slots,
    available_registers,
    get_commitment_state,
    check_and_apply_commitment,
    LOCKED_WHILE_SKEPTICAL,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _slots(*, filled_count: int = 12, validated_count: int = 12) -> dict[str, dict]:
    """
    Build a synthetic slots dict with the given number of filled and validated
    required slots. Slots beyond filled_count are absent. Slots beyond
    validated_count (but within filled_count) are PROVISIONAL.
    """
    slots: dict[str, dict] = {}
    for i, slot_id in enumerate(REQUIRED_SLOTS):
        if i >= filled_count:
            break
        conf = "VALIDATED" if i < validated_count else "PROVISIONAL"
        slots[slot_id] = {"is_filled": True, "input_conf": conf}
    return slots


def _make_supabase_mock(current_state: str = "SKEPTICAL") -> MagicMock:
    """Return a mock Supabase client returning current_state on .single()."""
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "commitment_state": current_state,
    }
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    return sb


# ---------------------------------------------------------------------------
# exit_predicate_met
# ---------------------------------------------------------------------------

class TestExitPredicateMet:
    def test_all_12_filled_returns_true(self):
        slots = _slots(filled_count=12)
        assert exit_predicate_met(slots) is True

    def test_11_filled_returns_false(self):
        slots = _slots(filled_count=11)
        assert exit_predicate_met(slots) is False

    def test_empty_slots_returns_false(self):
        assert exit_predicate_met({}) is False

    def test_optional_slots_do_not_count(self):
        """S11 and TP1 are optional; their absence does not block the exit predicate."""
        slots = _slots(filled_count=12)
        # S11 and TP1 absent — predicate must still pass
        assert "S11" not in slots
        assert "TP1" not in slots
        assert exit_predicate_met(slots) is True

    def test_optional_slots_present_do_not_break_predicate(self):
        slots = _slots(filled_count=12)
        slots["S11"] = {"is_filled": True, "input_conf": "VALIDATED"}
        slots["TP1"] = {"is_filled": True, "input_conf": "VALIDATED"}
        assert exit_predicate_met(slots) is True


# ---------------------------------------------------------------------------
# validated_slot_count
# ---------------------------------------------------------------------------

class TestValidatedSlotCount:
    def test_all_12_validated(self):
        slots = _slots(validated_count=12)
        assert validated_slot_count(slots) == 12

    def test_10_validated(self):
        slots = _slots(validated_count=10)
        assert validated_slot_count(slots) == 10

    def test_9_validated(self):
        slots = _slots(validated_count=9)
        assert validated_slot_count(slots) == 9

    def test_zero_validated(self):
        slots = _slots(validated_count=0)
        assert validated_slot_count(slots) == 0

    def test_optional_slots_excluded(self):
        """S11 and TP1, even if VALIDATED, do not inflate the count."""
        slots = _slots(validated_count=12)
        slots["S11"] = {"is_filled": True, "input_conf": "VALIDATED"}
        slots["TP1"] = {"is_filled": True, "input_conf": "VALIDATED"}
        # Still 12, not 14
        assert validated_slot_count(slots) == 12

    def test_empty_slots(self):
        assert validated_slot_count({}) == 0


# ---------------------------------------------------------------------------
# check_and_apply_commitment — transition predicate
# ---------------------------------------------------------------------------

class TestCommitmentTransitionPredicate:
    """
    The state machine fires only when:
      - all 12 required slots are filled
      - at least 10 of those 12 have input_conf = VALIDATED
      - current state is SKEPTICAL
    """

    def _run(self, filled: int, validated: int, current_state: str = "SKEPTICAL"):
        slots = _slots(filled_count=filled, validated_count=validated)
        sb_mock = _make_supabase_mock(current_state)
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event") as pub:
            result = check_and_apply_commitment("proj-1", slots)
        return result, sb_mock, pub

    def test_12_filled_10_validated_transitions(self):
        result, sb, pub = self._run(12, 10)
        assert result is True

    def test_12_filled_11_validated_transitions(self):
        result, _, _ = self._run(12, 11)
        assert result is True

    def test_12_filled_12_validated_transitions(self):
        result, _, _ = self._run(12, 12)
        assert result is True

    def test_12_filled_9_validated_does_not_transition(self):
        """Nine validated — one short of threshold."""
        result, _, _ = self._run(12, 9)
        assert result is False

    def test_12_filled_0_validated_does_not_transition(self):
        result, _, _ = self._run(12, 0)
        assert result is False

    def test_11_filled_11_validated_does_not_transition(self):
        """Exit predicate not met — not all 12 filled."""
        result, _, _ = self._run(11, 11)
        assert result is False

    def test_0_filled_does_not_transition(self):
        result, _, _ = self._run(0, 0)
        assert result is False

    def test_already_committed_returns_false(self):
        """One-way: transition does not fire when already COMMITTED."""
        result, _, _ = self._run(12, 12, current_state="COMMITTED")
        assert result is False

    def test_already_committed_does_not_write_supabase(self):
        """One-way: no DB write when already COMMITTED."""
        slots = _slots(filled_count=12, validated_count=12)
        sb_mock = _make_supabase_mock("COMMITTED")
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event"):
            check_and_apply_commitment("proj-1", slots)
        sb_mock.table.return_value.update.assert_not_called()

    def test_already_committed_does_not_publish_event(self):
        """One-way: no Confluent event when already COMMITTED."""
        slots = _slots(filled_count=12, validated_count=12)
        sb_mock = _make_supabase_mock("COMMITTED")
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event") as pub:
            check_and_apply_commitment("proj-1", slots)
        pub.assert_not_called()


# ---------------------------------------------------------------------------
# check_and_apply_commitment — Supabase write
# ---------------------------------------------------------------------------

class TestCommitmentSupabaseWrite:
    def test_updates_commitment_state_to_committed(self):
        slots = _slots(filled_count=12, validated_count=10)
        sb_mock = _make_supabase_mock("SKEPTICAL")
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event"):
            check_and_apply_commitment("proj-42", slots)
        sb_mock.table.return_value.update.assert_called_once_with(
            {"commitment_state": "COMMITTED"}
        )

    def test_update_filters_by_project_id(self):
        slots = _slots(filled_count=12, validated_count=10)
        sb_mock = _make_supabase_mock("SKEPTICAL")
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event"):
            check_and_apply_commitment("proj-42", slots)
        sb_mock.table.return_value.update.return_value.eq.assert_called_once_with(
            "project_id", "proj-42"
        )


# ---------------------------------------------------------------------------
# check_and_apply_commitment — Confluent event
# ---------------------------------------------------------------------------

class TestCommitmentConfluentEvent:
    def test_emits_commitment_changed_event(self):
        slots = _slots(filled_count=12, validated_count=10)
        sb_mock = _make_supabase_mock("SKEPTICAL")
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event") as pub:
            check_and_apply_commitment("proj-1", slots)
        pub.assert_called_once()
        kwargs = pub.call_args

    def test_event_type_is_commitment_changed(self):
        slots = _slots(filled_count=12, validated_count=10)
        sb_mock = _make_supabase_mock("SKEPTICAL")
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event") as pub:
            check_and_apply_commitment("proj-1", slots)
        _, kwargs = pub.call_args
        assert kwargs["event_type"] == "COMMITMENT_CHANGED"

    def test_event_payload_from_state(self):
        slots = _slots(filled_count=12, validated_count=10)
        sb_mock = _make_supabase_mock("SKEPTICAL")
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event") as pub:
            check_and_apply_commitment("proj-1", slots)
        _, kwargs = pub.call_args
        assert kwargs["payload"]["from_state"] == "SKEPTICAL"

    def test_event_payload_to_state(self):
        slots = _slots(filled_count=12, validated_count=10)
        sb_mock = _make_supabase_mock("SKEPTICAL")
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event") as pub:
            check_and_apply_commitment("proj-1", slots)
        _, kwargs = pub.call_args
        assert kwargs["payload"]["to_state"] == "COMMITTED"

    def test_event_payload_validated_slot_count(self):
        slots = _slots(filled_count=12, validated_count=10)
        sb_mock = _make_supabase_mock("SKEPTICAL")
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event") as pub:
            check_and_apply_commitment("proj-1", slots)
        _, kwargs = pub.call_args
        assert kwargs["payload"]["validated_slot_count"] == 10

    def test_event_payload_validated_slot_count_12(self):
        slots = _slots(filled_count=12, validated_count=12)
        sb_mock = _make_supabase_mock("SKEPTICAL")
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event") as pub:
            check_and_apply_commitment("proj-1", slots)
        _, kwargs = pub.call_args
        assert kwargs["payload"]["validated_slot_count"] == 12

    def test_event_project_id_set(self):
        slots = _slots(filled_count=12, validated_count=10)
        sb_mock = _make_supabase_mock("SKEPTICAL")
        with patch("src.greenlight.get_supabase", return_value=sb_mock), \
             patch("src.greenlight.publish_event") as pub:
            check_and_apply_commitment("proj-xyz", slots)
        _, kwargs = pub.call_args
        assert kwargs["project_id"] == "proj-xyz"


# ---------------------------------------------------------------------------
# Register gating — available_registers()
# ---------------------------------------------------------------------------

class TestAvailableRegisters:
    def test_skeptical_excludes_enthusiastic_advocacy(self):
        regs = available_registers("SKEPTICAL")
        assert "Enthusiastic Advocacy" not in regs

    def test_skeptical_includes_four_other_registers(self):
        regs = available_registers("SKEPTICAL")
        assert "Mentorial Anecdotal" in regs
        assert "Diagnostic Unsparing" in regs
        assert "Borscht Belt Deflection" in regs
        assert "Transactional Boundary" in regs

    def test_skeptical_returns_four_registers(self):
        assert len(available_registers("SKEPTICAL")) == 4

    def test_committed_includes_all_five(self):
        regs = available_registers("COMMITTED")
        assert len(regs) == 5
        assert "Enthusiastic Advocacy" in regs

    def test_committed_includes_enthusiastic_advocacy(self):
        assert "Enthusiastic Advocacy" in available_registers("COMMITTED")

    def test_locked_while_skeptical_constant(self):
        assert LOCKED_WHILE_SKEPTICAL == "Enthusiastic Advocacy"

    def test_unknown_state_treated_as_skeptical(self):
        regs = available_registers("UNKNOWN")
        assert "Enthusiastic Advocacy" not in regs


# ---------------------------------------------------------------------------
# Register gating — get_commitment_state()
# ---------------------------------------------------------------------------

class TestGetCommitmentState:
    def _mock_state(self, state: str) -> MagicMock:
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "commitment_state": state,
        }
        return sb

    def test_skeptical_state_returned(self):
        with patch("src.greenlight.get_supabase", return_value=self._mock_state("SKEPTICAL")):
            info = get_commitment_state("proj-1")
        assert info["commitment_state"] == "SKEPTICAL"

    def test_committed_state_returned(self):
        with patch("src.greenlight.get_supabase", return_value=self._mock_state("COMMITTED")):
            info = get_commitment_state("proj-1")
        assert info["commitment_state"] == "COMMITTED"

    def test_skeptical_advocacy_locked_true(self):
        with patch("src.greenlight.get_supabase", return_value=self._mock_state("SKEPTICAL")):
            info = get_commitment_state("proj-1")
        assert info["enthusiastic_advocacy_locked"] is True

    def test_committed_advocacy_locked_false(self):
        with patch("src.greenlight.get_supabase", return_value=self._mock_state("COMMITTED")):
            info = get_commitment_state("proj-1")
        assert info["enthusiastic_advocacy_locked"] is False

    def test_skeptical_use_name_not_kid_false(self):
        with patch("src.greenlight.get_supabase", return_value=self._mock_state("SKEPTICAL")):
            info = get_commitment_state("proj-1")
        assert info["use_name_not_kid"] is False

    def test_committed_use_name_not_kid_true(self):
        with patch("src.greenlight.get_supabase", return_value=self._mock_state("COMMITTED")):
            info = get_commitment_state("proj-1")
        assert info["use_name_not_kid"] is True

    def test_skeptical_available_registers_has_four(self):
        with patch("src.greenlight.get_supabase", return_value=self._mock_state("SKEPTICAL")):
            info = get_commitment_state("proj-1")
        assert len(info["available_registers"]) == 4

    def test_committed_available_registers_has_five(self):
        with patch("src.greenlight.get_supabase", return_value=self._mock_state("COMMITTED")):
            info = get_commitment_state("proj-1")
        assert len(info["available_registers"]) == 5
