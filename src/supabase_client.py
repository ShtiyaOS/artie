"""
Supabase singleton client.

Uses the secret key, which bypasses RLS (docs/11_supabase.md §3).
Connection config mirrors scripts/test_supabase.py exactly.
"""

import os

from supabase import Client, create_client

_client: Client | None = None


def get_client() -> Client:
    """Return the singleton Supabase client, creating it on first call."""
    global _client
    if _client is None:
        _client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SECRET_KEY"],
        )
    return _client

def create_asset_record(scene_id: str, gcs_uri: str, model: str, prompt: str, assumption_note: str, finish_reason: str) -> dict:
    """Creates an asset record in the assets table."""
    client = get_client()
    response = client.table("assets").insert({
        "scene_id": scene_id,
        "gcs_uri": gcs_uri,
        "model": model,
        "prompt": prompt,
        "assumption_note": assumption_note,
        "finish_reason": finish_reason,
    }).execute()
    return response.data[0]
