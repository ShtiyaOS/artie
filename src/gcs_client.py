"""Client for Google Cloud Storage."""

import os
from google.cloud import storage

def upload_asset(image_bytes: bytes, project_id: str, scene_id: str, asset_id: str) -> str:
    """Uploads an image asset to GCS and returns the GCS URI."""
    BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
    if not BUCKET_NAME:
        raise ValueError("GCS_BUCKET_NAME environment variable not set.")

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    
    gcs_path = f"projects/{project_id}/scenes/{scene_id}/{asset_id}.jpg"
    blob = bucket.blob(gcs_path)
    
    blob.upload_from_string(image_bytes, content_type="image/jpeg")
    
    return f"gs://{BUCKET_NAME}/{gcs_path}"
