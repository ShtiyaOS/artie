"""
Tests for the Director agent.
"""

import unittest
import json

import pytest
from unittest.mock import patch, MagicMock, ANY

from src.agents import director

class TestDirectorHelpers(unittest.TestCase):
    def test_parse_scene_heading(self):
        self.assertEqual(director._parse_scene_heading("INT. ROOM - DAY"), {'interiority': 'interior', 'location': 'ROOM', 'time_of_day': 'DAY'})
        self.assertEqual(director._parse_scene_heading("EXT. DESERT - NIGHT"), {'interiority': 'exterior', 'location': 'DESERT', 'time_of_day': 'NIGHT'})
        self.assertEqual(director._parse_scene_heading("INT. SPACESHIP"), {'interiority': 'interior', 'location': 'SPACESHIP', 'time_of_day': 'DAY'})

    def test_normalize_capitalization(self):
        self.assertEqual(director._normalize_capitalization("MARLA enters."), "Marla enters.")
        self.assertEqual(director._normalize_capitalization("He RUNS."), "He Runs.")
        self.assertEqual(director._normalize_capitalization("A normal sentence."), "A normal sentence.")

@pytest.mark.asyncio
@patch('src.agents.director._call_llm_for_step')
async def test_construct_prompt_pipeline(mock_call_llm):
    """
    Tests the full prompt construction pipeline, mocking the LLM calls.
    """
    # Assemble
    payload = {
        "action_lines": ["MARLA enters. She REMEMBERS her father. A GUN is on the table."],
        "scene_heading": "INT. OFFICE - NIGHT"
    }
    # Mock the return values for the 3 LLM calls in the pipeline
    mock_call_llm.side_effect = [
        "Marla enters and sees a gun on the table.", # 3. Select moment
        "Marla enters and sees a gun on the table.", # 4. Drop interiority
        "Marla enters and sees a weapon on the table."  # 6. Restrain violence
    ]

    # Act
    result = await director._construct_prompt(payload)

    # Assert
    assert "weapon on the table" in result["prompt"]
    assert "OFFICE" in result["prompt"]
    assert "cinematic still" in result["prompt"]
    assert "Capitalization normalized." in result["assumption_note"]
    assert "Moment selected:" in result["assumption_note"]
    assert mock_call_llm.call_count == 3

@pytest.mark.asyncio
@patch('src.agents.director._construct_prompt')
@patch('src.agents.director.invoke_agent')
async def test_invoke_calls_pipeline_and_agent(mock_invoke_agent, mock_construct_prompt):
    """
    Tests that the main invoke function calls the construction pipeline
    and then passes the result to the agent runner.
    """
    # Assemble
    payload = {"action_lines": ["Action!"], "scene_heading": "INT. PLACE - DAY"}
    constructed_data = {"prompt": "A prompt", "assumption_note": "A note"}
    mock_construct_prompt.return_value = constructed_data
    mock_invoke_agent.return_value = json.dumps(constructed_data)

    # Act
    result = await director.invoke(
        payload=payload, user_id="test", project_id="test", scene_id="test"
    )

    # Assert
    mock_construct_prompt.assert_awaited_once_with(payload)
    mock_invoke_agent.assert_awaited_once_with(
        runner=ANY,
        session_service=ANY,
        app_name='director',
        user_id='test',
        input_text=json.dumps(constructed_data),
        event_type='FRAME_PROMPT_CONSTRUCTED',
        actor='director',
        project_id='test',
        scene_id='test',
        bible_version_id=0,
        extra_provenance={
            'action_line_count': 1,
            'character_ref_count': 0,
            'constructed_prompt': 'A prompt',
            'assumption_note': 'A note',
        },
    )
    assert result == json.dumps(constructed_data)

