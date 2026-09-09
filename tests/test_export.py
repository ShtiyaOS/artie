"""
Test the export module.
"""

import unittest
from unittest.mock import patch, MagicMock

from src.export import export_script


import unittest
from unittest.mock import patch, MagicMock

from src.export import export_script


class TestExport(unittest.TestCase):
    @patch("src.export.get_supabase")
    @patch("src.export.publish_event")
    @patch("src.export.pdf")
    @patch("src.export.fdx")
    @patch("src.export.f")
    def test_export_script_pdf(self, mock_f, mock_fdx, mock_pdf, mock_publish_event, mock_get_supabase):
        # Arrange
        project_id = "some-project-id"
        writer_name = "A. Writer"
        format = "pdf"

        # Mock Supabase client
        mock_supabase_client = MagicMock()
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"value": "My Awesome Script"}]
        mock_supabase_client.rpc.return_value.execute.return_value.data = [
            {"comp_type": "SCENE_HEADING", "content": "INT. TEST ROOM - DAY"},
            {"comp_type": "ACTION", "content": "This is a test."},
        ]
        mock_get_supabase.return_value = mock_supabase_client

        # Mock screenplain
        mock_script = MagicMock()
        mock_f.parse.return_value = mock_script

        # Act
        output_bytes = export_script(project_id=project_id, writer_name=writer_name, format=format)

        # Assert
        mock_pdf.export.assert_called_once()
        mock_fdx.export.assert_not_called()
        mock_publish_event.assert_called_once()

    @patch("src.export.get_supabase")
    @patch("src.export.publish_event")
    @patch("src.export.pdf")
    @patch("src.export.fdx")
    @patch("src.export.f")
    def test_export_script_fdx(self, mock_f, mock_fdx, mock_pdf, mock_publish_event, mock_get_supabase):
        # Arrange
        project_id = "some-project-id"
        writer_name = "A. Writer"
        format = "fdx"

        # Mock Supabase client
        mock_supabase_client = MagicMock()
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"value": "My Awesome Script"}]
        mock_supabase_client.rpc.return_value.execute.return_value.data = [
            {"comp_type": "SCENE_HEADING", "content": "INT. TEST ROOM - DAY"},
            {"comp_type": "ACTION", "content": "This is a test."},
        ]
        mock_get_supabase.return_value = mock_supabase_client

        # Mock screenplain
        mock_script = MagicMock()
        mock_f.parse.return_value = mock_script

        # Act
        output_bytes = export_script(project_id=project_id, writer_name=writer_name, format=format)

        # Assert
        mock_fdx.export.assert_called_once()
        mock_pdf.export.assert_not_called()
        mock_publish_event.assert_called_once()

    @patch("src.export.get_supabase")
    @patch("src.export.publish_event")
    @patch("src.export.pdf")
    @patch("src.export.fdx")
    @patch("src.export.f")
    def test_export_script_fountain(self, mock_f, mock_fdx, mock_pdf, mock_publish_event, mock_get_supabase):
        # Arrange
        project_id = "some-project-id"
        writer_name = "A. Writer"
        format = "fountain"

        # Mock Supabase client
        mock_supabase_client = MagicMock()
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"value": "My Awesome Script"}]
        mock_supabase_client.rpc.return_value.execute.return_value.data = [
            {"comp_type": "SCENE_HEADING", "content": "INT. TEST ROOM - DAY"},
            {"comp_type": "ACTION", "content": "This is a test."},
        ]
        mock_get_supabase.return_value = mock_supabase_client

        # Act
        output_bytes = export_script(project_id=project_id, writer_name=writer_name, format=format)

        # Assert
        expected_fountain_doc = (
            "Title: My Awesome Script\n"
            "Credit: Written by\n"
            "Author: A. Writer\n"
            f"Draft date: {__import__('datetime').date.today().isoformat()}\n"
            "\n"
            "\n"
            ".INT. TEST ROOM - DAY\n"
            "\n"
            "!This is a test."
        )
        self.assertEqual(output_bytes.decode("utf-8"), expected_fountain_doc)
        mock_f.parse.assert_not_called()
        mock_pdf.export.assert_not_called()
        mock_fdx.export.assert_not_called()
        mock_publish_event.assert_called_once()


if __name__ == "__main__":
    unittest.main()
