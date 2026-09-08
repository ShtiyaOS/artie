"""
Tests for the Artie prose firewall.

docs/05_orchestration.md §6 — assert_no_prose must raise on every
forbidden key, at any nesting depth, never sanitize.

Run with: python -m pytest tests/test_firewall.py -v
"""

import pytest

from src.agents.firewall import (
    FORBIDDEN_KEYS,
    FirewallBreach,
    assert_no_prose,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _clean_payload() -> dict:
    """A valid Backend → Artie payload with no prose fields."""
    return {
        "project_id": "00000000-0000-0000-0000-000000000001",
        "gate": "GREENLIGHT",
        "bible_slots": {"S02": "A grieving father finds purpose"},
        "rig_slots": {},
        "pending_findings": [],
        "canon_findings": [],
        "coverage_summary": {"total": 6, "satisfied": 4, "gap": 2},
        "user_message": "What should I work on next?",
    }


# ---------------------------------------------------------------------------
# Clean payload — must not raise
# ---------------------------------------------------------------------------

def test_clean_payload_passes():
    """A payload with no forbidden keys must not raise."""
    assert_no_prose(_clean_payload())


# ---------------------------------------------------------------------------
# Every forbidden key at top level
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(FORBIDDEN_KEYS))
def test_top_level_forbidden_key_raises(key):
    """Each forbidden key at the top level raises FirewallBreach."""
    payload = _clean_payload()
    payload[key] = "some value"
    with pytest.raises(FirewallBreach) as exc_info:
        assert_no_prose(payload)
    assert key in str(exc_info.value)


# ---------------------------------------------------------------------------
# Forbidden key inside a nested dict
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(FORBIDDEN_KEYS))
def test_nested_dict_forbidden_key_raises(key):
    """Forbidden key one level deep raises and names the dotted path."""
    payload = _clean_payload()
    payload["context"] = {key: "nested prose"}
    with pytest.raises(FirewallBreach) as exc_info:
        assert_no_prose(payload)
    assert f"context.{key}" in str(exc_info.value)


def test_deeply_nested_dict_raises():
    """Forbidden key three levels deep raises with the full dotted path."""
    payload = _clean_payload()
    payload["a"] = {"b": {"scene_text": "INT. OFFICE - DAY"}}
    with pytest.raises(FirewallBreach) as exc_info:
        assert_no_prose(payload)
    assert "a.b.scene_text" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Forbidden key inside a dict that is an element of a list
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(FORBIDDEN_KEYS))
def test_list_of_dicts_forbidden_key_raises(key):
    """Forbidden key inside a list-of-dicts raises and names the indexed path."""
    payload = _clean_payload()
    payload["pending_findings"] = [
        {"cell_id": "X06.Y1", "verdict": "GAP"},
        {"cell_id": "X06.Y2", key: "some prose"},
    ]
    with pytest.raises(FirewallBreach) as exc_info:
        assert_no_prose(payload)
    assert f"pending_findings[1].{key}" in str(exc_info.value)


def test_list_first_element_raises_correct_index():
    """Index in the error message is 0 when the first element is the violation."""
    payload = _clean_payload()
    payload["items"] = [{"evidence": "span reference"}]
    with pytest.raises(FirewallBreach) as exc_info:
        assert_no_prose(payload)
    assert "items[0].evidence" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Guard raises, never sanitizes
# ---------------------------------------------------------------------------

def test_raises_not_returns_false():
    """The guard raises — it does not return a boolean or None on failure."""
    payload = {"scene_text": "INT. OFFICE - DAY"}
    with pytest.raises(FirewallBreach):
        assert_no_prose(payload)


def test_no_modification_on_clean_payload():
    """assert_no_prose does not mutate the payload it inspects."""
    payload = _clean_payload()
    original_keys = set(payload.keys())
    assert_no_prose(payload)
    assert set(payload.keys()) == original_keys


# ---------------------------------------------------------------------------
# Non-dict list elements are ignored (strings, ints — not walkable)
# ---------------------------------------------------------------------------

def test_list_of_strings_does_not_raise():
    """A list of strings is not walked — no false positives."""
    payload = _clean_payload()
    # The string values themselves may contain forbidden words; only keys matter
    payload["notes"] = ["scene_text is a key name", "this is fine"]
    assert_no_prose(payload)


def test_list_of_mixed_types_walks_only_dicts():
    """Ints and strings in a list are skipped; dicts in the same list are walked."""
    payload = _clean_payload()
    payload["mixed"] = [1, "two", {"safe_key": "value"}]
    assert_no_prose(payload)  # no forbidden key in the dict


def test_list_of_mixed_types_catches_dict_violation():
    payload = _clean_payload()
    payload["mixed"] = [1, "two", {"dialogue": "Hello there"}]
    with pytest.raises(FirewallBreach) as exc_info:
        assert_no_prose(payload)
    assert "mixed[2].dialogue" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Error message quality
# ---------------------------------------------------------------------------

def test_error_message_names_path():
    """FirewallBreach message always contains the full dotted path."""
    payload = {"wrapper": {"inner": {"script": "fade in"}}}
    with pytest.raises(FirewallBreach) as exc_info:
        assert_no_prose(payload)
    msg = str(exc_info.value)
    assert "wrapper.inner.script" in msg


def test_error_message_contains_artie():
    """Message is clearly addressed at the Artie boundary."""
    with pytest.raises(FirewallBreach) as exc_info:
        assert_no_prose({"prose": "text"})
    assert "Artie" in str(exc_info.value)
