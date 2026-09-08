"""
Tests for Greenlight RULE-based slot validation.

docs/02_greenlight.md §3 — S09 Genre, S13 Working Title, S15 Target Scene Count
docs/02_greenlight.md §8 — determinism map

Acceptance criterion (Task 21):
  Pure-rule slots are validated according to their specified rules.
  Example: S15 accepts an integer between 20 and 200.

Run with: python -m pytest tests/test_greenlight_rules.py -v
"""

import pytest

from src.greenlight_rules import validate_slot, GENRE_VALUES, RuleResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(result: RuleResult) -> None:
    assert result.ok, f"Expected OK but got error: {result.error}"


def _fail(result: RuleResult) -> None:
    assert not result.ok, "Expected failure but got OK"
    assert result.error, "Failure result must carry an error message"


# ---------------------------------------------------------------------------
# S09 Genre — enum membership (pure rule, no JUDGMENT)
# docs/02_greenlight.md §8
# ---------------------------------------------------------------------------

class TestS09Genre:
    def test_valid_genre_passes(self):
        _ok(validate_slot("S09", "Drama"))

    def test_every_valid_genre_passes(self):
        for genre in GENRE_VALUES:
            result = validate_slot("S09", genre)
            assert result.ok, f"Genre '{genre}' should pass but got: {result.error}"

    def test_unknown_genre_fails(self):
        _fail(validate_slot("S09", "Anime"))

    def test_empty_string_fails(self):
        _fail(validate_slot("S09", ""))

    def test_whitespace_only_fails(self):
        _fail(validate_slot("S09", "   "))

    def test_none_fails(self):
        _fail(validate_slot("S09", None))

    def test_integer_fails(self):
        _fail(validate_slot("S09", 42))

    def test_case_sensitive(self):
        """Genre enum is case-sensitive — 'drama' is not 'Drama'."""
        _fail(validate_slot("S09", "drama"))

    def test_error_message_contains_genre_value(self):
        result = validate_slot("S09", "Telenovela")
        assert "Telenovela" in result.error

    def test_error_message_lists_allowed(self):
        result = validate_slot("S09", "NotAGenre")
        assert "Drama" in result.error   # one of the allowed values appears


# ---------------------------------------------------------------------------
# S13 Working Title — non-empty; ≤ 15 words (pure rule, no JUDGMENT)
# docs/02_greenlight.md §3
# ---------------------------------------------------------------------------

class TestS13WorkingTitle:
    def test_single_word_passes(self):
        _ok(validate_slot("S13", "Untitled"))

    def test_exactly_15_words_passes(self):
        title = " ".join(["Word"] * 15)
        _ok(validate_slot("S13", title))

    def test_14_words_passes(self):
        title = " ".join(["Word"] * 14)
        _ok(validate_slot("S13", title))

    def test_16_words_fails(self):
        title = " ".join(["Word"] * 16)
        _fail(validate_slot("S13", title))

    def test_empty_string_fails(self):
        _fail(validate_slot("S13", ""))

    def test_whitespace_only_fails(self):
        _fail(validate_slot("S13", "   "))

    def test_none_fails(self):
        _fail(validate_slot("S13", None))

    def test_integer_fails(self):
        _fail(validate_slot("S13", 0))

    def test_error_message_contains_word_count(self):
        title = " ".join(["Word"] * 20)
        result = validate_slot("S13", title)
        assert "20" in result.error

    def test_legitimate_title_passes(self):
        _ok(validate_slot("S13", "The Quiet Man in the Corner of the Room"))

    def test_single_letter_passes(self):
        _ok(validate_slot("S13", "X"))


# ---------------------------------------------------------------------------
# S15 Target Scene Count — integer, 20 ≤ n ≤ 200 (pure rule, no JUDGMENT)
# docs/02_greenlight.md §3
# ---------------------------------------------------------------------------

class TestS15TargetSceneCount:
    # --- Boundary passing ---

    def test_lower_bound_passes(self):
        _ok(validate_slot("S15", 20))

    def test_upper_bound_passes(self):
        _ok(validate_slot("S15", 200))

    def test_midrange_passes(self):
        _ok(validate_slot("S15", 90))

    def test_string_integer_passes(self):
        """Artie may return a number as a JSON string."""
        _ok(validate_slot("S15", "60"))

    def test_float_whole_number_passes(self):
        """JSON sometimes delivers integers as floats."""
        _ok(validate_slot("S15", 60.0))

    # --- Boundary failing ---

    def test_below_lower_bound_fails(self):
        _fail(validate_slot("S15", 19))

    def test_above_upper_bound_fails(self):
        _fail(validate_slot("S15", 201))

    def test_zero_fails(self):
        _fail(validate_slot("S15", 0))

    def test_negative_fails(self):
        _fail(validate_slot("S15", -1))

    # --- Type failures ---

    def test_float_non_integer_fails(self):
        _fail(validate_slot("S15", 60.5))

    def test_string_float_fails(self):
        _fail(validate_slot("S15", "60.5"))

    def test_none_fails(self):
        _fail(validate_slot("S15", None))

    def test_bool_fails(self):
        """bool is a subclass of int in Python; must be rejected."""
        _fail(validate_slot("S15", True))

    def test_string_non_integer_fails(self):
        _fail(validate_slot("S15", "sixty"))

    def test_list_fails(self):
        _fail(validate_slot("S15", [60]))

    # --- Error message quality ---

    def test_error_message_below_contains_value(self):
        result = validate_slot("S15", 5)
        assert "5" in result.error

    def test_error_message_above_contains_value(self):
        result = validate_slot("S15", 250)
        assert "250" in result.error


# ---------------------------------------------------------------------------
# S14 Principal Characters — structural rule gate
# docs/02_greenlight.md §3
# ---------------------------------------------------------------------------

class TestS14PrincipalCharacters:
    def _entry(self, name="Alice", role="PROTAGONIST", description="Leads the story"):
        return {"name": name, "role": role, "description": description}

    def test_single_valid_entry_passes(self):
        _ok(validate_slot("S14", [self._entry()]))

    def test_two_entries_passes(self):
        entries = [
            self._entry("Alice", "PROTAGONIST", "Leads"),
            self._entry("Bob", "ANTAGONIST", "Opposes"),
        ]
        _ok(validate_slot("S14", entries))

    def test_eight_entries_passes(self):
        entries = [
            self._entry(f"Char{i}", "PRINCIPAL", f"Role {i}")
            for i in range(7)
        ]
        entries.insert(0, self._entry())
        assert len(entries) == 8
        _ok(validate_slot("S14", entries))

    def test_nine_entries_fails(self):
        entries = [
            self._entry(f"Char{i}", "PRINCIPAL", f"Role {i}")
            for i in range(9)
        ]
        _fail(validate_slot("S14", entries))

    def test_empty_list_fails(self):
        _fail(validate_slot("S14", []))

    def test_missing_name_fails(self):
        entry = {"role": "PROTAGONIST", "description": "Leads"}
        _fail(validate_slot("S14", [entry]))

    def test_empty_name_fails(self):
        entry = self._entry(name="")
        _fail(validate_slot("S14", [entry]))

    def test_invalid_role_fails(self):
        entry = self._entry(role="HERO")
        _fail(validate_slot("S14", [entry]))

    def test_missing_description_fails(self):
        entry = {"name": "Alice", "role": "PROTAGONIST"}
        _fail(validate_slot("S14", [entry]))

    def test_json_string_input_passes(self):
        """S14 value may arrive as a JSON-serialised string."""
        import json
        entries = [self._entry()]
        _ok(validate_slot("S14", json.dumps(entries)))

    def test_not_a_list_fails(self):
        _fail(validate_slot("S14", {"name": "Alice", "role": "PROTAGONIST", "description": "x"}))


# ---------------------------------------------------------------------------
# Slots with no rule entry — pass unconditionally
# (Judgment-dominant: S02, S03, S04, S08, TP1)
# ---------------------------------------------------------------------------

class TestNoRuleSlots:
    @pytest.mark.parametrize("slot_id", ["S02", "S03", "S04", "S08", "TP1"])
    def test_judgment_dominant_slots_always_pass(self, slot_id):
        _ok(validate_slot(slot_id, "any value"))

    @pytest.mark.parametrize("slot_id", ["S02", "S03", "S04", "S08", "TP1"])
    def test_judgment_dominant_slots_pass_none(self, slot_id):
        _ok(validate_slot(slot_id, None))

    def test_unknown_slot_passes(self):
        _ok(validate_slot("ZZZZ", "some value"))


# ---------------------------------------------------------------------------
# S05 Antagonism — structural gate: must have non-empty locus
# ---------------------------------------------------------------------------

class TestS05Antagonism:
    def test_valid_dict_passes(self):
        _ok(validate_slot("S05", {"locus": "AGENT", "agent_name": "Victor"}))

    def test_systemic_locus_passes(self):
        _ok(validate_slot("S05", {"locus": "SYSTEMIC"}))

    def test_missing_locus_fails(self):
        _fail(validate_slot("S05", {"agent_name": "Victor"}))

    def test_empty_locus_fails(self):
        _fail(validate_slot("S05", {"locus": ""}))

    def test_not_a_dict_fails(self):
        _fail(validate_slot("S05", "AGENT"))

    def test_json_string_dict_passes(self):
        import json
        _ok(validate_slot("S05", json.dumps({"locus": "AGENT"})))
