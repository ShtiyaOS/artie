import unittest
from unittest.mock import MagicMock, patch

from src.clickhouse_client import get_coverage_heatmap


class TestClickHouseClient(unittest.TestCase):
    @patch("src.clickhouse_client.get_client")
    def test_get_coverage_heatmap(self, mock_get_client):
        # Arrange
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_result = MagicMock()
        mock_result.column_names = [
            "cell_id",
            "position",
            "lens",
            "coverage_state",
            "cell_confidence",
            "input_confidence",
            "display_confidence",
        ]
        # Create 72 rows of dummy data
        mock_result.result_rows = [
            (
                f"X{p:02d}.Y{l}",
                f"X{p:02d}",
                f"Y{l}",
                "NO_DATA",
                "ATTESTED",
                "NONE",
                "ATTESTED",
            )
            for p in range(1, 13)
            for l in range(1, 7)
        ]
        mock_client.query.return_value = mock_result

        project_id = "test_project"
        bible_version_id = 1

        # Act
        result = get_coverage_heatmap(project_id, bible_version_id)

        # Assert
        self.assertEqual(len(result), 72)
        self.assertEqual(
            list(result[0].keys()),
            [
                "cell_id",
                "position",
                "lens",
                "coverage_state",
                "cell_confidence",
                "input_confidence",
                "display_confidence",
            ],
        )
        mock_client.query.assert_called_once()
        # We can also assert the query itself if we want to be more specific
        called_query = mock_client.query.call_args[0][0]
        self.assertIn("WITH latest AS", called_query)
        self.assertIn("fresh AS", called_query)
        self.assertIn("per_cell AS", called_query)
        self.assertIn("ORDER BY c.position_id, c.lens_id", called_query)


if __name__ == "__main__":
    unittest.main()
