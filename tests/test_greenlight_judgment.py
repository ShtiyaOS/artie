"""
Tests for Greenlight JUDGMENT-based slot validation.

docs/02_greenlight.md §8 — determinism map; re-ask taxonomy; three-attempt
                             escalation ladder; PROVISIONAL on non-convergence;
                             curated foreign-example library interface.
docs/04_agent_roster.md §3 — contrast barred from psychological slots.

Acceptance criterion (Task 22):
  A JUDGMENT-dominant slot such as S02 is sent for validation and input_conf
  is updated to VALIDATED or PROVISIONAL based on the response.

These tests are unit tests of the JUDGMENT module. They do NOT make model
calls. All model interaction is patched. The tests cover:
  - JUDGMENT questions exist verbatim for every judgment-dominant slot
  - Contrast permission rules are correct
  - Non-convergence (reask_count >= 3) returns PROVISIONAL immediately
  - Slots without a JUDGMENT question return VALIDATED unconditionally
  - Model-satisfied answers return VALIDATED
  - Model-unsatisfied answers return PROVISIONAL with a reask_move
  - Model failures degrade gracefully to PROVISIONAL (fail-open)
  - Foreign-example interface returns None (library not yet written)
  - JudgmentResult fields are correct in all branches

Run with: python -m pytest tests/test_greenlight_judgment.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.greenlight_judgment import (
    JudgmentResult,
    JUDGMENT_QUESTIONS,
    _CONTRAST_ALLOWED,
    _PSYCHOLOGICAL_SLOTS,
    _get_foreign_example,
    validate_judgment,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_model_response(satisfied: bool, reask_move: str | None = None) -> MagicMock:
    """Return a mock Google GenAI response for the given judgment outcome."""
    payload = {"satisfied": satisfied, "reason": "test reason"}
    if not satisfied:
        payload["reask_move"] = reask_move or "narrow"
    response = MagicMock()
    response.text = json.dumps(payload)
    return response


def _patch_client(satisfied: bool, reask_move: str | None = None):
    """Context manager that patches the GenAI client with a fixed response."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_model_response(
        satisfied=satisfied, reask_move=reask_move
    )
    return patch("src.greenlight_judgment.Client", return_value=mock_client)


# ---------------------------------------------------------------------------
# JUDGMENT questions — verbatim contract
# docs/02_greenlight.md §8: "The JUDGMENT question is stated per slot"
# ---------------------------------------------------------------------------

class TestJudgmentQuestions:
    """JUDGMENT questions must exist for every judgment-dominant slot."""

    def test_s02_question_exists(self):
        assert "S02" in JUDGMENT_QUESTIONS
        assert JUDGMENT_QUESTIONS["S02"]

    def test_s03_question_exists(self):
        assert "S03" in JUDGMENT_QUESTIONS
        assert JUDGMENT_QUESTIONS["S03"]

    def test_s04_question_exists(self):
        assert "S04" in JUDGMENT_QUESTIONS
        assert JUDGMENT_QUESTIONS["S04"]

    def test_s08_question_exists(self):
        assert "S08" in JUDGMENT_QUESTIONS
        assert JUDGMENT_QUESTIONS["S08"]

    def test_s14_question_exists(self):
        """S14 JUDGMENT question is verbatim from docs/02_greenlight.md §3."""
        assert "S14" in JUDGMENT_QUESTIONS
        q = JUDGMENT_QUESTIONS["S14"]
        assert "distinct people" in q
        assert "distinguishable narrative functions" in q

    def test_tp1_question_exists(self):
        assert "TP1" in JUDGMENT_QUESTIONS
        assert JUDGMENT_QUESTIONS["TP1"]

    def test_pure_rule_slots_have_no_judgment_question(self):
        """S09, S13, S15 are pure-rule — no JUDGMENT question."""
        for slot_id in ("S09", "S13", "S15"):
            assert slot_id not in JUDGMENT_QUESTIONS, (
                f"{slot_id} is pure-rule and must not have a JUDGMENT question"
            )

    def test_s02_question_mentions_specific_person(self):
        """S02 question must ask about a specific person."""
        q = JUDGMENT_QUESTIONS["S02"]
        assert "specific" in q.lower()
        assert "person" in q.lower()

    def test_s03_question_mentions_active_want(self):
        """S03 question must ask about an active, specific want."""
        q = JUDGMENT_QUESTIONS["S03"]
        assert "specific" in q.lower()
        assert "want" in q.lower()

    def test_s04_question_mentions_internal_condition(self):
        """S04 question must ask about an internal condition (psychological slot)."""
        q = JUDGMENT_QUESTIONS["S04"]
        assert "internal" in q.lower()

    def test_s08_question_mentions_tangible_space(self):
        """S08 question must ask about a tangible space."""
        q = JUDGMENT_QUESTIONS["S08"]
        assert "tangible" in q.lower() or "space" in q.lower()

    def test_tp1_question_mentions_specific_event(self):
        """TP1 question must ask about a specific event."""
        q = JUDGMENT_QUESTIONS["TP1"]
        assert "specific" in q.lower()
        assert "event" in q.lower()


# ---------------------------------------------------------------------------
# Re-ask taxonomy — contrast permission rules
# docs/04_agent_roster.md §3:
#   contrast on S03 and S07 only;
#   barred from psychological slots (S04).
# ---------------------------------------------------------------------------

class TestContrastPermissions:
    def test_s03_allows_contrast(self):
        """Contrast is permitted on S03 (Protagonist Want)."""
        assert "S03" in _CONTRAST_ALLOWED

    def test_s07_allows_contrast(self):
        """Contrast is permitted on S07 (Status Quo Baseline) — non-psychological facet."""
        assert "S07" in _CONTRAST_ALLOWED

    def test_s04_is_psychological(self):
        """S04 is a psychological slot — contrast absolutely barred."""
        assert "S04" in _PSYCHOLOGICAL_SLOTS

    def test_s02_does_not_allow_contrast(self):
        """S02 is not in the contrast-allowed set."""
        assert "S02" not in _CONTRAST_ALLOWED

    def test_s08_does_not_allow_contrast(self):
        """S08 does not allow contrast."""
        assert "S08" not in _CONTRAST_ALLOWED

    def test_tp1_does_not_allow_contrast(self):
        """TP1 does not allow contrast."""
        assert "TP1" not in _CONTRAST_ALLOWED

    def test_s04_not_in_contrast_allowed(self):
        """S04 must not appear in _CONTRAST_ALLOWED even if added accidentally."""
        assert "S04" not in _CONTRAST_ALLOWED


# ---------------------------------------------------------------------------
# Attempt limit — non-convergence path
# docs/02_greenlight.md §8: "On non-convergence, accept the degraded value
# and mark the slot PROVISIONAL. Do not block."
# ---------------------------------------------------------------------------

class TestAttemptLimit:
    """reask_count >= 3 means the attempt limit is reached — return PROVISIONAL immediately."""

    @pytest.mark.parametrize("reask_count", [3, 4, 10])
    def test_attempt_limit_returns_provisional(self, reask_count):
        """Any reask_count >= 3 returns PROVISIONAL without a model call."""
        result = validate_judgment("S02", "some protagonist", reask_count)
        assert result.confidence == "PROVISIONAL"
        assert result.converged is False

    @pytest.mark.parametrize("reask_count", [3, 4])
    def test_attempt_limit_no_reask_move(self, reask_count):
        """At the attempt limit, reask_move is None — nothing more to ask."""
        result = validate_judgment("S02", "some protagonist", reask_count)
        assert result.reask_move is None

    @pytest.mark.parametrize("reask_count", [3, 4])
    def test_attempt_limit_no_model_call(self, reask_count):
        """The model is not called when the attempt limit is already reached."""
        with patch("src.greenlight_judgment.Client") as mock_client_cls:
            validate_judgment("S02", "some protagonist", reask_count)
            mock_client_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Slot with no JUDGMENT question — passes unconditionally
# ---------------------------------------------------------------------------

class TestNoJudgmentSlot:
    @pytest.mark.parametrize("slot_id", ["S09", "S13", "S15", "S05", "S06", "ZZZZ"])
    def test_slot_without_judgment_question_returns_validated(self, slot_id):
        """Slots with no JUDGMENT question are VALIDATED without a model call."""
        with patch("src.greenlight_judgment.Client") as mock_client_cls:
            result = validate_judgment(slot_id, "any value", reask_count=0)
            assert result.confidence == "VALIDATED"
            assert result.converged is True
            mock_client_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Model-satisfied path — returns VALIDATED
# docs/02_greenlight.md §8: VALIDATED when judgment is satisfied.
# ---------------------------------------------------------------------------

class TestModelSatisfied:
    @pytest.mark.parametrize("slot_id", ["S02", "S03", "S04", "S08", "TP1"])
    def test_satisfied_returns_validated(self, slot_id):
        """When the model returns satisfied=true, confidence is VALIDATED."""
        with _patch_client(satisfied=True):
            result = validate_judgment(slot_id, "a good answer", reask_count=0)
        assert result.confidence == "VALIDATED"
        assert result.converged is True
        assert result.reask_move is None

    def test_s02_satisfied_validated(self):
        """Acceptance criterion: S02 sent for validation → VALIDATED on satisfied."""
        with _patch_client(satisfied=True):
            result = validate_judgment("S02", "Marcus, a disgraced city planner", reask_count=0)
        assert result.confidence == "VALIDATED"


# ---------------------------------------------------------------------------
# Model-unsatisfied path — returns PROVISIONAL with reask_move
# docs/02_greenlight.md §8: PROVISIONAL when not yet satisfied.
# ---------------------------------------------------------------------------

class TestModelUnsatisfied:
    @pytest.mark.parametrize("slot_id", ["S02", "S03", "S04", "S08", "TP1"])
    def test_unsatisfied_returns_provisional(self, slot_id):
        """When the model returns satisfied=false, confidence is PROVISIONAL."""
        with _patch_client(satisfied=False, reask_move="narrow"):
            result = validate_judgment(slot_id, "a vague answer", reask_count=0)
        assert result.confidence == "PROVISIONAL"
        assert result.converged is False

    def test_unsatisfied_carries_reask_move(self):
        """Unsatisfied result carries the reask_move from the model."""
        with _patch_client(satisfied=False, reask_move="specify"):
            result = validate_judgment("S02", "a vague answer", reask_count=0)
        assert result.reask_move == "specify"

    def test_s02_unsatisfied_provisional(self):
        """Acceptance criterion: S02 sent for validation → PROVISIONAL on unsatisfied."""
        with _patch_client(satisfied=False, reask_move="narrow"):
            result = validate_judgment("S02", "a protagonist", reask_count=0)
        assert result.confidence == "PROVISIONAL"


# ---------------------------------------------------------------------------
# Model failure — fail open, return PROVISIONAL
# docs/02_greenlight.md §8: do not block on judgment failures.
# ---------------------------------------------------------------------------

class TestModelFailure:
    def test_model_exception_returns_provisional(self):
        """A model call exception is caught; result is PROVISIONAL (fail-open)."""
        with patch("src.greenlight_judgment.Client") as mock_client_cls:
            mock_client_cls.return_value.models.generate_content.side_effect = (
                RuntimeError("network error")
            )
            result = validate_judgment("S02", "some protagonist", reask_count=0)
        assert result.confidence == "PROVISIONAL"
        assert result.converged is False

    def test_invalid_json_returns_provisional(self):
        """A model response that is not valid JSON degrades to PROVISIONAL."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value.text = "not valid json {"
        with patch("src.greenlight_judgment.Client", return_value=mock_client):
            result = validate_judgment("S02", "some protagonist", reask_count=0)
        assert result.confidence == "PROVISIONAL"
        assert result.converged is False

    def test_model_returns_empty_string_is_provisional(self):
        """Empty model response degrades to PROVISIONAL."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value.text = ""
        with patch("src.greenlight_judgment.Client", return_value=mock_client):
            result = validate_judgment("S02", "some protagonist", reask_count=0)
        assert result.confidence == "PROVISIONAL"


# ---------------------------------------------------------------------------
# Foreign-example library interface
# docs/02_greenlight.md §8 / docs/04_agent_roster.md §3:
#   library not yet written — interface returns None.
# ---------------------------------------------------------------------------

class TestForeignExampleLibrary:
    @pytest.mark.parametrize("slot_id", ["S02", "S03", "S04", "S08", "S14", "TP1"])
    def test_no_example_available_yet(self, slot_id):
        """
        The curated foreign-example library is not yet written.
        _get_foreign_example returns None for all slots.
        """
        assert _get_foreign_example(slot_id) is None

    def test_none_for_unknown_slot(self):
        assert _get_foreign_example("ZZZZ") is None


# ---------------------------------------------------------------------------
# JudgmentResult dataclass
# ---------------------------------------------------------------------------

class TestJudgmentResult:
    def test_validated_result_is_frozen(self):
        r = JudgmentResult(confidence="VALIDATED", reask_move=None, converged=True)
        with pytest.raises(Exception):
            r.confidence = "PROVISIONAL"  # type: ignore[misc]

    def test_provisional_result_fields(self):
        r = JudgmentResult(confidence="PROVISIONAL", reask_move="narrow", converged=False)
        assert r.confidence == "PROVISIONAL"
        assert r.reask_move == "narrow"
        assert r.converged is False

    def test_validated_result_fields(self):
        r = JudgmentResult(confidence="VALIDATED", reask_move=None, converged=True)
        assert r.confidence == "VALIDATED"
        assert r.reask_move is None
        assert r.converged is True


# ---------------------------------------------------------------------------
# Escalation ladder — prompt content at each attempt
# (smoke-tests: model is called; prompt includes correct elements)
# ---------------------------------------------------------------------------

class TestEscalationLadder:
    def test_attempt_zero_calls_model(self):
        """Attempt 0 (first try) calls the model."""
        with _patch_client(satisfied=True) as p:
            validate_judgment("S02", "Marcus", reask_count=0)
            p.return_value.models.generate_content.assert_called_once()

    def test_attempt_one_calls_model(self):
        """Attempt 1 (second try) calls the model."""
        with _patch_client(satisfied=True) as p:
            validate_judgment("S02", "Marcus", reask_count=1)
            p.return_value.models.generate_content.assert_called_once()

    def test_attempt_two_calls_model(self):
        """Attempt 2 (third and final try) calls the model."""
        with _patch_client(satisfied=True) as p:
            validate_judgment("S02", "Marcus", reask_count=2)
            p.return_value.models.generate_content.assert_called_once()

    def test_attempt_three_does_not_call_model(self):
        """Attempt 3 hits the limit — model is not called."""
        with patch("src.greenlight_judgment.Client") as mock_client_cls:
            validate_judgment("S02", "Marcus", reask_count=3)
            mock_client_cls.assert_not_called()

    def test_contrast_option_in_prompt_for_s03(self):
        """S03 prompt includes contrast as a permitted move."""
        captured_prompt = {}

        def capture_call(model, contents):
            captured_prompt["text"] = contents
            return _mock_model_response(satisfied=True)

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = capture_call
        with patch("src.greenlight_judgment.Client", return_value=mock_client):
            validate_judgment("S03", "To buy back the family house", reask_count=0)

        assert "contrast" in captured_prompt.get("text", "")

    def test_contrast_not_in_prompt_for_s04(self):
        """S04 prompt does NOT include contrast (psychological slot)."""
        captured_prompt = {}

        def capture_call(model, contents):
            captured_prompt["text"] = contents
            return _mock_model_response(satisfied=True)

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = capture_call
        with patch("src.greenlight_judgment.Client", return_value=mock_client):
            validate_judgment("S04", "He cannot ask for help", reask_count=0)

        # contrast must not appear in the allowed moves list
        prompt_text = captured_prompt.get("text", "")
        # "contrast" may appear in other context; specifically the allowed-moves
        # line must not include it. We check the allowed-moves clause.
        assert ", contrast" not in prompt_text
