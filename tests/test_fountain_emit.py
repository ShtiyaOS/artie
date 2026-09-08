"""
Tests for src/fountain/emit.py — docs/14_editor.md §2.

Verifies that each component type emits the correct Fountain forcing character
and that multi-component assembly produces a well-formed document.
"""

import pytest

from src.fountain.emit import emit_component, emit_fountain


# ---------------------------------------------------------------------------
# emit_component — individual type tests
# ---------------------------------------------------------------------------

class TestEmitComponent:
    def test_scene_heading_forcing_char(self):
        result = emit_component("SCENE_HEADING", "INT. DINER - NIGHT")
        assert result == ".INT. DINER - NIGHT"

    def test_action_forcing_char(self):
        result = emit_component("ACTION", "She walks in.")
        assert result == "!She walks in."

    def test_character_forcing_char(self):
        result = emit_component("CHARACTER", "MARLA")
        assert result == "@MARLA"

    def test_dialogue_no_forcing_char(self):
        """Dialogue has no forcing character — plain text."""
        result = emit_component("DIALOGUE", "You don't own me.")
        assert result == "You don't own me."

    def test_parenthetical_adds_parens(self):
        result = emit_component("PARENTHETICAL", "quietly")
        assert result == "(quietly)"

    def test_parenthetical_preserves_existing_parens(self):
        result = emit_component("PARENTHETICAL", "(already wrapped)")
        assert result == "(already wrapped)"

    def test_transition_forcing_char(self):
        result = emit_component("TRANSITION", "CUT TO:")
        assert result == ">CUT TO:"

    def test_note_double_brackets(self):
        result = emit_component("NOTE", "remind myself about this scene")
        assert result == "[[remind myself about this scene]]"

    def test_note_preserves_existing_brackets(self):
        result = emit_component("NOTE", "[[already bracketed]]")
        assert result == "[[already bracketed]]"

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            emit_component("MONOLOGUE", "text")

    def test_empty_action(self):
        result = emit_component("ACTION", "")
        assert result == "!"

    def test_empty_scene_heading(self):
        result = emit_component("SCENE_HEADING", "")
        assert result == "."

    def test_empty_character(self):
        result = emit_component("CHARACTER", "")
        assert result == "@"


# ---------------------------------------------------------------------------
# emit_fountain — multi-component assembly
# ---------------------------------------------------------------------------

class TestEmitFountain:
    def _make(self, comp_type, content, seq=1):
        return {"comp_type": comp_type, "content": content, "sequence_order": seq}

    def test_single_action(self):
        comps = [self._make("ACTION", "She enters.")]
        result = emit_fountain(comps)
        assert result == "!She enters."

    def test_blank_line_before_scene_heading(self):
        comps = [
            self._make("ACTION", "Rain falls.", 1),
            self._make("SCENE_HEADING", "INT. DINER - NIGHT", 2),
        ]
        result = emit_fountain(comps)
        lines = result.split("\n")
        assert lines[0] == "!Rain falls."
        assert lines[1] == ""            # blank separator
        assert lines[2] == ".INT. DINER - NIGHT"

    def test_no_blank_before_dialogue(self):
        comps = [
            self._make("CHARACTER", "MARLA", 1),
            self._make("DIALOGUE", "You don't own me.", 2),
        ]
        result = emit_fountain(comps)
        lines = result.split("\n")
        assert lines[0] == "@MARLA"
        assert lines[1] == "You don't own me."  # no blank line between

    def test_no_blank_before_parenthetical(self):
        comps = [
            self._make("DIALOGUE", "You said—", 1),
            self._make("PARENTHETICAL", "low, controlled", 2),
        ]
        result = emit_fountain(comps)
        lines = result.split("\n")
        assert lines[0] == "You said—"
        assert lines[1] == "(low, controlled)"

    def test_note_excluded_from_non_empty_output(self):
        """Note content is wrapped; confirm the [[]] syntax is used."""
        comps = [self._make("NOTE", "reminder for later")]
        result = emit_fountain(comps)
        assert result == "[[reminder for later]]"

    def test_full_exchange(self):
        comps = [
            {"comp_type": "SCENE_HEADING", "content": "INT. DINER - NIGHT", "sequence_order": 1},
            {"comp_type": "ACTION",        "content": "Marla enters.",       "sequence_order": 2},
            {"comp_type": "CHARACTER",     "content": "MARLA",               "sequence_order": 3},
            {"comp_type": "DIALOGUE",      "content": "You don't own me.",   "sequence_order": 4},
            {"comp_type": "CHARACTER",     "content": "TYLER",               "sequence_order": 5},
            {"comp_type": "PARENTHETICAL", "content": "quietly",             "sequence_order": 6},
            {"comp_type": "DIALOGUE",      "content": "I know.",             "sequence_order": 7},
            {"comp_type": "TRANSITION",    "content": "CUT TO:",             "sequence_order": 8},
        ]
        result = emit_fountain(comps)
        lines = result.split("\n")

        # Scene heading is first — no blank line before it.
        assert lines[0] == ".INT. DINER - NIGHT"
        # Blank before ACTION
        assert lines[1] == ""
        assert lines[2] == "!Marla enters."
        # Blank before CHARACTER
        assert lines[3] == ""
        assert lines[4] == "@MARLA"
        # Dialogue glues directly
        assert lines[5] == "You don't own me."
        # Blank before second CHARACTER
        assert lines[6] == ""
        assert lines[7] == "@TYLER"
        # Parenthetical glues
        assert lines[8] == "(quietly)"
        # Dialogue glues
        assert lines[9] == "I know."
        # Blank before TRANSITION
        assert lines[10] == ""
        assert lines[11] == ">CUT TO:"

    def test_empty_components_list(self):
        result = emit_fountain([])
        assert result == ""

    def test_unix_line_endings(self):
        """emit_fountain must use LF, never CRLF."""
        comps = [
            {"comp_type": "ACTION", "content": "Line one.", "sequence_order": 1},
            {"comp_type": "ACTION", "content": "Line two.", "sequence_order": 2},
        ]
        result = emit_fountain(comps)
        assert "\r" not in result
