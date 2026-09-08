"""
Tests for the editor workbench API — docs/14_editor.md §1, §2, §6.

All Supabase calls are patched. No network I/O.

Run with: python -m pytest tests/test_editor_api.py -v
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import FileResponse


# ---------------------------------------------------------------------------
# App fixture — build a minimal FastAPI app with only the editor router.
# This avoids the provenance_consumer signal.signal non-main-thread error
# that fires when TestClient bootstraps the full src.main app.
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    test_app = FastAPI()

    # Mount the editor router directly.
    from src.api.editor import router as editor_router
    test_app.include_router(editor_router)

    # Add the /editor HTML route (mirrors src/main.py).
    @test_app.get("/editor")
    async def _editor_ui():
        path = os.path.join(
            os.path.dirname(__file__), "..", "static", "editor.html"
        )
        return FileResponse(path, media_type="text/html")

    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper: build a mock Supabase chained-call result
# ---------------------------------------------------------------------------

def _mock_db(return_data):
    """Return a mock that simulates db.table(...).select(...).eq(...).execute()."""
    mock_result = MagicMock()
    mock_result.data = return_data

    mock_chain = MagicMock()
    mock_chain.execute.return_value = mock_result
    mock_chain.select.return_value = mock_chain
    mock_chain.insert.return_value = mock_chain
    mock_chain.update.return_value = mock_chain
    mock_chain.delete.return_value = mock_chain
    mock_chain.eq.return_value = mock_chain
    mock_chain.order.return_value = mock_chain
    mock_chain.limit.return_value = mock_chain

    mock_db = MagicMock()
    mock_db.table.return_value = mock_chain
    return mock_db, mock_chain


# ---------------------------------------------------------------------------
# POST /scene/{scene_id}/takes — create a take
# ---------------------------------------------------------------------------

class TestCreateTake:
    def test_creates_first_take(self, client):
        take_row = {
            "take_id": "take-uuid-1",
            "take_number": 1,
            "scene_id": "scene-uuid",
            "is_final_cut": False,
        }
        db, chain = _mock_db([take_row])
        # First call (counting existing) returns empty; second (insert) returns the row.
        chain.execute.side_effect = [
            MagicMock(data=[]),          # count existing takes
            MagicMock(data=[take_row]),  # insert result
        ]
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.post("/scene/scene-uuid/takes")
        assert res.status_code == 201
        body = res.json()
        assert body["take_id"] == "take-uuid-1"
        assert body["take_number"] == 1

    def test_creates_second_take(self, client):
        existing_row = {"take_number": 1}
        take_row = {
            "take_id": "take-uuid-2",
            "take_number": 2,
            "scene_id": "scene-uuid",
            "is_final_cut": False,
        }
        db, chain = _mock_db([take_row])
        chain.execute.side_effect = [
            MagicMock(data=[existing_row]),  # existing takes → max take_number=1
            MagicMock(data=[take_row]),      # insert result
        ]
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.post("/scene/scene-uuid/takes")
        assert res.status_code == 201
        assert res.json()["take_number"] == 2


# ---------------------------------------------------------------------------
# GET /scene/{scene_id}/takes — list takes
# ---------------------------------------------------------------------------

class TestListTakes:
    def test_returns_takes(self, client):
        rows = [
            {"take_id": "t1", "take_number": 1, "is_final_cut": False, "submitted_at": None, "created_at": "2025-01-01T00:00:00Z"},
            {"take_id": "t2", "take_number": 2, "is_final_cut": True,  "submitted_at": "2025-01-02T00:00:00Z", "created_at": "2025-01-02T00:00:00Z"},
        ]
        db, chain = _mock_db(rows)
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.get("/scene/scene-uuid/takes")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        assert data[0]["take_id"] == "t1"
        assert data[1]["is_final_cut"] is True

    def test_empty_scene(self, client):
        db, chain = _mock_db([])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.get("/scene/new-scene/takes")
        assert res.status_code == 200
        assert res.json() == []


# ---------------------------------------------------------------------------
# GET /takes/{take_id} — single take
# ---------------------------------------------------------------------------

class TestGetTake:
    def test_found(self, client):
        row = {"take_id": "t1", "take_number": 1, "scene_id": "s1", "is_final_cut": False}
        db, chain = _mock_db([row])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.get("/takes/t1")
        assert res.status_code == 200
        assert res.json()["take_id"] == "t1"

    def test_not_found(self, client):
        db, chain = _mock_db([])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.get("/takes/no-such-take")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# GET /takes/{take_id}/components
# ---------------------------------------------------------------------------

class TestListComponents:
    def test_returns_components(self, client):
        rows = [
            {"component_id": "c1", "sequence_order": 1, "comp_type": "SCENE_HEADING", "content": "INT. DINER - NIGHT", "updated_at": "2025-01-01T00:00:00Z"},
            {"component_id": "c2", "sequence_order": 2, "comp_type": "ACTION",        "content": "Marla enters.",       "updated_at": "2025-01-01T00:00:00Z"},
        ]
        db, chain = _mock_db(rows)
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.get("/takes/take-1/components")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        assert data[0]["comp_type"] == "SCENE_HEADING"


# ---------------------------------------------------------------------------
# POST /takes/{take_id}/components
# ---------------------------------------------------------------------------

class TestCreateComponent:
    def test_creates_action(self, client):
        row = {"component_id": "c1", "sequence_order": 1, "comp_type": "ACTION", "content": "She enters."}
        db, chain = _mock_db([row])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.post("/takes/take-1/components", json={
                "comp_type": "ACTION",
                "content": "She enters.",
                "sequence_order": 1,
            })
        assert res.status_code == 201
        assert res.json()["comp_type"] == "ACTION"

    def test_normalises_lowercase_type(self, client):
        row = {"component_id": "c2", "sequence_order": 1, "comp_type": "CHARACTER", "content": "MARLA"}
        db, chain = _mock_db([row])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.post("/takes/take-1/components", json={
                "comp_type": "character",      # lowercase — should be accepted
                "content": "MARLA",
                "sequence_order": 1,
            })
        assert res.status_code == 201

    def test_rejects_invalid_type(self, client):
        db, _ = _mock_db([])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.post("/takes/take-1/components", json={
                "comp_type": "MONOLOGUE",
                "content": "hello",
                "sequence_order": 1,
            })
        assert res.status_code == 400

    def test_rejects_missing_sequence_order(self, client):
        db, _ = _mock_db([])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.post("/takes/take-1/components", json={
                "comp_type": "ACTION",
                "content": "hello",
            })
        assert res.status_code == 400

    def test_all_seven_component_types_accepted(self, client):
        types = ["SCENE_HEADING", "ACTION", "CHARACTER", "DIALOGUE",
                 "PARENTHETICAL", "TRANSITION", "NOTE"]
        for ctype in types:
            row = {"component_id": f"c-{ctype}", "sequence_order": 1,
                   "comp_type": ctype, "content": "test"}
            db, chain = _mock_db([row])
            with patch("src.api.editor.get_supabase", return_value=db):
                res = client.post("/takes/take-1/components", json={
                    "comp_type": ctype,
                    "content": "test",
                    "sequence_order": 1,
                })
            assert res.status_code == 201, f"Expected 201 for {ctype}, got {res.status_code}"


# ---------------------------------------------------------------------------
# PUT /components/{component_id}
# ---------------------------------------------------------------------------

class TestUpdateComponent:
    def test_updates_content(self, client):
        row = {"component_id": "c1", "sequence_order": 1, "comp_type": "ACTION", "content": "Updated text."}
        db, chain = _mock_db([row])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.put("/components/c1", json={"content": "Updated text."})
        assert res.status_code == 200
        assert res.json()["content"] == "Updated text."

    def test_updates_comp_type(self, client):
        row = {"component_id": "c1", "sequence_order": 1, "comp_type": "CHARACTER", "content": "MARLA"}
        db, chain = _mock_db([row])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.put("/components/c1", json={"comp_type": "CHARACTER", "content": "MARLA"})
        assert res.status_code == 200

    def test_rejects_invalid_type(self, client):
        db, _ = _mock_db([])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.put("/components/c1", json={"comp_type": "MONOLOGUE"})
        assert res.status_code == 400

    def test_not_found(self, client):
        db, chain = _mock_db([])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.put("/components/no-such", json={"content": "x"})
        assert res.status_code == 404

    def test_empty_body_rejected(self, client):
        db, _ = _mock_db([])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.put("/components/c1", json={})
        assert res.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /components/{component_id}
# ---------------------------------------------------------------------------

class TestDeleteComponent:
    def test_deletes(self, client):
        row = {"component_id": "c1"}
        db, chain = _mock_db([row])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.delete("/components/c1")
        assert res.status_code == 200

    def test_not_found(self, client):
        db, chain = _mock_db([])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.delete("/components/no-such")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# GET /takes/{take_id}/fountain — Fountain export
# ---------------------------------------------------------------------------

class TestFountainExport:
    def test_emits_forcing_characters(self, client):
        rows = [
            {"comp_type": "SCENE_HEADING", "content": "INT. DINER - NIGHT", "sequence_order": 1},
            {"comp_type": "ACTION",        "content": "Marla enters.",       "sequence_order": 2},
            {"comp_type": "CHARACTER",     "content": "MARLA",               "sequence_order": 3},
            {"comp_type": "DIALOGUE",      "content": "You don't own me.",   "sequence_order": 4},
        ]
        db, chain = _mock_db(rows)
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.get("/takes/take-1/fountain")
        assert res.status_code == 200
        text = res.text
        assert ".INT. DINER - NIGHT" in text
        assert "!Marla enters." in text
        assert "@MARLA" in text
        assert "You don't own me." in text

    def test_content_type_is_plain_text(self, client):
        db, chain = _mock_db([])
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.get("/takes/take-1/fountain")
        assert res.status_code == 200
        assert "text/plain" in res.headers["content-type"]

    def test_unix_line_endings(self, client):
        rows = [
            {"comp_type": "ACTION", "content": "Line 1.", "sequence_order": 1},
            {"comp_type": "ACTION", "content": "Line 2.", "sequence_order": 2},
        ]
        db, chain = _mock_db(rows)
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.get("/takes/take-1/fountain")
        assert "\r" not in res.text

    def test_note_uses_double_brackets(self, client):
        rows = [{"comp_type": "NOTE", "content": "reminder", "sequence_order": 1}]
        db, chain = _mock_db(rows)
        with patch("src.api.editor.get_supabase", return_value=db):
            res = client.get("/takes/take-1/fountain")
        assert "[[reminder]]" in res.text


# ---------------------------------------------------------------------------
# GET /editor — serves the HTML page
# ---------------------------------------------------------------------------

class TestEditorPage:
    def test_returns_html(self, client):
        res = client.get("/editor")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "workbench" in res.text.lower()
