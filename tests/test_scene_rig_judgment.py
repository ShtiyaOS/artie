"""
Tests for Scene Rig asynchronous JUDGMENT validation.

docs/03_scene_rig.md §3  — JUDGMENT questions verbatim per slot
docs/03_scene_rig.md §4  — JUDGMENT runs after writer enters drafting surface;
                             slot failing async judgment is marked PROVISIONAL.
docs/05_orchestration.md §8 — SLOT_JUDGMENT_FAILED enters per-project queue.

Acceptance criterion (Task 27):
    After the writer proceeds to the editor, a failed JUDGMENT check on a
    Rig slot enqueues a SLOT_JUDGMENT_FAILED item in the agent_queue table.

These tests are unit tests. All model calls and Supabase/Confluent I/O are
patched. No network I/O.

Run with: python -m pytest tests/test_scene_rig_judgment.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call

from src.scene_rig_judgment import (
    RIG_JUDGMENT_QUESTIONS,
    JUDGMENT_SLOT_IDS,
    run_rig_judgment,
    _evaluate_slot,
    _mark_provisional,
    _enqueue_judgment_failed,
    _call_judgment,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SCENE_ID   = "scene-0001"
PROJECT_ID = "proj-0001"


def _mock_satisfied_response() -> MagicMock:
    resp = MagicMock()
    resp.text = json.dumps({"satisfied": True, "reason": "Clear and specific"})
    return resp


def _mock_unsatisfied_response() -> MagicMock:
    resp = MagicMock()
    resp.text = json.dumps({"satisfied": False, "reason": "Too vague"})
    return resp


def _patch_model(satisfied: bool):
    """Patch the GenAI client to return a fixed judgment outcome."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = (
        _mock_satisfied_response() if satisfied else _mock_unsatisfied_response()
    )
    return patch("src.scene_rig_judgment.Client", return_value=mock_client)


def _sb_mock() -> MagicMock:
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock()
    return sb


def _slots_all_filled() -> dict[str, dict]:
    return {
        "N01": {"is_filled": True, "value": "X03"},
        "N02": {"is_filled": True, "value": json.dumps({"name": "Alice", "character_id": "c-1"})},
        "N03": {"is_filled": True, "value": "Secure a confession before the hearing"},
        "N04": {"is_filled": True, "value": json.dumps({"locus": "AGENT", "text": "The suspect refuses"})},
        "N05": {"is_filled": True, "value": json.dumps({"entry_state": "Partners aligned", "value_at_stake": "The partnership"})},
        "N06": {"is_filled": True, "value": json.dumps({"name": "Police precinct", "location_id": "l-1"})},
        "N07": {"is_filled": True, "value": "Hearing begins in two hours"},
    }


# ---------------------------------------------------------------------------
# JUDGMENT questions — verbatim contract
# docs/03_scene_rig.md §3
# ---------------------------------------------------------------------------

class TestRigJudgmentQuestions:
    """JUDGMENT questions must exist and match doc verbatim for every judged slot."""

    def test_n01_has_no_judgment_question(self):
        """N01 is pure-rule — no JUDGMENT question."""
        assert "N01" not in RIG_JUDGMENT_QUESTIONS

    def test_n02_question_exists(self):
        assert "N02" in RIG_JUDGMENT_QUESTIONS
        assert RIG_JUDGMENT_QUESTIONS["N02"]

    def test_n03_question_exists(self):
        assert "N03" in RIG_JUDGMENT_QUESTIONS
        assert RIG_JUDGMENT_QUESTIONS["N03"]

    def test_n04_question_exists(self):
        assert "N04" in RIG_JUDGMENT_QUESTIONS
        assert RIG_JUDGMENT_QUESTIONS["N04"]

    def test_n05_has_two_questions(self):
        """N05 has two JUDGMENT questions (docs/03_scene_rig.md §3)."""
        q = RIG_JUDGMENT_QUESTIONS["N05"]
        assert isinstance(q, list)
        assert len(q) == 2

    def test_n06_question_exists(self):
        assert "N06" in RIG_JUDGMENT_QUESTIONS
        assert RIG_JUDGMENT_QUESTIONS["N06"]

    def test_n07_question_exists(self):
        assert "N07" in RIG_JUDGMENT_QUESTIONS
        assert RIG_JUDGMENT_QUESTIONS["N07"]

    # Verbatim content checks (docs/03_scene_rig.md §3)

    def test_n02_question_mentions_distinct_agent(self):
        q = RIG_JUDGMENT_QUESTIONS["N02"]
        assert "distinct agent" in q

    def test_n03_question_mentions_actionable_objective(self):
        q = RIG_JUDGMENT_QUESTIONS["N03"]
        assert "actionable objective" in q
        assert "passive emotional state" in q

    def test_n04_question_mentions_tangible_force(self):
        q = RIG_JUDGMENT_QUESTIONS["N04"]
        assert "tangible force" in q

    def test_n05_first_question_mentions_entry_state(self):
        """First N05 question: entry_state is opening condition not outcome."""
        q = RIG_JUDGMENT_QUESTIONS["N05"][0]
        assert "entry_state" in q
        assert "opening" in q
        assert "outcome" in q

    def test_n05_second_question_mentions_risk_not_result(self):
        """Second N05 question: value_at_stake is risk not result."""
        q = RIG_JUDGMENT_QUESTIONS["N05"][1]
        assert "risk" in q
        assert "result" in q

    def test_n06_question_mentions_spatial_environment(self):
        q = RIG_JUDGMENT_QUESTIONS["N06"]
        assert "spatial environment" in q

    def test_n07_question_mentions_trigger_or_deadline(self):
        q = RIG_JUDGMENT_QUESTIONS["N07"]
        assert "trigger" in q or "deadline" in q

    def test_judgment_slot_ids_match_questions_keys(self):
        assert JUDGMENT_SLOT_IDS == frozenset(RIG_JUDGMENT_QUESTIONS.keys())

    def test_n01_not_in_judgment_slot_ids(self):
        assert "N01" not in JUDGMENT_SLOT_IDS

    def test_all_six_judgment_slots_present(self):
        assert JUDGMENT_SLOT_IDS == {"N02", "N03", "N04", "N05", "N06", "N07"}


# ---------------------------------------------------------------------------
# _evaluate_slot — per-slot judgment dispatch
# ---------------------------------------------------------------------------

class TestEvaluateSlot:
    def test_unknown_slot_passes_unconditionally(self):
        """Genre-addition slots have no JUDGMENT — pass unconditionally."""
        assert _evaluate_slot("ZZZZ", "Unknown", "any value") is True

    def test_n01_passes_unconditionally(self):
        """N01 is pure-rule — no JUDGMENT."""
        assert _evaluate_slot("N01", "Narrative Position", "X03") is True

    def test_satisfied_model_returns_true(self):
        with _patch_model(satisfied=True):
            assert _evaluate_slot("N03", "Active Want", "Get the confession") is True

    def test_unsatisfied_model_returns_false(self):
        with _patch_model(satisfied=False):
            assert _evaluate_slot("N03", "Active Want", "feels bad") is False

    def test_n05_both_questions_evaluated(self):
        """N05 calls the model twice (one per question)."""
        call_count = {"n": 0}
        def counting_call(model, contents):
            call_count["n"] += 1
            return _mock_satisfied_response()

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = counting_call
        with patch("src.scene_rig_judgment.Client", return_value=mock_client):
            value = json.dumps({"entry_state": "Alice and Bob are estranged",
                                "value_at_stake": "Their collaboration"})
            _evaluate_slot("N05", "Scene Frame", value)
        assert call_count["n"] == 2

    def test_n05_fails_when_first_question_fails(self):
        """N05 fails (returns False) when the first question is not satisfied."""
        responses = [_mock_unsatisfied_response(), _mock_satisfied_response()]
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = responses
        with patch("src.scene_rig_judgment.Client", return_value=mock_client):
            value = json.dumps({"entry_state": "They got divorced",
                                "value_at_stake": "Their remaining assets"})
            result = _evaluate_slot("N05", "Scene Frame", value)
        assert result is False

    def test_n05_fails_when_second_question_fails(self):
        """N05 fails (returns False) when the second question is not satisfied."""
        responses = [_mock_satisfied_response(), _mock_unsatisfied_response()]
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = responses
        with patch("src.scene_rig_judgment.Client", return_value=mock_client):
            value = json.dumps({"entry_state": "Partners are aligned",
                                "value_at_stake": "Their marriage, which ends here"})
            result = _evaluate_slot("N05", "Scene Frame", value)
        assert result is False

    def test_n05_passes_when_both_questions_pass(self):
        """N05 passes (returns True) when both questions are satisfied."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _mock_satisfied_response()
        with patch("src.scene_rig_judgment.Client", return_value=mock_client):
            value = json.dumps({"entry_state": "Partners are aligned",
                                "value_at_stake": "Their partnership"})
            result = _evaluate_slot("N05", "Scene Frame", value)
        assert result is True

    def test_model_exception_fails_open(self):
        """A model exception fails open (returns True) — never blocks."""
        with patch("src.scene_rig_judgment.Client") as cls:
            cls.return_value.models.generate_content.side_effect = RuntimeError("net")
            result = _evaluate_slot("N03", "Active Want", "x")
        assert result is True


# ---------------------------------------------------------------------------
# _call_judgment — single question model call
# ---------------------------------------------------------------------------

class TestCallJudgment:
    def test_satisfied_returns_true(self):
        with _patch_model(satisfied=True):
            assert _call_judgment("N03", "Active Want", "Get confession", "Is this specific?") is True

    def test_unsatisfied_returns_false(self):
        with _patch_model(satisfied=False):
            assert _call_judgment("N03", "Active Want", "feels sad", "Is this specific?") is False

    def test_model_error_returns_true(self):
        """Model errors fail open — return True, never block."""
        with patch("src.scene_rig_judgment.Client") as cls:
            cls.return_value.models.generate_content.side_effect = RuntimeError("err")
            assert _call_judgment("N03", "Active Want", "x", "Q?") is True

    def test_invalid_json_returns_true(self):
        """Unparseable model response fails open."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value.text = "not json {"
        with patch("src.scene_rig_judgment.Client", return_value=mock_client):
            assert _call_judgment("N03", "Active Want", "x", "Q?") is True

    def test_empty_response_returns_true(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value.text = ""
        with patch("src.scene_rig_judgment.Client", return_value=mock_client):
            assert _call_judgment("N03", "Active Want", "x", "Q?") is True


# ---------------------------------------------------------------------------
# _mark_provisional — marks scene_rig_slots.input_conf
# ---------------------------------------------------------------------------

class TestMarkProvisional:
    def test_updates_input_conf_to_provisional(self):
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb):
            _mark_provisional(SCENE_ID, "N03")
        sb.table.assert_any_call("scene_rig_slots")
        update_call = sb.table.return_value.update.call_args[0][0]
        assert update_call["input_conf"] == "PROVISIONAL"

    def test_filters_by_scene_id_and_slot_id(self):
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb):
            _mark_provisional(SCENE_ID, "N07")
        eq_chain = sb.table.return_value.update.return_value.eq
        # First .eq filters on scene_id
        first_eq_args = eq_chain.call_args_list[0]
        assert first_eq_args[0][0] == "scene_id"
        assert first_eq_args[0][1] == SCENE_ID

    def test_db_error_does_not_raise(self):
        """_mark_provisional must not raise on DB errors."""
        sb = MagicMock()
        sb.table.side_effect = Exception("db down")
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb):
            _mark_provisional(SCENE_ID, "N03")  # must not raise


# ---------------------------------------------------------------------------
# _enqueue_judgment_failed — agent_queue insert
# ---------------------------------------------------------------------------

class TestEnqueueJudgmentFailed:
    def _run(self):
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event") as pub:
            _enqueue_judgment_failed(PROJECT_ID, SCENE_ID, "N03", "Active Want")
        return sb, pub

    def test_inserts_into_agent_queue(self):
        sb, _ = self._run()
        sb.table.assert_any_call("agent_queue")

    def test_item_type_is_slot_judgment_failed(self):
        sb, _ = self._run()
        insert_call = sb.table.return_value.insert.call_args[0][0]
        assert insert_call["item_type"] == "SLOT_JUDGMENT_FAILED"

    def test_payload_contains_slot_id(self):
        sb, _ = self._run()
        insert_call = sb.table.return_value.insert.call_args[0][0]
        payload = json.loads(insert_call["payload"])
        assert payload["slot_id"] == "N03"

    def test_payload_contains_slot_label(self):
        sb, _ = self._run()
        insert_call = sb.table.return_value.insert.call_args[0][0]
        payload = json.loads(insert_call["payload"])
        assert payload["slot_label"] == "Active Want"

    def test_payload_contains_failure_mode(self):
        sb, _ = self._run()
        insert_call = sb.table.return_value.insert.call_args[0][0]
        payload = json.loads(insert_call["payload"])
        assert "failure_mode" in payload

    def test_project_id_recorded(self):
        sb, _ = self._run()
        insert_call = sb.table.return_value.insert.call_args[0][0]
        assert insert_call["project_id"] == PROJECT_ID

    def test_scene_id_recorded(self):
        sb, _ = self._run()
        insert_call = sb.table.return_value.insert.call_args[0][0]
        assert insert_call["scene_id"] == SCENE_ID

    def test_publishes_confluent_event(self):
        _, pub = self._run()
        pub.assert_called_once()
        _, kwargs = pub.call_args
        assert kwargs["event_type"] == "SLOT_JUDGMENT_FAILED"

    def test_confluent_event_project_id(self):
        _, pub = self._run()
        _, kwargs = pub.call_args
        assert kwargs["project_id"] == PROJECT_ID

    def test_confluent_event_scene_id(self):
        _, pub = self._run()
        _, kwargs = pub.call_args
        assert kwargs["scene_id"] == SCENE_ID

    def test_db_error_does_not_raise(self):
        sb = MagicMock()
        sb.table.side_effect = Exception("db down")
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event"):
            _enqueue_judgment_failed(PROJECT_ID, SCENE_ID, "N03", "Active Want")  # must not raise

    def test_confluent_error_does_not_raise(self):
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event", side_effect=Exception("kafka down")):
            _enqueue_judgment_failed(PROJECT_ID, SCENE_ID, "N03", "Active Want")  # must not raise


# ---------------------------------------------------------------------------
# run_rig_judgment — main acceptance criterion
# docs/03_scene_rig.md §4; docs/05_orchestration.md §8
# ---------------------------------------------------------------------------

class TestRunRigJudgment:
    """
    Acceptance criterion: after the writer proceeds to the editor, a failed
    JUDGMENT check on a Rig slot enqueues a SLOT_JUDGMENT_FAILED item in
    agent_queue.
    """

    def _run_with_outcome(self, satisfied: bool):
        """Run run_rig_judgment with all slots filled and a fixed model outcome."""
        slots = _slots_all_filled()
        sb = _sb_mock()
        # load_rig_slots returns the in-memory slots dict
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event"), \
             patch("src.scene_rig.get_supabase", return_value=sb), \
             _patch_model(satisfied=satisfied):
            # Patch load_rig_slots to return our fixture
            with patch("src.scene_rig_judgment.run_rig_judgment.__module__"):
                pass
            with patch("src.scene_rig.load_rig_slots", return_value=slots):
                run_rig_judgment(SCENE_ID, PROJECT_ID)
        return sb

    def test_failed_judgment_inserts_agent_queue_row(self):
        """Core acceptance criterion: SLOT_JUDGMENT_FAILED is enqueued on failure."""
        slots = _slots_all_filled()
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event"), \
             patch("src.scene_rig.load_rig_slots", return_value=slots), \
             _patch_model(satisfied=False):
            run_rig_judgment(SCENE_ID, PROJECT_ID)

        # At least one insert to agent_queue must have happened
        agent_queue_calls = [
            c for c in sb.table.call_args_list
            if c[0][0] == "agent_queue"
        ]
        assert agent_queue_calls, "Expected agent_queue inserts for failed slots"

    def test_failed_judgment_inserts_correct_item_type(self):
        """Each enqueued row must have item_type = SLOT_JUDGMENT_FAILED."""
        slots = {
            "N03": {"is_filled": True, "value": "feels sad"},
        }
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event"), \
             patch("src.scene_rig.load_rig_slots", return_value=slots), \
             _patch_model(satisfied=False):
            run_rig_judgment(SCENE_ID, PROJECT_ID)

        insert_call = sb.table.return_value.insert.call_args
        assert insert_call is not None
        row = insert_call[0][0]
        assert row["item_type"] == "SLOT_JUDGMENT_FAILED"

    def test_passed_judgment_does_not_enqueue(self):
        """A slot whose judgment is satisfied must NOT be enqueued."""
        slots = {
            "N03": {"is_filled": True, "value": "Secure a confession before the hearing"},
        }
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event") as pub, \
             patch("src.scene_rig.load_rig_slots", return_value=slots), \
             _patch_model(satisfied=True):
            run_rig_judgment(SCENE_ID, PROJECT_ID)

        # agent_queue insert must NOT have been called
        agent_queue_calls = [
            c for c in sb.table.call_args_list
            if c[0][0] == "agent_queue"
        ]
        assert not agent_queue_calls

        # No SLOT_JUDGMENT_FAILED Confluent event
        judgment_events = [
            c for c in pub.call_args_list
            if c[1].get("event_type") == "SLOT_JUDGMENT_FAILED"
        ]
        assert not judgment_events

    def test_failed_slot_marked_provisional(self):
        """A slot that fails judgment must be updated to PROVISIONAL."""
        slots = {
            "N03": {"is_filled": True, "value": "feels lost"},
        }
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event"), \
             patch("src.scene_rig.load_rig_slots", return_value=slots), \
             _patch_model(satisfied=False):
            run_rig_judgment(SCENE_ID, PROJECT_ID)

        # scene_rig_slots update called with PROVISIONAL
        update_calls = [
            c for c in sb.table.call_args_list
            if c[0][0] == "scene_rig_slots"
        ]
        assert update_calls
        update_data = sb.table.return_value.update.call_args[0][0]
        assert update_data.get("input_conf") == "PROVISIONAL"

    def test_passed_slot_not_marked_provisional(self):
        """A slot that passes judgment must NOT have its input_conf changed."""
        slots = {
            "N03": {"is_filled": True, "value": "Secure a confession"},
        }
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event"), \
             patch("src.scene_rig.load_rig_slots", return_value=slots), \
             _patch_model(satisfied=True):
            run_rig_judgment(SCENE_ID, PROJECT_ID)

        # scene_rig_slots must NOT have been updated
        rig_updates = [
            c for c in sb.table.call_args_list
            if c[0][0] == "scene_rig_slots"
        ]
        assert not rig_updates

    def test_unfilled_slot_is_skipped(self):
        """Unfilled slots are not judged."""
        slots = {
            "N03": {"is_filled": False, "value": None},
        }
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event") as pub, \
             patch("src.scene_rig.load_rig_slots", return_value=slots), \
             patch("src.scene_rig_judgment.Client") as client_cls:
            run_rig_judgment(SCENE_ID, PROJECT_ID)
        # No model call on unfilled slot
        client_cls.assert_not_called()

    def test_n01_never_judged(self):
        """N01 is pure-rule; run_rig_judgment must never call the model for it."""
        slots = {
            "N01": {"is_filled": True, "value": "X03"},
        }
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event"), \
             patch("src.scene_rig.load_rig_slots", return_value=slots), \
             patch("src.scene_rig_judgment.Client") as client_cls:
            run_rig_judgment(SCENE_ID, PROJECT_ID)
        client_cls.assert_not_called()

    def test_multiple_failing_slots_each_enqueued(self):
        """Each failing slot gets its own agent_queue row."""
        slots = {
            "N03": {"is_filled": True, "value": "feels lost"},
            "N07": {"is_filled": True, "value": "x"},
        }
        sb = _sb_mock()
        insert_calls = []

        def capture_insert(data):
            insert_calls.append(data)
            return sb.table.return_value.insert.return_value

        sb.table.return_value.insert.side_effect = capture_insert

        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event"), \
             patch("src.scene_rig.load_rig_slots", return_value=slots), \
             _patch_model(satisfied=False):
            run_rig_judgment(SCENE_ID, PROJECT_ID)

        # Two inserts — one per failing slot
        judgment_inserts = [
            d for d in insert_calls
            if d.get("item_type") == "SLOT_JUDGMENT_FAILED"
        ]
        assert len(judgment_inserts) == 2

    def test_n05_outcome_wearing_intent_clothes_fails(self):
        """
        docs/03_scene_rig.md §3 (N05 second judgment):
        'Their marriage, which ends here' is an outcome wearing intent's clothes.
        The second N05 question must catch this.
        """
        # Supply a response that says: first question OK, second fails
        responses = [_mock_satisfied_response(), _mock_unsatisfied_response()]
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = responses

        slots = {
            "N05": {
                "is_filled": True,
                "value": json.dumps({
                    "entry_state": "Alice and Bob are married",
                    "value_at_stake": "Their marriage, which ends here",
                }),
            }
        }
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event"), \
             patch("src.scene_rig.load_rig_slots", return_value=slots), \
             patch("src.scene_rig_judgment.Client", return_value=mock_client):
            run_rig_judgment(SCENE_ID, PROJECT_ID)

        # N05 must be marked PROVISIONAL and enqueued
        rig_updates = [
            c for c in sb.table.call_args_list
            if c[0][0] == "scene_rig_slots"
        ]
        assert rig_updates

        agent_queue_calls = [
            c for c in sb.table.call_args_list
            if c[0][0] == "agent_queue"
        ]
        assert agent_queue_calls

    def test_empty_slots_dict_runs_silently(self):
        """No slots filled — nothing judged, nothing enqueued."""
        sb = _sb_mock()
        with patch("src.scene_rig_judgment.get_supabase", return_value=sb), \
             patch("src.scene_rig_judgment.publish_event"), \
             patch("src.scene_rig.load_rig_slots", return_value={}), \
             patch("src.scene_rig_judgment.Client") as client_cls:
            run_rig_judgment(SCENE_ID, PROJECT_ID)
        client_cls.assert_not_called()
