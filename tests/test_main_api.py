
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

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
