"""
Tests for Greenlight blueprint production.

docs/02_greenlight.md §6 — the six things that happen on commitment:
  1. Title page (Fountain block) from S13, writer of record, date.
  2. Roster seeded from S14 into characters, source='BLUEPRINT'.
  3. Arena seeded from S08 into locations, source='BLUEPRINT'.
  4. Scene 1 created in scenes, position_id=1, sequence_order=1,
     status='RIG_OPEN'.
  5. Blueprint view — twelve slots as a readable document.
  6. Commitment announced (BLUEPRINT_PRODUCED event via Confluent).

Acceptance criterion (Task 24):
  Upon commitment, a title page is viewable, roster and arena are seeded,
  and scene 1 is created with the Rig open at position X01.

All Supabase and Confluent calls are patched. No network I/O.

Run with: python -m pytest tests/test_blueprint.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call

from src.blueprint import (
    build_title_page,
    seed_roster,
    seed_arena,
    create_scene_one,
    build_blueprint_view,
    announce_commitment,
    produce_blueprint,
    _arena_name,
    _parse_list,
)
from src.greenlight import REQUIRED_SLOTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sb(*, existing_scene=None, insert_scene_id="scene-uuid-001"):
    """Return a mock Supabase client."""
    sb = MagicMock()

    # characters upsert
    sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()

    # locations upsert
    # (same mock chain)

    # scenes — select existing
    existing_data = [{"scene_id": existing_scene}] if existing_scene else []
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = (
        existing_data
    )

    # scenes — insert
    sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"scene_id": insert_scene_id}
    ]

    return sb


def _all_slots(title="My Great Film", arena_value=None, s14_value=None):
    """Return a minimal slots dict covering all 12 required slots."""
    arena = arena_value or json.dumps({"name": "Downtown Los Angeles"})
    s14 = s14_value or json.dumps([
        {"name": "Alice", "role": "PROTAGONIST", "description": "The hero"},
        {"name": "Bob", "role": "ANTAGONIST", "description": "The villain"},
    ])
    slots = {}
    for sid in REQUIRED_SLOTS:
        slots[sid] = {"is_filled": True, "input_conf": "VALIDATED", "value": "placeholder"}
    slots["S13"] = {"is_filled": True, "input_conf": "VALIDATED", "value": title}
    slots["S08"] = {"is_filled": True, "input_conf": "VALIDATED", "value": arena}
    slots["S14"] = {"is_filled": True, "input_conf": "VALIDATED", "value": s14}
    return slots


# ===========================================================================
# 1. build_title_page
# ===========================================================================

class TestBuildTitlePage:
    def test_contains_title(self):
        page = build_title_page(title="Fade In", writer_name="Jane Doe")
        assert "Fade In" in page

    def test_contains_writer_name(self):
        page = build_title_page(title="Fade In", writer_name="Jane Doe")
        assert "Jane Doe" in page

    def test_contains_date_when_supplied(self):
        page = build_title_page(title="T", writer_name="W", written_date="2025-01-15")
        assert "2025-01-15" in page

    def test_uses_today_when_date_omitted(self):
        from datetime import date
        page = build_title_page(title="T", writer_name="W")
        assert date.today().isoformat() in page

    def test_fountain_title_key(self):
        page = build_title_page(title="My Film", writer_name="Jane")
        assert page.startswith("Title:")

    def test_fountain_credit_key(self):
        page = build_title_page(title="T", writer_name="W")
        assert "Credit:" in page

    def test_fountain_author_key(self):
        page = build_title_page(title="T", writer_name="Writer Person")
        assert "Author:" in page
        assert "Writer Person" in page

    def test_fountain_draft_date_key(self):
        page = build_title_page(title="T", writer_name="W", written_date="2025-06-01")
        assert "Draft date:" in page

    def test_untitled_allowed(self):
        page = build_title_page(title="Untitled", writer_name="Unknown")
        assert "Untitled" in page


# ===========================================================================
# 2. seed_roster
# ===========================================================================

class TestSeedRoster:
    def _upsert_call_args(self, sb):
        """Return (args, kwargs) of the upsert call on the characters table."""
        # The call is: sb.table("characters").upsert(rows, ...).execute()
        # We check the upsert was called with rows.
        return sb.table.return_value.upsert.call_args

    def test_upserts_characters(self):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        s14 = json.dumps([{"name": "Alice", "role": "PROTAGONIST", "description": "Hero"}])
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_roster("proj-1", s14)
        sb.table.return_value.upsert.assert_called_once()
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"

    def test_source_is_blueprint(self):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        s14 = json.dumps([{"name": "Alice", "role": "PROTAGONIST", "description": "Hero"}])
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_roster("proj-1", s14)
        assert rows[0]["source"] == "BLUEPRINT"

    def test_multiple_characters(self):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        s14 = json.dumps([
            {"name": "Alice", "role": "PROTAGONIST", "description": "Hero"},
            {"name": "Bob", "role": "ANTAGONIST", "description": "Villain"},
        ])
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_roster("proj-1", s14)
        assert len(rows) == 2

    def test_empty_s14_skips_upsert(self):
        sb = MagicMock()
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_roster("proj-1", "[]")
        sb.table.return_value.upsert.assert_not_called()
        assert rows == []

    def test_none_value_skips_upsert(self):
        sb = MagicMock()
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_roster("proj-1", None)
        sb.table.return_value.upsert.assert_not_called()

    def test_on_conflict_ignore_duplicates(self):
        """Unique constraint on (project_id, name) must be respected."""
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        s14 = json.dumps([{"name": "Alice", "role": "PROTAGONIST", "description": ""}])
        with patch("src.blueprint.get_supabase", return_value=sb):
            seed_roster("proj-1", s14)
        call_kwargs = sb.table.return_value.upsert.call_args
        # ignore_duplicates=True tells supabase-py to use ON CONFLICT DO NOTHING
        assert call_kwargs.kwargs.get("ignore_duplicates") is True

    def test_project_id_set_on_rows(self):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        s14 = json.dumps([{"name": "Alice", "role": "PROTAGONIST", "description": ""}])
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_roster("proj-99", s14)
        assert rows[0]["project_id"] == "proj-99"

    def test_role_uppercased(self):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        s14 = json.dumps([{"name": "Alice", "role": "protagonist", "description": ""}])
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_roster("proj-1", s14)
        assert rows[0]["role"] == "PROTAGONIST"

    def test_entries_with_empty_name_skipped(self):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        s14 = json.dumps([
            {"name": "", "role": "PRINCIPAL", "description": ""},
            {"name": "Alice", "role": "PROTAGONIST", "description": "Hero"},
        ])
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_roster("proj-1", s14)
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"


# ===========================================================================
# 3. seed_arena
# ===========================================================================

class TestSeedArena:
    def test_upserts_location(self):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        s08 = json.dumps({"name": "Downtown LA"})
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_arena("proj-1", s08)
        sb.table.return_value.upsert.assert_called_once()
        assert len(rows) == 1
        assert rows[0]["name"] == "Downtown LA"

    def test_source_is_blueprint(self):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_arena("proj-1", json.dumps({"name": "Arena"}))
        assert rows[0]["source"] == "BLUEPRINT"

    def test_project_id_set(self):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_arena("proj-42", json.dumps({"name": "Place"}))
        assert rows[0]["project_id"] == "proj-42"

    def test_on_conflict_ignore_duplicates(self):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        with patch("src.blueprint.get_supabase", return_value=sb):
            seed_arena("proj-1", json.dumps({"name": "Place"}))
        call_kwargs = sb.table.return_value.upsert.call_args
        assert call_kwargs.kwargs.get("ignore_duplicates") is True

    def test_plain_string_value(self):
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_arena("proj-1", "The Mojave Desert")
        assert rows[0]["name"] == "The Mojave Desert"

    def test_setting_key_fallback(self):
        """Some S08 responses use 'setting' instead of 'name'."""
        sb = MagicMock()
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_arena("proj-1", json.dumps({"setting": "Small-town America"}))
        assert rows[0]["name"] == "Small-town America"

    def test_empty_value_skips_upsert(self):
        sb = MagicMock()
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_arena("proj-1", "")
        sb.table.return_value.upsert.assert_not_called()
        assert rows == []

    def test_none_value_skips_upsert(self):
        sb = MagicMock()
        with patch("src.blueprint.get_supabase", return_value=sb):
            rows = seed_arena("proj-1", None)
        sb.table.return_value.upsert.assert_not_called()


# ===========================================================================
# 4. create_scene_one
# ===========================================================================

class TestCreateSceneOne:
    def _make_sb_no_existing(self, insert_scene_id="scene-001"):
        sb = MagicMock()
        # select returns empty (no existing scene)
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        # insert returns the new scene
        sb.table.return_value.insert.return_value.execute.return_value.data = [
            {"scene_id": insert_scene_id}
        ]
        return sb

    def _make_sb_with_existing(self, existing_id="scene-existing"):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"scene_id": existing_id}
        ]
        return sb

    def test_inserts_scene_when_none_exists(self):
        sb = self._make_sb_no_existing("scene-new")
        with patch("src.blueprint.get_supabase", return_value=sb):
            scene_id = create_scene_one("proj-1")
        sb.table.return_value.insert.assert_called_once()
        assert scene_id == "scene-new"

    def test_position_id_is_1(self):
        sb = self._make_sb_no_existing()
        with patch("src.blueprint.get_supabase", return_value=sb):
            create_scene_one("proj-1")
        insert_call = sb.table.return_value.insert.call_args
        payload = insert_call.args[0]
        assert payload["position_id"] == 1

    def test_sequence_order_is_1(self):
        sb = self._make_sb_no_existing()
        with patch("src.blueprint.get_supabase", return_value=sb):
            create_scene_one("proj-1")
        insert_call = sb.table.return_value.insert.call_args
        payload = insert_call.args[0]
        assert payload["sequence_order"] == 1

    def test_status_is_rig_open(self):
        sb = self._make_sb_no_existing()
        with patch("src.blueprint.get_supabase", return_value=sb):
            create_scene_one("proj-1")
        insert_call = sb.table.return_value.insert.call_args
        payload = insert_call.args[0]
        assert payload["status"] == "RIG_OPEN"

    def test_project_id_on_insert(self):
        sb = self._make_sb_no_existing()
        with patch("src.blueprint.get_supabase", return_value=sb):
            create_scene_one("proj-99")
        insert_call = sb.table.return_value.insert.call_args
        payload = insert_call.args[0]
        assert payload["project_id"] == "proj-99"

    def test_returns_scene_id(self):
        sb = self._make_sb_no_existing("scene-xyz")
        with patch("src.blueprint.get_supabase", return_value=sb):
            result = create_scene_one("proj-1")
        assert result == "scene-xyz"

    def test_idempotent_when_scene_exists(self):
        """If scene 1 already exists, no insert is made."""
        sb = self._make_sb_with_existing("scene-existing")
        with patch("src.blueprint.get_supabase", return_value=sb):
            result = create_scene_one("proj-1")
        sb.table.return_value.insert.assert_not_called()
        assert result == "scene-existing"


# ===========================================================================
# 5. build_blueprint_view
# ===========================================================================

class TestBuildBlueprintView:
    def test_contains_all_12_required_slot_ids(self):
        slots = _all_slots()
        view = build_blueprint_view(slots)
        for sid in REQUIRED_SLOTS:
            assert sid in view, f"Missing slot {sid} in blueprint view"

    def test_starts_with_blueprint_heading(self):
        view = build_blueprint_view(_all_slots())
        assert "Blueprint" in view

    def test_provisional_slots_marked(self):
        slots = _all_slots()
        slots["S13"]["input_conf"] = "PROVISIONAL"
        view = build_blueprint_view(slots)
        assert "provisional" in view.lower()

    def test_validated_slots_not_marked_provisional(self):
        slots = _all_slots()
        view = build_blueprint_view(slots)
        # S13 is VALIDATED — should not show provisional marker next to it
        # (other slots may be provisional, but S13 here is VALIDATED)
        lines = view.split("\n")
        s13_line = next((l for l in lines if "S13" in l), "")
        assert "provisional" not in s13_line.lower()

    def test_optional_slots_excluded(self):
        """S11 and TP1 are optional; they should not appear in the blueprint view."""
        slots = _all_slots()
        slots["S11"] = {"is_filled": True, "input_conf": "VALIDATED", "value": "Some rule"}
        view = build_blueprint_view(slots)
        # S11 and TP1 are optional; build_blueprint_view only shows required slots
        assert "S11" not in view
        assert "TP1" not in view

    def test_slot_labels_present(self):
        view = build_blueprint_view(_all_slots())
        assert "Working Title" in view
        assert "Protagonist" in view
        assert "Arena" in view

    def test_title_value_present(self):
        slots = _all_slots(title="Midnight Express")
        view = build_blueprint_view(slots)
        assert "Midnight Express" in view


# ===========================================================================
# 6. announce_commitment
# ===========================================================================

class TestAnnounceCommitment:
    def test_emits_blueprint_produced_event(self):
        with patch("src.blueprint.publish_event") as pub:
            announce_commitment(
                "proj-1",
                title="Test Film",
                scene_id="scene-001",
                character_count=2,
                location_count=1,
            )
        pub.assert_called_once()
        _, kwargs = pub.call_args
        assert kwargs["event_type"] == "BLUEPRINT_PRODUCED"

    def test_actor_is_system(self):
        with patch("src.blueprint.publish_event") as pub:
            announce_commitment("proj-1", title="T", scene_id=None,
                                character_count=0, location_count=0)
        _, kwargs = pub.call_args
        assert kwargs["actor"] == "system"

    def test_payload_contains_title(self):
        with patch("src.blueprint.publish_event") as pub:
            announce_commitment("proj-1", title="My Film", scene_id="s1",
                                character_count=3, location_count=1)
        _, kwargs = pub.call_args
        assert kwargs["payload"]["title"] == "My Film"

    def test_payload_contains_scene_1_id(self):
        with patch("src.blueprint.publish_event") as pub:
            announce_commitment("proj-1", title="T", scene_id="scene-abc",
                                character_count=1, location_count=1)
        _, kwargs = pub.call_args
        assert kwargs["payload"]["scene_1_id"] == "scene-abc"

    def test_payload_contains_character_count(self):
        with patch("src.blueprint.publish_event") as pub:
            announce_commitment("proj-1", title="T", scene_id=None,
                                character_count=5, location_count=1)
        _, kwargs = pub.call_args
        assert kwargs["payload"]["character_count"] == 5

    def test_payload_contains_location_count(self):
        with patch("src.blueprint.publish_event") as pub:
            announce_commitment("proj-1", title="T", scene_id=None,
                                character_count=0, location_count=2)
        _, kwargs = pub.call_args
        assert kwargs["payload"]["location_count"] == 2

    def test_project_id_passed(self):
        with patch("src.blueprint.publish_event") as pub:
            announce_commitment("proj-xyz", title="T", scene_id=None,
                                character_count=0, location_count=0)
        _, kwargs = pub.call_args
        assert kwargs["project_id"] == "proj-xyz"


# ===========================================================================
# 7. produce_blueprint — integration of all six steps
# ===========================================================================

class TestProduceBlueprint:
    """
    Tests the orchestrator.  Each sub-component is already unit-tested above.
    Here we verify that all six steps are called and the return dict is correct.
    """

    def _run(self, *, title="Fade In", project_id="proj-1", writer_name="Jane Doe"):
        """Patch everything; run produce_blueprint; return result."""
        slots = _all_slots(title=title)

        sb = MagicMock()
        # load_bible_slots select
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"slot_id": sid, "value": row["value"],
             "is_filled": True, "input_conf": "VALIDATED"}
            for sid, row in slots.items()
        ]
        # scene select (no existing)
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        # scene insert
        sb.table.return_value.insert.return_value.execute.return_value.data = [
            {"scene_id": "scene-001"}
        ]
        # upserts
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()

        with patch("src.blueprint.get_supabase", return_value=sb), \
             patch("src.greenlight.get_supabase", return_value=sb), \
             patch("src.blueprint.publish_event") as pub:
            result = produce_blueprint(project_id, writer_name=writer_name)
        return result, sb, pub

    def test_returns_title_page(self):
        result, _, _ = self._run(title="My Film")
        assert "title_page" in result
        assert "My Film" in result["title_page"]

    def test_title_page_is_fountain_block(self):
        result, _, _ = self._run(title="My Film")
        assert result["title_page"].startswith("Title:")

    def test_returns_blueprint_view(self):
        result, _, _ = self._run()
        assert "blueprint_view" in result
        assert "Blueprint" in result["blueprint_view"]

    def test_returns_scene_1_id(self):
        result, _, _ = self._run()
        assert "scene_1_id" in result

    def test_returns_characters_list(self):
        result, _, _ = self._run()
        assert "characters" in result
        assert isinstance(result["characters"], list)

    def test_returns_locations_list(self):
        result, _, _ = self._run()
        assert "locations" in result
        assert isinstance(result["locations"], list)

    def test_blueprint_produced_event_emitted(self):
        _, _, pub = self._run()
        pub.assert_called_once()
        _, kwargs = pub.call_args
        assert kwargs["event_type"] == "BLUEPRINT_PRODUCED"

    def test_writer_name_appears_in_title_page(self):
        result, _, _ = self._run(writer_name="Jane Doe")
        assert "Jane Doe" in result["title_page"]


# ===========================================================================
# 8. Internal helpers
# ===========================================================================

class TestArenaName:
    def test_plain_string(self):
        assert _arena_name("Small town") == "Small town"

    def test_json_string_with_name(self):
        assert _arena_name(json.dumps({"name": "LA"})) == "LA"

    def test_dict_with_name(self):
        assert _arena_name({"name": "Paris"}) == "Paris"

    def test_dict_with_setting(self):
        assert _arena_name({"setting": "The suburbs"}) == "The suburbs"

    def test_dict_with_location(self):
        assert _arena_name({"location": "Chicago"}) == "Chicago"

    def test_dict_with_arena(self):
        assert _arena_name({"arena": "The dojo"}) == "The dojo"

    def test_none_returns_empty(self):
        assert _arena_name(None) == ""

    def test_empty_string_returns_empty(self):
        assert _arena_name("") == ""

    def test_truncates_to_200_chars(self):
        long = "A" * 300
        assert len(_arena_name(long)) <= 200


class TestParseList:
    def test_parses_json_string(self):
        items = _parse_list(json.dumps([{"name": "Alice"}]))
        assert items == [{"name": "Alice"}]

    def test_passes_through_list(self):
        items = _parse_list([{"name": "Alice"}])
        assert items == [{"name": "Alice"}]

    def test_empty_list(self):
        assert _parse_list([]) == []

    def test_empty_json_list(self):
        assert _parse_list("[]") == []

    def test_none_returns_empty(self):
        assert _parse_list(None) == []

    def test_non_dict_items_filtered(self):
        items = _parse_list([{"name": "Alice"}, "not a dict", 42])
        assert items == [{"name": "Alice"}]
