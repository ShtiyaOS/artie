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
