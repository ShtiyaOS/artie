"""
Tests for the Director agent.
"""

import asyncio
import os
import unittest
import json

import pytest
from unittest.mock import patch, MagicMock, ANY, PropertyMock, AsyncMock

from google.genai import types

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

@patch.dict("os.environ", {"GEMINI_TEXT_MODEL": "models/gemini-3.5-flash", "GEMINI_IMAGE_MODEL": "models/gemini-3-pro-image"})
@pytest.mark.asyncio
@patch('src.agents.director._construct_prompt')
@patch('src.agents.director.generate_frame')
@patch('src.agents.director.gcs_client.upload_asset')
@patch('src.agents.director.supabase_client.create_asset_record')
@patch('src.agents.director._generate_assumption_note_model_part')
@patch('src.agents.director._get_session_service')
async def test_invoke_end_to_end_success(
    mock_get_session_service,
    mock_generate_assumption_note,
    mock_create_asset_record,
    mock_upload_asset,
    mock_generate_frame,
    mock_construct_prompt,
):
    """
    Tests the full invoke pipeline on success.
    """
    # Assemble
    payload = {"action_lines": ["Action!"], "scene_heading": "INT. PLACE - DAY"}
    constructed_data = {"prompt": "A prompt", "assumption_note": "A note"}
    mock_construct_prompt.return_value = constructed_data
    mock_generate_assumption_note.return_value = "Model-generated note."

    mock_generate_frame.return_value = (b'imagedata', "STOP")
    mock_upload_asset.return_value = "gs://test-bucket/some/path.jpg"
    
    expected_asset_record = {"asset_id": "new-uuid", "gcs_uri": "gs://test-bucket/some/path.jpg"}
    mock_create_asset_record.return_value = expected_asset_record

    mock_session = MagicMock()
    mock_session.emit_event = AsyncMock()
    mock_session_service = MagicMock()
    mock_session_service.get_session = AsyncMock(return_value=mock_session)
    mock_get_session_service.return_value = mock_session_service

    # Act
    result = await director.invoke(
        payload=payload, user_id="test", project_id="p1", scene_id="s1"
    )

    # Assert
    mock_construct_prompt.assert_awaited_once_with(payload)
    mock_generate_frame.assert_awaited_once()
    mock_upload_asset.assert_called_once()
    mock_create_asset_record.assert_called_once_with(
        scene_id='s1',
        gcs_uri="gs://test-bucket/some/path.jpg",
        model="models/gemini-3-pro-image",
        prompt="A prompt",
        assumption_note="A note\n\nModel-generated assumptions:\nModel-generated note.",
        finish_reason="STOP",
    )
    assert result == expected_asset_record
    # Check that FRAME_PROMPT_CONSTRUCTED event was emitted
    assert mock_session.emit_event.call_count == 1
    event_name, event_kwargs = mock_session.emit_event.call_args
    assert event_name[0] == "FRAME_PROMPT_CONSTRUCTED"


@pytest.mark.asyncio
@patch('src.agents.director._construct_prompt')
@patch('src.agents.director.generate_frame')
@patch('src.agents.director.gcs_client.upload_asset')
@patch('src.agents.director.supabase_client.create_asset_record')
@patch('src.agents.director._get_session_service')
async def test_invoke_generation_fails(
    mock_get_session_service,
    mock_create_asset_record,
    mock_upload_asset,
    mock_generate_frame,
    mock_construct_prompt,
):
    """
    Tests that the invoke pipeline returns an error if image generation fails.
    """
    # Assemble
    payload = {"action_lines": ["Action!"], "scene_heading": "INT. PLACE - DAY"}
    constructed_data = {"prompt": "A prompt", "assumption_note": "A note"}
    mock_construct_prompt.return_value = constructed_data

    mock_generate_frame.return_value = (None, "SAFETY")

    mock_session = MagicMock()
    mock_session.emit_event = AsyncMock()
    mock_session_service = MagicMock()
    mock_session_service.get_session = AsyncMock(return_value=mock_session)
    mock_get_session_service.return_value = mock_session_service

    # Act
    result = await director.invoke(
        payload=payload, user_id="test", project_id="p1", scene_id="s1"
    )

    # Assert
    mock_construct_prompt.assert_awaited_once_with(payload)
    mock_generate_frame.assert_awaited_once()
    mock_upload_asset.assert_not_called()
    mock_create_asset_record.assert_not_called()
    assert result == {"error": "Image generation failed", "finish_reason": "SAFETY"}



# ------------------------------------------------------------------------------
# Mock Response Objects (for genai.Client pattern)
# ------------------------------------------------------------------------------
class MockInlineData:
    def __init__(self, data=b'imagedata', mime_type='image/jpeg'):
        self.data = data
        self.mime_type = mime_type

class MockPart:
    def __init__(self, with_inline_data=True, text=None):
        if with_inline_data:
            self.inline_data = MockInlineData()
        if text:
            self.text = text

class MockContent:
    def __init__(self, parts=None):
        self.parts = parts if parts is not None else [MockPart()]

class MockCandidate:
    def __init__(self, finish_reason_str="STOP", content=None):
        self.finish_reason = MagicMock()
        self.finish_reason.name = finish_reason_str
        self.finish_reason.value = 1 # Dummy value
        self.content = content if content is not None else MockContent()

class MockPromptFeedback:
    def __init__(self, block_reason=None):
        self.block_reason = None
        if block_reason:
            self.block_reason = MagicMock()
            self.block_reason.name = block_reason

class MockGenAIResponse:
    def __init__(self, candidates=None, prompt_feedback=None):
        self.candidates = candidates if candidates is not None else [MockCandidate()]
        # Use hasattr to check for prompt_feedback because the real object may not have it on success
        if prompt_feedback is not None:
            self.prompt_feedback = prompt_feedback
        else:
            self.prompt_feedback = None

# ------------------------------------------------------------------------------
# Image Generation Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
@patch.dict(os.environ, {"GEMINI_API_KEY": "test_key", "GEMINI_IMAGE_MODEL": "gemini-test-model"})
@patch('src.agents.director.genai.Client')
async def test_generate_frame_success(mock_genai_client):
    """
    Tests the happy path for image generation using the client pattern.
    """
    # Assemble
    mock_client_instance = mock_genai_client.return_value
    mock_client_instance.models.generate_content.return_value = MockGenAIResponse()

    mock_session = MagicMock()
    mock_session.emit_event = AsyncMock()
    mock_session_service = MagicMock()
    mock_session_service.get_session = AsyncMock(return_value=mock_session)

    # Act
    image_bytes, finish_reason = await director.generate_frame(
        prompt="A test prompt",
        user_id="test_user",
        session_service=mock_session_service,
        project_id="p1",
        scene_id="s1",
        is_demo_frame=True,
    )

    # Assert
    mock_genai_client.assert_called_with(api_key='test_key')
    mock_client_instance.models.generate_content.assert_called_once()
    call_kwargs = mock_client_instance.models.generate_content.call_args.kwargs
    assert "2K resolution" in call_kwargs['contents']
    assert call_kwargs['model'] == 'gemini-test-model'
    
    assert image_bytes == b'imagedata'
    assert finish_reason == "STOP"
    
    mock_session_service.get_session.assert_awaited_once_with("director", "test_user")
    mock_session.emit_event.assert_awaited_once()
    event_name, event_kwargs = mock_session.emit_event.call_args
    assert event_name[0] == "FRAME_GENERATED"
    assert event_kwargs['extra_data']['finish_reason'] == "STOP"

@pytest.mark.asyncio
@patch.dict(os.environ, {"GEMINI_API_KEY": "test_key", "GEMINI_IMAGE_MODEL": "gemini-test-model"})
@patch('src.agents.director.genai.Client')
async def test_generate_frame_blocked_prompt(mock_genai_client):
    """
    Tests failure handling for a blocked prompt.
    """
    # Assemble
    mock_client_instance = mock_genai_client.return_value
    mock_client_instance.models.generate_content.return_value = MockGenAIResponse(
        prompt_feedback=MockPromptFeedback(block_reason="SAFETY"),
        candidates=[] # No candidates when prompt is blocked
    )

    mock_session = MagicMock()
    mock_session.emit_event = AsyncMock()
    mock_session_service = MagicMock()
    mock_session_service.get_session = AsyncMock(return_value=mock_session)
    
    # Act
    image_bytes, finish_reason = await director.generate_frame(
        prompt="A naughty prompt", user_id="test_user", session_service=mock_session_service
    )

    # Assert
    assert image_bytes is None
    assert finish_reason == "BLOCK_REASON_SAFETY"
    
    mock_session.emit_event.assert_awaited_once()
    _, event_kwargs = mock_session.emit_event.call_args
    assert event_kwargs['extra_data']['finish_reason'] == "BLOCK_REASON_SAFETY"

@pytest.mark.asyncio
@patch.dict(os.environ, {"GEMINI_API_KEY": "test_key", "GEMINI_IMAGE_MODEL": "gemini-test-model"})
@patch('src.agents.director.genai.Client')
async def test_generate_frame_finish_reason_safety(mock_genai_client):
    """
    Tests failure handling for an image withheld due to safety reasons.
    """
    # Assemble
    mock_client_instance = mock_genai_client.return_value
    mock_client_instance.models.generate_content.return_value = MockGenAIResponse(
        candidates=[MockCandidate(finish_reason_str="SAFETY", content=MockContent(parts=[]))]
    )

    mock_session = MagicMock()
    mock_session.emit_event = AsyncMock()
    mock_session_service = MagicMock()
    mock_session_service.get_session = AsyncMock(return_value=mock_session)

    # Act
    image_bytes, finish_reason = await director.generate_frame(
        prompt="A prompt", user_id="test_user", session_service=mock_session_service
    )

    # Assert
    assert image_bytes is None
    assert finish_reason == "SAFETY"
    
    mock_session.emit_event.assert_awaited_once()
    _, event_kwargs = mock_session.emit_event.call_args
    assert event_kwargs['extra_data']['finish_reason'] == "SAFETY"

@pytest.mark.asyncio
@patch.dict(os.environ, {"GEMINI_API_KEY": "test_key", "GEMINI_IMAGE_MODEL": "gemini-test-model"})
@patch('src.agents.director.genai.Client')
async def test_generate_frame_api_exception(mock_genai_client):
    """
    Tests failure handling when the API call raises an exception.
    """
    # Assemble
    mock_client_instance = mock_genai_client.return_value
    mock_client_instance.models.generate_content.side_effect = ValueError("API Error")

    mock_session = MagicMock()
    mock_session.emit_event = AsyncMock()
    mock_session_service = MagicMock()
    mock_session_service.get_session = AsyncMock(return_value=mock_session)

    # Act
    image_bytes, finish_reason = await director.generate_frame(
        prompt="A prompt", user_id="test_user", session_service=mock_session_service
    )

    # Assert
    assert image_bytes is None
    assert finish_reason == "GENERATION_ERROR"


@pytest.mark.asyncio
@patch.dict(os.environ, {"GEMINI_API_KEY": "test_key", "GEMINI_FAST_MODEL": "gemini-fast-model"})
@patch('src.agents.director.genai.Client')
async def test_generate_assumption_note_model_part_success(mock_genai_client):
    """
    Tests the happy path for assumption note model part generation.
    """
    # Assemble
    mock_client_instance = mock_genai_client.return_value
    mock_response_content = "people present: a man (not specified in prompt)"
    mock_client_instance.models.generate_content.return_value = MockGenAIResponse(
        candidates=[MockCandidate(content=MockContent(parts=[MockPart(with_inline_data=False, text=mock_response_content)]))]
    )

    # Act
    note = await director._generate_assumption_note_model_part(
        prompt="A test prompt",
        image_bytes=b"testimagedata"
    )

    # Assert
    mock_genai_client.assert_called_with(api_key='test_key')
    mock_client_instance.models.generate_content.assert_called_once()
    call_kwargs = mock_client_instance.models.generate_content.call_args.kwargs
    assert call_kwargs['model'] == 'gemini-fast-model'
    assert "people present:" in call_kwargs['contents']
    assert any(isinstance(p, types.Part) and p.inline_data.data == b'testimagedata' for p in call_kwargs['contents'])
    assert note == mock_response_content

@patch.dict("os.environ", {"GEMINI_TEXT_MODEL": "models/gemini-3.5-flash", "GEMINI_IMAGE_MODEL": "models/gemini-3-pro-image"})
@pytest.mark.asyncio
@patch('src.agents.director._construct_prompt')
@patch('src.agents.director.generate_frame')
@patch('src.agents.director._generate_assumption_note_model_part')
@patch('src.agents.director.gcs_client.upload_asset')
@patch('src.agents.director.supabase_client.create_asset_record')
@patch('src.agents.director._get_session_service')
async def test_invoke_with_assumption_note(
    mock_get_session_service,
    mock_create_asset_record,
    mock_upload_asset,
    mock_generate_assumption_note,
    mock_generate_frame,
    mock_construct_prompt,
):
    """
    Tests that the invoke pipeline generates and saves the full assumption note.
    """
    # Assemble
    payload = {"action_lines": ["Action!"], "scene_heading": "INT. PLACE - DAY"}
    mock_construct_prompt.return_value = {"prompt": "A prompt", "assumption_note": "Deterministic note."}
    mock_generate_frame.return_value = (b'imagedata', "STOP")
    mock_generate_assumption_note.return_value = "Model-generated note."
    mock_upload_asset.return_value = "gs://test-bucket/some/path.jpg"
    mock_create_asset_record.return_value = {"asset_id": "new-uuid"}
    
    mock_session = MagicMock()
    mock_session.emit_event = AsyncMock()
    mock_session_service = MagicMock()
    mock_session_service.get_session = AsyncMock(return_value=mock_session)
    mock_get_session_service.return_value = mock_session_service

    # Act
    await director.invoke(
        payload=payload, user_id="test", project_id="p1", scene_id="s1"
    )

    # Assert
    mock_generate_assumption_note.assert_awaited_once_with(prompt="A prompt", image_bytes=b'imagedata')
    mock_create_asset_record.assert_called_once()
    _, kwargs = mock_create_asset_record.call_args
    expected_note = "Deterministic note.\n\nModel-generated assumptions:\nModel-generated note."
    assert kwargs['assumption_note'] == expected_note
