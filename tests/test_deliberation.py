"""
Tests for Artie's Deliberation Engine.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.deliberation import apply_disposition_weights, get_active_axes, synthesize


def test_apply_disposition_weights():
    """Tests the disposition weight logic."""
    poles = [
        {
            "axis": "A1",
            "poles": [
                {"pole": "EXPANSION", "strength": 3},
                {"pole": "RESTRICTION", "strength": 4},
            ],
        },
        {
            "axis": "A2",
            "poles": [
                {"pole": "INSIGHT", "strength": 2},
                {"pole": "ANALYSIS", "strength": 2},
            ],
        },
    ]
    payload = {
        "pending_findings": [{"status": "ATTESTED", "weight": 5}],
        "progress_ratio": 0.1,
        "friction_tripped": True,
    }

    weighted_poles = apply_disposition_weights(poles, payload)

    # A1: RESTRICTION +1 (ATTESTED, weight >= 4), EXPANSION +1 (progress_ratio < 0.15)
    assert weighted_poles[0]["poles"][0]["strength"] == 4  # EXPANSION
    assert weighted_poles[0]["poles"][1]["strength"] == 5  # RESTRICTION

    # A2: ANALYSIS +1
    assert weighted_poles[1]["poles"][0]["strength"] == 2  # INSIGHT
    assert weighted_poles[1]["poles"][1]["strength"] == 3  # ANALYSIS


@patch.dict("os.environ", {"GEMINI_TEXT_MODEL": "models/gemini-3.5-flash"})
@pytest.mark.asyncio
async def test_synthesize():
    """Tests the synthesis function."""
    poles = [{"axis": "A1", "poles": [{"pole": "EXPANSION", "strength": 3}]}]
    payload = {"some": "data"}
    user_id = "test_user"
    project_id = "test_project"

    mock_decision = {
        "action": "RAISE_FINDING",
        "target": "X06.Y2",
        "hold": [],
        "register": "MENTORIAL_ANECDOTAL",
        "rationale": "Test rationale",
    }

    # Mock the response from the LlmAgent
    mock_response = MagicMock()
    mock_response.parts = [MagicMock()]
    mock_response.parts[0].text = f"```json\n{json.dumps(mock_decision)}\n```"

    # Patch dependencies
    with patch("src.deliberation.get_commitment_state") as mock_get_commitment_state, \
         patch("src.deliberation.get_session_for_user", new_callable=AsyncMock) as mock_get_session, \
         patch("src.deliberation.LlmAgent") as mock_llm_agent:
        
        # Configure mocks
        mock_get_commitment_state.return_value = {"available_registers": ["MENTORIAL_ANECDOTAL"]}
        mock_get_session.return_value = MagicMock(session_id="test_session")
        
        mock_agent_instance = MagicMock()
        mock_agent_instance.send = AsyncMock(return_value=mock_response)
        mock_llm_agent.return_value = mock_agent_instance

        # Call the function
        decision = await synthesize(poles, payload=payload, user_id=user_id, project_id=project_id)

        # Assertions
        assert decision == mock_decision
        mock_get_commitment_state.assert_called_once_with(project_id)
        mock_llm_agent.assert_called_once()
        mock_agent_instance.send.assert_called_once()

def test_get_active_axes_no_findings():
    """Tests that no axes are returned when there are no findings."""
    payload = {}
    assert get_active_axes(payload) == []

def test_get_active_axes_pending_findings():
    """Tests that A1 is returned when there are pending findings."""
    payload = {"pending_findings": [{"status": "PENDING"}]}
    assert get_active_axes(payload) == ["A1"]

def test_get_active_axes_anchored_finding():
    """Tests that A1 and A4 are returned when there is an anchored finding."""
    payload = {"pending_findings": [{"status": "ANCHORED"}]}
    assert get_active_axes(payload) == ["A1", "A4"]

def test_get_active_axes_slot_value():
    """Tests that A2 is returned when a slot value arrives."""
    payload = {"gate": "GREENLIGHT", "slot_id": "test_slot"}
    assert get_active_axes(payload) == ["A2"]

def test_get_active_axes_a3_counter_placeholder():
    """
    Tests that A3 is not activated, as the logic is not yet implemented.
    This test is a placeholder for when A3's counter logic is added.
    """
    # This payload would theoretically trigger A3 if it were implemented.
    payload = {"hypothetical_A3_trigger": True}
    assert "A3" not in get_active_axes(payload)

def test_get_active_axes_two_axis_cap():
    """Tests that the active axes are capped at two when three would qualify."""
    payload = {
        "pending_findings": [{"status": "PENDING"}, {"status": "ANCHORED"}],
        "gate": "GREENLIGHT",
        "slot_id": "test_slot"
    }
    # A1, A2, and A4 are all active. A1 and A4 have priority.
    assert get_active_axes(payload) == ["A1", "A4"]


@patch.dict("os.environ", {"GEMINI_TEXT_MODEL": "models/gemini-3.5-flash"})
@pytest.mark.asyncio
async def test_voice():
    """Tests the voice rendering function."""
    decision = {"action": "ACKNOWLEDGE_ONLY", "register": "MENTORIAL_ANECDOTAL"}
    payload = {"some": "payload"}
    user_id = "test_user"
    project_id = "test_project"
    system_prompt_content = "You are Artie."

    mock_response = MagicMock()
    mock_response.parts = [MagicMock()]
    mock_response.parts[0].text = "Acknowledged, kid."

    with patch("builtins.open", MagicMock(read_data=system_prompt_content)), \
         patch("src.deliberation.get_commitment_state") as mock_get_commitment_state, \
         patch("src.deliberation.load_bible_slots") as mock_load_bible_slots, \
         patch("src.deliberation.get_session_for_user", new_callable=AsyncMock) as mock_get_session, \
         patch("src.deliberation.LlmAgent") as mock_llm_agent:

        mock_get_commitment_state.return_value = {
            "commitment_state": "SKEPTICAL",
            "use_name_not_kid": False
        }
        mock_load_bible_slots.return_value = {"S09": {"value": "Comedy"}}
        mock_get_session.return_value = MagicMock(session_id="test_session")
        
        mock_agent_instance = MagicMock()
        mock_agent_instance.send = AsyncMock(return_value=mock_response)
        mock_llm_agent.return_value = mock_agent_instance

        # We need to import 'voice' inside the test function to use the mocks
        from src.deliberation import voice
        result = await voice(decision, payload=payload, user_id=user_id, project_id=project_id)

        assert result == "Acknowledged, kid."
        mock_llm_agent.assert_called_once()
        
        # Check that the prompt contains the key elements
        sent_prompt = mock_agent_instance.send.call_args[0][1]
        assert "Project Genre: Comedy" in sent_prompt
        assert "Tummler/Poet Blend: 90/10" in sent_prompt
        assert "Commitment State: SKEPTICAL" in sent_prompt
        assert '"register": "MENTORIAL_ANECDOTAL"' in sent_prompt
