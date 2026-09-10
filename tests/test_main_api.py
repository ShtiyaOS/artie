
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

class TestDemoEndpoint:
    @patch("src.main.get_supabase")
    @patch("src.main.create_scene_one")
    def test_demo_creates_new_project_and_take(self, mock_create_scene_one, mock_get_supabase):
        # Arrange
        mock_db = MagicMock()
        mock_get_supabase.return_value = mock_db
        mock_create_scene_one.return_value = "test-scene-id"

        # Mock the chained calls to execute()
        
        # The sequence of execute calls is:
        # 1. select project -> empty
        # 2. insert project -> new-project-id
        # 3. select take -> empty
        # 4. insert take -> new-take-id
        # 5. insert components -> empty
        
        # This mock will be the return value for *all* `execute()` calls in the endpoint
        execute_mock = MagicMock()
        execute_mock.side_effect = [
            MagicMock(data=[]),  # 1. select project
            MagicMock(data=[{"project_id": "new-project-id"}]),  # 2. insert project
            MagicMock(data=[]),  # 3. select take
            MagicMock(data=[{"take_id": "new-take-id"}]),  # 4. insert take
            MagicMock(data=[]),  # 5. insert components
        ]

        # When table() is called, we return a mock that has all the subsequent calls mocked
        # out to eventually call our execute_mock
        table_mock = MagicMock()
        
        # Route all `select` and `insert` chains to the same `execute` mock
        table_mock.select.return_value.eq.return_value.limit.return_value.execute = execute_mock
        table_mock.insert.return_value.execute = execute_mock
        mock_db.table.return_value = table_mock
        
        # Act
        response = client.get("/demo")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "new-project-id"
        assert data["scene_id"] == "test-scene-id"
        assert data["take_id"] == "new-take-id"

        assert execute_mock.call_count == 5
        mock_create_scene_one.assert_called_once_with("new-project-id")

    @patch("src.main.get_supabase")
    @patch("src.main.create_scene_one")
    def test_demo_returns_existing_project_and_take(self, mock_create_scene_one, mock_get_supabase):
        # Arrange
        mock_db = MagicMock()
        mock_get_supabase.return_value = mock_db
        mock_create_scene_one.return_value = "existing-scene-id"

        # Mock project and take found
        execute_mock = MagicMock()
        execute_mock.side_effect = [
            MagicMock(data=[{"project_id": "existing-project-id"}]),
            MagicMock(data=[{"take_id": "existing-take-id"}]),
        ]
        
        table_mock = MagicMock()
        table_mock.select.return_value.eq.return_value.limit.return_value.execute = execute_mock
        mock_db.table.return_value = table_mock

        # Act
        response = client.get("/demo")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "existing-project-id"
        assert data["scene_id"] == "existing-scene-id"
        assert data["take_id"] == "existing-take-id"

        # Ensure no new data was inserted
        table_mock.insert.assert_not_called()
        mock_create_scene_one.assert_called_once_with("existing-project-id")


class TestGetHeatmap:
    @patch.dict("os.environ", {"CLICKHOUSE_HOST": "test-host"})
    @patch("src.main._current_bible_version", return_value=1)
    @patch("src.clickhouse_client.get_coverage_heatmap")
    def test_get_heatmap_returns_data(self, mock_get_heatmap, mock_bible_version):
        # Arrange
        project_id = "test-project"
        bible_version_id = 1
        heatmap_data = [
            {"cell_id": "X01-Y1", "coverage_state": "SATISFIED", "display_confidence": "ATTESTED"},
            {"cell_id": "X01-Y2", "coverage_state": "GAP", "display_confidence": "ANCHORED"},
        ]
        mock_get_heatmap.return_value = heatmap_data

        # Act
        response = client.get(f"/project/{project_id}/heatmap")

        # Assert
        assert response.status_code == 200
        assert response.json() == heatmap_data
        mock_get_heatmap.assert_called_once_with(project_id, bible_version_id)
        mock_bible_version.assert_called_once_with(project_id)

    @patch.dict("os.environ", {"CLICKHOUSE_HOST": "test-host"})
    @patch("src.main._current_bible_version", return_value=2)
    @patch("src.clickhouse_client.get_coverage_heatmap")
    def test_get_heatmap_with_explicit_bible_version(self, mock_get_heatmap, mock_bible_version):
        # Arrange
        project_id = "test-project"
        bible_version_id = 5
        heatmap_data = [{"cell_id": "X02-Y1", "coverage_state": "NA"}]
        mock_get_heatmap.return_value = heatmap_data

        # Act
        response = client.get(f"/project/{project_id}/heatmap?bible_version_id={bible_version_id}")

        # Assert
        assert response.status_code == 200
        assert response.json() == heatmap_data
        mock_get_heatmap.assert_called_once_with(project_id, bible_version_id)
        # _current_bible_version should not be called when the version is specified
        mock_bible_version.assert_not_called()
