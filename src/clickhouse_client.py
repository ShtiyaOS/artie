"""
ClickHouse singleton client.

Connection config mirrors scripts/test_clickhouse.py exactly.
"""

import os

import clickhouse_connect

_client = None


def get_client():
    """Return the singleton ClickHouse client, creating it on first call."""
    global _client
    if _client is None:
        _client = clickhouse_connect.get_client(
            host=os.environ["CLICKHOUSE_HOST"],
            port=int(os.environ["CLICKHOUSE_PORT"]),
            username=os.environ["CLICKHOUSE_USER"],
            password=os.environ["CLICKHOUSE_PASSWORD"],
            secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
        )
    return _client
