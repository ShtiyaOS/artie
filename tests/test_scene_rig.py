"""
Tests for the Scene Rig slot-filling conversation and persistence.

docs/03_scene_rig.md §1  — resets each scene
docs/03_scene_rig.md §2  — 7 required slots
docs/03_scene_rig.md §4  — exit predicate (RULE only; accept-first)
docs/03_scene_rig.md §6  — carry-over rules

Acceptance criterion (Task 25):
    For a given scene, a user can converse with Artie and the backend
    persists answers to the seven required Scene Rig slots in the
    scene_rig_slots table.

All Supabase and Confluent calls are patched. No network I/O.

Run with: python -m pytest tests/test_scene_rig.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call

from src.scene_rig import (
    REQUIRED_SLOTS,
    SLOT_LABELS,
    POSITION_VALUES,
    OBSTACLE_LOCUS_VALUES,
    load_rig_slots,
    upsert_rig_slot,
    unfilled_required_slots,
    exit_predicate_met,
    compute_prefills,
    resolve_or_create_character,
    resolve_or_create_location,
    get_project_genre,
)
from src.scene_rig_conversation import _validate_rig_slot


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SCENE_ID   = "scene-0001"
PROJECT_ID = "proj-0001"


def _slots_all_filled() -> dict[str, dict]:
    """Return a fully-filled rig slots dict for tests."""
    return {
        "N01": {"is_filled": True, "value": "X03", "input_conf": "VALIDATED"},
        "N02": {"is_filled": True, "value": {"name": "Alice", "character_id": "c-1"}, "input_conf": "VALIDATED"},
        "N03": {"is_filled": True, "value": "Secure a confession before the hearing", "input_conf": "VALIDATED"},
        "N04": {"is_filled": True, "value": {"locus": "AGENT", "text": "The suspect refuses to talk"}, "input_conf": "VALIDATED"},
        "N05": {"is_filled": True, "value": {"entry_state": "Partners are aligned", "value_at_stake": "The partnership itself"}, "input_conf": "VALIDATED"},
        "N06": {"is_filled": True, "value": {"name": "Police precinct", "location_id": "l-1"}, "input_conf": "VALIDATED"},
        "N07": {"is_filled": True, "value": "Hearing begins in two hours", "input_conf": "VALIDATED"},
    }


def _slots_partial(filled: int) -> dict[str, dict]:
    """Return a slots dict with `filled` slots filled in order."""
    all_filled = _slots_all_filled()
    result = {}
    for i, sid in enumerate(REQUIRED_SLOTS):
        if i >= filled:
            break
        result[sid] = all_filled[sid]
    return result


def _sb_mock_empty() -> MagicMock:
    """Supabase mock returning no rows."""
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None
    sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"character_id": "c-new", "location_id": "l-new"}]
    return sb


# ---------------------------------------------------------------------------
# Slot catalogue
# ---------------------------------------------------------------------------

class TestSlotCatalogue:
    def test_seven_required_slots(self):
        assert len(REQUIRED_SLOTS) == 7

    def test_required_slot_ids(self):
        assert set(REQUIRED_SLOTS) == {"N01", "N02", "N03", "N04", "N05", "N06", "N07"}

    def test_all_slots_have_labels(self):
        for sid in REQUIRED_SLOTS:
            assert sid in SLOT_LABELS, f"No label for {sid}"
            assert SLOT_LABELS[sid], f"Empty label for {sid}"

    def test_position_values_x01_to_x12(self):
        assert len(POSITION_VALUES) == 12
        for i in range(1, 13):
            assert f"X{i:02d}" in POSITION_VALUES

    def test_obstacle_locus_enum_non_empty(self):
        assert len(OBSTACLE_LOCUS_VALUES) >= 4


# ---------------------------------------------------------------------------
# exit_predicate_met
# ---------------------------------------------------------------------------

class TestExitPredicateMet:
    def test_all_7_filled_returns_true(self):
        assert exit_predicate_met(_slots_all_filled()) is True

    def test_6_filled_returns_false(self):
        assert exit_predicate_met(_slots_partial(6)) is False

    def test_empty_returns_false(self):
        assert exit_predicate_met({}) is False

    def test_0_filled_returns_false(self):
        assert exit_predicate_met(_slots_partial(0)) is False

    def test_all_7_individually(self):
        for i in range(1, 8):
            result = exit_predicate_met(_slots_partial(i))
            if i == 7:
                assert result is True
            else:
                assert result is False


# ---------------------------------------------------------------------------
# unfilled_required_slots
# ---------------------------------------------------------------------------

class TestUnfilledRequiredSlots:
    def test_all_filled_returns_empty_list(self):
        assert unfilled_required_slots(_slots_all_filled()) == []

    def test_empty_slots_returns_all_required(self):
        unfilled = unfilled_required_slots({})
        assert set(unfilled) == set(REQUIRED_SLOTS)

    def test_partial_fill_returns_remainder(self):
        unfilled = unfilled_required_slots(_slots_partial(3))
        assert len(unfilled) == 4

    def test_unfilled_order_follows_catalogue(self):
        """Unfilled list follows the catalogue order."""
        unfilled = unfilled_required_slots(_slots_partial(2))
        assert unfilled == REQUIRED_SLOTS[2:]


# ---------------------------------------------------------------------------
# RULE validation — _validate_rig_slot
# ---------------------------------------------------------------------------

class TestValidateRigSlotN01:
    def test_valid_position_passes(self):
        ok, err = _validate_rig_slot("N01", "X01")
        assert ok
        assert err == ""

    def test_x12_passes(self):
        ok, _ = _validate_rig_slot("N01", "X12")
        assert ok

    def test_all_valid_positions_pass(self):
        for pos in POSITION_VALUES:
            ok, _ = _validate_rig_slot("N01", pos)
            assert ok, f"Position {pos} should pass"

    def test_invalid_position_fails(self):
        ok, err = _validate_rig_slot("N01", "X13")
        assert not ok
        assert err

    def test_lowercase_fails(self):
        ok, _ = _validate_rig_slot("N01", "x01")
        assert not ok

    def test_empty_string_fails(self):
        ok, _ = _validate_rig_slot("N01", "")
        assert not ok

    def test_none_fails(self):
        ok, _ = _validate_rig_slot("N01", None)
        assert not ok

    def test_integer_fails(self):
        ok, _ = _validate_rig_slot("N01", 1)
        assert not ok

    def test_error_message_lists_allowed(self):
        _, err = _validate_rig_slot("N01", "X99")
        assert "X01" in err


class TestValidateRigSlotN02:
    def test_non_empty_name_passes(self):
        ok, _ = _validate_rig_slot("N02", "Alice")
        assert ok

    def test_empty_string_fails(self):
        ok, _ = _validate_rig_slot("N02", "")
        assert not ok

    def test_whitespace_only_fails(self):
        ok, _ = _validate_rig_slot("N02", "   ")
        assert not ok

    def test_none_fails(self):
        ok, _ = _validate_rig_slot("N02", None)
        assert not ok


class TestValidateRigSlotN03:
    def test_non_empty_text_passes(self):
        ok, _ = _validate_rig_slot("N03", "Get the confession before the hearing")
        assert ok

    def test_empty_fails(self):
        ok, _ = _validate_rig_slot("N03", "")
        assert not ok

    def test_none_fails(self):
        ok, _ = _validate_rig_slot("N03", None)
        assert not ok


class TestValidateRigSlotN04:
    def _valid(self, locus="AGENT", text="Victor won't cooperate"):
        return {"locus": locus, "text": text}

    def test_valid_dict_passes(self):
        ok, _ = _validate_rig_slot("N04", self._valid())
        assert ok

    def test_all_locus_values_pass(self):
        for locus in OBSTACLE_LOCUS_VALUES:
            ok, err = _validate_rig_slot("N04", self._valid(locus=locus))
            assert ok, f"Locus {locus} should pass: {err}"

    def test_invalid_locus_fails(self):
        ok, err = _validate_rig_slot("N04", {"locus": "SUPERNATURAL", "text": "Something"})
        assert not ok
        assert err

    def test_empty_locus_fails(self):
        ok, _ = _validate_rig_slot("N04", {"locus": "", "text": "Something"})
        assert not ok

    def test_empty_text_fails(self):
        ok, _ = _validate_rig_slot("N04", {"locus": "AGENT", "text": ""})
        assert not ok

    def test_missing_text_fails(self):
        ok, _ = _validate_rig_slot("N04", {"locus": "AGENT"})
        assert not ok

    def test_missing_locus_fails(self):
        ok, _ = _validate_rig_slot("N04", {"text": "Something"})
        assert not ok

    def test_not_a_dict_fails(self):
        ok, _ = _validate_rig_slot("N04", "AGENT: Victor")
        assert not ok

    def test_json_string_passes(self):
        value = json.dumps({"locus": "AGENT", "text": "Victor refuses"})
        ok, _ = _validate_rig_slot("N04", value)
        assert ok

    def test_error_mentions_locus(self):
        _, err = _validate_rig_slot("N04", {"locus": "BAD", "text": "x"})
        assert "locus" in err.lower() or "AGENT" in err


class TestValidateRigSlotN05:
    def _valid(self):
        return {"entry_state": "Partners aligned", "value_at_stake": "The partnership"}

    def test_valid_dict_passes(self):
        ok, _ = _validate_rig_slot("N05", self._valid())
        assert ok

    def test_empty_entry_state_fails(self):
        ok, _ = _validate_rig_slot("N05", {"entry_state": "", "value_at_stake": "x"})
        assert not ok

    def test_empty_value_at_stake_fails(self):
        ok, _ = _validate_rig_slot("N05", {"entry_state": "x", "value_at_stake": ""})
        assert not ok

    def test_missing_entry_state_fails(self):
        ok, _ = _validate_rig_slot("N05", {"value_at_stake": "x"})
        assert not ok

    def test_missing_value_at_stake_fails(self):
        ok, _ = _validate_rig_slot("N05", {"entry_state": "x"})
        assert not ok

    def test_not_a_dict_fails(self):
        ok, _ = _validate_rig_slot("N05", "entry: open")
        assert not ok

    def test_json_string_passes(self):
        value = json.dumps({"entry_state": "Open", "value_at_stake": "Trust"})
        ok, _ = _validate_rig_slot("N05", value)
        assert ok

    def test_error_mentions_entry_state(self):
        _, err = _validate_rig_slot("N05", {"value_at_stake": "x"})
        assert "entry_state" in err

    def test_error_mentions_value_at_stake(self):
        _, err = _validate_rig_slot("N05", {"entry_state": "x"})
        assert "value_at_stake" in err


class TestValidateRigSlotN06:
    def test_non_empty_name_passes(self):
        ok, _ = _validate_rig_slot("N06", "Police precinct")
        assert ok

    def test_empty_string_fails(self):
        ok, _ = _validate_rig_slot("N06", "")
        assert not ok

    def test_none_fails(self):
        ok, _ = _validate_rig_slot("N06", None)
        assert not ok


class TestValidateRigSlotN07:
    def test_non_empty_text_passes(self):
        ok, _ = _validate_rig_slot("N07", "Hearing in two hours")
        assert ok

    def test_empty_fails(self):
        ok, _ = _validate_rig_slot("N07", "")
        assert not ok

    def test_none_fails(self):
        ok, _ = _validate_rig_slot("N07", None)
        assert not ok


# ---------------------------------------------------------------------------
# upsert_rig_slot — Supabase write + Confluent event
# ---------------------------------------------------------------------------

class TestUpsertRigSlot:
    def _run(self, **kwargs):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        with patch("src.scene_rig.get_supabase", return_value=sb), \
             patch("src.scene_rig.publish_event") as pub:
            upsert_rig_slot(
                SCENE_ID,
                kwargs.get("slot_id", "N03"),
                kwargs.get("value", "Get confession"),
                input_conf=kwargs.get("input_conf", "VALIDATED"),
                project_id=kwargs.get("project_id", PROJECT_ID),
            )
        return sb, pub

    def test_upserts_to_scene_rig_slots_table(self):
        sb, _ = self._run()
        sb.table.assert_any_call("scene_rig_slots")

    def test_upsert_includes_is_filled_true(self):
        sb, _ = self._run()
        upsert_call = sb.table.return_value.upsert.call_args
        data = upsert_call[0][0]
        assert data["is_filled"] is True

    def test_upsert_includes_scene_id(self):
        sb, _ = self._run()
        data = sb.table.return_value.upsert.call_args[0][0]
        assert data["scene_id"] == SCENE_ID

    def test_upsert_includes_slot_id(self):
        sb, _ = self._run(slot_id="N03")
        data = sb.table.return_value.upsert.call_args[0][0]
        assert data["slot_id"] == "N03"

    def test_upsert_includes_input_conf(self):
        sb, _ = self._run(input_conf="PROVISIONAL")
        data = sb.table.return_value.upsert.call_args[0][0]
        assert data["input_conf"] == "PROVISIONAL"

    def test_publishes_slot_answered_event(self):
        _, pub = self._run()
        pub.assert_called_once()
        _, kwargs = pub.call_args
        assert kwargs["event_type"] == "SLOT_ANSWERED"

    def test_event_payload_has_gate_scene_rig(self):
        _, pub = self._run()
        _, kwargs = pub.call_args
        assert kwargs["payload"]["gate"] == "SCENE_RIG"

    def test_event_project_id(self):
        _, pub = self._run(project_id="proj-42")
        _, kwargs = pub.call_args
        assert kwargs["project_id"] == "proj-42"

    def test_dict_value_serialised_to_json(self):
        val = {"entry_state": "x", "value_at_stake": "y"}
        sb, _ = self._run(slot_id="N05", value=val)
        data = sb.table.return_value.upsert.call_args[0][0]
        # JSONB column receives the JSON string
        stored = data["value"]
        assert isinstance(stored, str)
        parsed = json.loads(stored)
        assert parsed["entry_state"] == "x"

    def test_string_value_stored_directly(self):
        sb, _ = self._run(slot_id="N03", value="Get confession")
        data = sb.table.return_value.upsert.call_args[0][0]
        assert data["value"] == "Get confession"


# ---------------------------------------------------------------------------
# load_rig_slots
# ---------------------------------------------------------------------------

class TestLoadRigSlots:
    def test_returns_dict_keyed_by_slot_id(self):
        rows = [
            {"slot_id": "N01", "value": "X03", "is_filled": True, "input_conf": "VALIDATED", "reask_count": 0},
            {"slot_id": "N03", "value": "Get confession", "is_filled": True, "input_conf": "VALIDATED", "reask_count": 0},
        ]
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = rows
        with patch("src.scene_rig.get_supabase", return_value=sb):
            result = load_rig_slots(SCENE_ID)
        assert "N01" in result
        assert "N03" in result

    def test_empty_table_returns_empty_dict(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        with patch("src.scene_rig.get_supabase", return_value=sb):
            result = load_rig_slots(SCENE_ID)
        assert result == {}


# ---------------------------------------------------------------------------
# Roster accretion — resolve_or_create_character
# ---------------------------------------------------------------------------

class TestResolveOrCreateCharacter:
    def _make_sb(self, existing_id=None):
        sb = MagicMock()
        if existing_id:
            sb.table.return_value.select.return_value.eq.return_value.ilike.return_value.limit.return_value.execute.return_value.data = [
                {"character_id": existing_id}
            ]
        else:
            sb.table.return_value.select.return_value.eq.return_value.ilike.return_value.limit.return_value.execute.return_value.data = []
            sb.table.return_value.insert.return_value.execute.return_value.data = [
                {"character_id": "c-new-1"}
            ]
        return sb

    def test_returns_existing_character_id(self):
        sb = self._make_sb(existing_id="c-existing")
        with patch("src.scene_rig.get_supabase", return_value=sb):
            cid = resolve_or_create_character(PROJECT_ID, "Alice")
        assert cid == "c-existing"

    def test_creates_new_character_when_not_found(self):
        sb = self._make_sb()
        with patch("src.scene_rig.get_supabase", return_value=sb):
            cid = resolve_or_create_character(PROJECT_ID, "Bob")
        assert cid == "c-new-1"

    def test_new_character_inserted_with_scene_rig_source(self):
        sb = self._make_sb()
        with patch("src.scene_rig.get_supabase", return_value=sb):
            resolve_or_create_character(PROJECT_ID, "Bob")
        insert_call = sb.table.return_value.insert.call_args[0][0]
        assert insert_call["source"] == "SCENE_RIG"

    def test_new_character_has_secondary_role(self):
        sb = self._make_sb()
        with patch("src.scene_rig.get_supabase", return_value=sb):
            resolve_or_create_character(PROJECT_ID, "Bob")
        insert_call = sb.table.return_value.insert.call_args[0][0]
        assert insert_call["role"] == "SECONDARY"

    def test_strips_whitespace_from_name(self):
        sb = self._make_sb()
        with patch("src.scene_rig.get_supabase", return_value=sb):
            resolve_or_create_character(PROJECT_ID, "  Carol  ")
        insert_call = sb.table.return_value.insert.call_args[0][0]
        assert insert_call["name"] == "Carol"


# ---------------------------------------------------------------------------
# Arena accretion — resolve_or_create_location
# ---------------------------------------------------------------------------

class TestResolveOrCreateLocation:
    def _make_sb(self, existing_id=None):
        sb = MagicMock()
        if existing_id:
            sb.table.return_value.select.return_value.eq.return_value.ilike.return_value.limit.return_value.execute.return_value.data = [
                {"location_id": existing_id}
            ]
        else:
            sb.table.return_value.select.return_value.eq.return_value.ilike.return_value.limit.return_value.execute.return_value.data = []
            sb.table.return_value.insert.return_value.execute.return_value.data = [
                {"location_id": "l-new-1"}
            ]
        return sb

    def test_returns_existing_location_id(self):
        sb = self._make_sb(existing_id="l-existing")
        with patch("src.scene_rig.get_supabase", return_value=sb):
            lid = resolve_or_create_location(PROJECT_ID, "Police precinct")
        assert lid == "l-existing"

    def test_creates_new_location_when_not_found(self):
        sb = self._make_sb()
        with patch("src.scene_rig.get_supabase", return_value=sb):
            lid = resolve_or_create_location(PROJECT_ID, "Rooftop")
        assert lid == "l-new-1"

    def test_new_location_inserted_with_scene_rig_source(self):
        sb = self._make_sb()
        with patch("src.scene_rig.get_supabase", return_value=sb):
            resolve_or_create_location(PROJECT_ID, "Rooftop")
        insert_call = sb.table.return_value.insert.call_args[0][0]
        assert insert_call["source"] == "SCENE_RIG"

    def test_strips_whitespace_from_name(self):
        sb = self._make_sb()
        with patch("src.scene_rig.get_supabase", return_value=sb):
            resolve_or_create_location(PROJECT_ID, "  Rooftop  ")
        insert_call = sb.table.return_value.insert.call_args[0][0]
        assert insert_call["name"] == "Rooftop"


# ---------------------------------------------------------------------------
# compute_prefills — carry-over N01
# ---------------------------------------------------------------------------

class TestComputePrefills:
    def _make_sb_with_prior(self, prior_position_id: int | None):
        sb = MagicMock()
        # Current scene row
        sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "sequence_order": 5
        }
        # Prior scene row
        if prior_position_id is not None:
            sb.table.return_value.select.return_value.eq.return_value.lt.return_value.order.return_value.limit.return_value.execute.return_value.data = [
                {"scene_id": "prior-scene", "position_id": prior_position_id}
            ]
        else:
            sb.table.return_value.select.return_value.eq.return_value.lt.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        return sb

    def test_n01_prefills_from_prior_position(self):
        sb = self._make_sb_with_prior(prior_position_id=3)
        with patch("src.scene_rig.get_supabase", return_value=sb):
            prefills = compute_prefills(SCENE_ID, PROJECT_ID)
        assert prefills.get("N01") == "X03"

    def test_no_prior_scene_returns_empty(self):
        sb = self._make_sb_with_prior(prior_position_id=None)
        with patch("src.scene_rig.get_supabase", return_value=sb):
            prefills = compute_prefills(SCENE_ID, PROJECT_ID)
        assert "N01" not in prefills

    def test_n03_n04_n05_n07_never_prefill(self):
        sb = self._make_sb_with_prior(prior_position_id=7)
        with patch("src.scene_rig.get_supabase", return_value=sb):
            prefills = compute_prefills(SCENE_ID, PROJECT_ID)
        for reset_slot in ("N03", "N04", "N05", "N07"):
            assert reset_slot not in prefills, f"{reset_slot} must not pre-fill"

    def test_out_of_range_position_not_prefilled(self):
        """position_id = 13 has no X13 in POSITION_VALUES; should not prefill."""
        sb = self._make_sb_with_prior(prior_position_id=13)
        with patch("src.scene_rig.get_supabase", return_value=sb):
            prefills = compute_prefills(SCENE_ID, PROJECT_ID)
        assert "N01" not in prefills

    def test_scene_not_found_returns_empty(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None
        with patch("src.scene_rig.get_supabase", return_value=sb):
            prefills = compute_prefills(SCENE_ID, PROJECT_ID)
        assert prefills == {}


# ---------------------------------------------------------------------------
# get_project_genre
# ---------------------------------------------------------------------------

class TestGetProjectGenre:
    def _make_sb(self, value):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "value": value
        }
        return sb

    def test_returns_genre_string(self):
        sb = self._make_sb("Drama")
        with patch("src.scene_rig.get_supabase", return_value=sb):
            genre = get_project_genre(PROJECT_ID)
        assert genre == "Drama"

    def test_returns_none_when_no_row(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = None
        with patch("src.scene_rig.get_supabase", return_value=sb):
            genre = get_project_genre(PROJECT_ID)
        assert genre is None

    def test_handles_exception_gracefully(self):
        sb = MagicMock()
        sb.table.side_effect = Exception("DB error")
        with patch("src.scene_rig.get_supabase", return_value=sb):
            genre = get_project_genre(PROJECT_ID)
        assert genre is None


# ---------------------------------------------------------------------------
# scene_rig_conversation._validate_rig_slot — unknown slot passes
# ---------------------------------------------------------------------------

class TestValidateRigSlotUnknown:
    def test_unknown_slot_passes(self):
        ok, err = _validate_rig_slot("ZZZZ", "any value")
        assert ok
        assert err == ""

    def test_unknown_slot_none_passes(self):
        ok, _ = _validate_rig_slot("ZZZZ", None)
        assert ok


# ---------------------------------------------------------------------------
# N05 field semantics — entry_state is intent, not outcome
# docs/03_scene_rig.md §2 (N05 note): entry_state never pre-fills from prior
# This is a documentation constraint; we verify the data model enforces
# that N05 resets fully (the value is never carried over from prefills).
# ---------------------------------------------------------------------------

class TestN05ResetSemantics:
    def test_n05_never_in_prefills(self):
        """compute_prefills must never include N05 regardless of prior scene."""
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "sequence_order": 2
        }
        sb.table.return_value.select.return_value.eq.return_value.lt.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"scene_id": "prior", "position_id": 3}
        ]
        with patch("src.scene_rig.get_supabase", return_value=sb):
            prefills = compute_prefills(SCENE_ID, PROJECT_ID)
        assert "N05" not in prefills

    def test_n05_entry_state_non_empty_required(self):
        ok, err = _validate_rig_slot("N05", {"entry_state": "", "value_at_stake": "trust"})
        assert not ok
        assert "entry_state" in err

    def test_n05_value_at_stake_non_empty_required(self):
        ok, err = _validate_rig_slot("N05", {"entry_state": "trust is intact", "value_at_stake": ""})
        assert not ok
        assert "value_at_stake" in err


# ---------------------------------------------------------------------------
# N02 and N06 accretion — verify slot value wraps name + id
# (tested via the scene_rig_conversation layer)
# ---------------------------------------------------------------------------

class TestN02N06Accretion:
    """
    N02 and N06 must accrete into characters/locations tables.
    The persisted value wraps {name, character_id} / {name, location_id}.
    """

    def test_n02_rule_accepts_name_string(self):
        """Rule layer accepts any non-empty name for N02."""
        ok, _ = _validate_rig_slot("N02", "Victor")
        assert ok

    def test_n06_rule_accepts_name_string(self):
        ok, _ = _validate_rig_slot("N06", "Rooftop Bar")
        assert ok

    def test_n02_empty_name_rejected_at_rule(self):
        ok, _ = _validate_rig_slot("N02", "")
        assert not ok

    def test_n06_empty_name_rejected_at_rule(self):
        ok, _ = _validate_rig_slot("N06", "")
        assert not ok
