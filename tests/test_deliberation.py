"""
Tests for Artie's Deliberation Engine.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.deliberation import apply_disposition_weights, synthesize


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
