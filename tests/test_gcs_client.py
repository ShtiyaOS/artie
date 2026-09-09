"""
Tests for the GCS client.
"""

import unittest
from unittest.mock import patch, MagicMock

from src import gcs_client

class TestGcsClient(unittest.TestCase):
    @patch.dict('os.environ', {'GCS_BUCKET_NAME': 'test-bucket'})
    @patch('src.gcs_client.storage.Client')
    def test_upload_asset(self, mock_storage_client):
        """Tests that upload_asset constructs the correct GCS path and calls the client."""
        # Assemble
        mock_client_instance = mock_storage_client.return_value
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client_instance.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        image_bytes = b'test-image'
        project_id = 'p1'
        scene_id = 's1'
        asset_id = 'a1'

        # Act
        gcs_uri = gcs_client.upload_asset(image_bytes, project_id, scene_id, asset_id)

        # Assert
        expected_path = f"projects/{project_id}/scenes/{scene_id}/{asset_id}.jpg"
        mock_storage_client.assert_called_once()
        mock_client_instance.bucket.assert_called_once_with('test-bucket')
        mock_bucket.blob.assert_called_once_with(expected_path)
        mock_blob.upload_from_string.assert_called_once_with(image_bytes, content_type="image/jpeg")
        self.assertEqual(gcs_uri, f"gs://test-bucket/{expected_path}")

    @patch.dict("os.environ", {}, clear=True)
    def test_upload_asset_no_bucket(self):
        """Tests that a ValueError is raised if the GCS_BUCKET_NAME is not set."""
        with self.assertRaises(ValueError):
            gcs_client.upload_asset(b'', '', '', '')
