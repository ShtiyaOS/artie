"""
Tests for the editor API's /events endpoint.
"""

import json
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

# Mock the database lookups and event publishers
@patch("src.api.editor.get_supabase")
@patch("src.api.editor.get_clickhouse")
@patch("src.api.editor.publish_event")
def test_post_keystroke_batch_event(mock_publish_event, mock_get_clickhouse, mock_get_supabase):
    # Arrange
    mock_supabase_client = MagicMock()
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"project_id": "proj-123"}]
    mock_get_supabase.return_value = mock_supabase_client

    mock_clickhouse_client = MagicMock()
    mock_get_clickhouse.return_value = mock_clickhouse_client

    scene_id = "scene-456"
    payload = {
        "component_id": "comp-789",
        "ts_start_micros": 1700000000000000,
        "ts_end_micros": 1700000001000000,
        "char_delta": 10,
        "chain_hash": "hash-abc-123",
    }
    event = {"event_type": "KEYSTROKE_BATCH", "scene_id": scene_id, "payload": payload}

    # Act
    response = client.post("/events", json=event)

    # Assert
    assert response.status_code == 202
    assert response.json() == {"status": "keystroke batch recorded"}

    mock_get_clickhouse.assert_called_once()
    mock_clickhouse_client.insert.assert_called_once_with(
        "keystroke_batches",
        [[
            "proj-123",
            scene_id,
            payload["component_id"],
            payload["ts_start_micros"],
            payload["ts_end_micros"],
            payload["char_delta"],
            payload["chain_hash"],
        ]],
        column_names=[
            "project_id", "scene_id", "component_id",
            "ts_start_micros", "ts_end_micros", "char_delta", "content_hash"
        ],
    )
    mock_publish_event.assert_not_called()


@patch("src.api.editor.get_supabase")
@patch("src.api.editor.get_clickhouse")
@patch("src.api.editor.publish_event")
def test_post_paste_event(mock_publish_event, mock_get_clickhouse, mock_get_supabase):
    # Arrange
    mock_supabase_client = MagicMock()
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"project_id": "proj-123"}]
    mock_get_supabase.return_value = mock_supabase_client

    scene_id = "scene-456"
    payload = {
		"origin": "UNKNOWN",
		"char_count": 150,
		"target_component_id": "comp-789"
    }
    event = {"event_type": "PASTE", "scene_id": scene_id, "payload": payload}

    # Act
    response = client.post("/events", json=event)

    # Assert
    assert response.status_code == 202
    assert response.json() == {"status": "paste event published"}

    mock_publish_event.assert_called_once_with(
        event_type="PASTE",
        actor="human",
        payload=payload,
        project_id="proj-123",
        scene_id=scene_id,
    )
    mock_get_clickhouse.assert_not_called()

@patch("src.api.editor.publish_event")
@patch("src.api.editor.get_clickhouse")
@patch("src.api.editor.get_supabase")
def test_post_event_project_not_found(mock_get_supabase, mock_get_clickhouse, mock_publish_event):
    # Arrange
    mock_supabase_client = MagicMock()
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    mock_get_supabase.return_value = mock_supabase_client

    event = {"event_type": "KEYSTROKE_BATCH", "scene_id": "scene-nonexistent", "payload": {}}

    # Act
    response = client.post("/events", json=event)

    # Assert
    assert response.status_code == 404
    assert "could not find project for scene" in response.json()["error"]
    mock_get_clickhouse.assert_not_called()
    mock_publish_event.assert_not_called()
