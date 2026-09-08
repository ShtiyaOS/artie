"""
Acceptance test for Task 16.

Publishes a SESSION_OPENED event via the Cloud Run endpoint, then polls
ClickHouse for up to 30 seconds to confirm the row landed in provenance_events.

Requires provenance_events table to exist (sql/20_provenance_events.sql).
"""

import os
import time
import uuid

import requests
from dotenv import load_dotenv
import clickhouse_connect

load_dotenv()

SERVICE_URL = "https://artie-109916792184.us-central1.run.app"

project_id = str(uuid.uuid4())

print(f"POST {SERVICE_URL}/session/open  project_id={project_id}")
resp = requests.post(
    f"{SERVICE_URL}/session/open",
    json={"project_id": project_id, "slug_line": "INT. TEST ROOM - DAY"},
    timeout=15,
)
print(f"  → {resp.status_code} {resp.json()}")
assert resp.status_code == 202, f"Expected 202, got {resp.status_code}"
session_id = resp.json()["session_id"]

ch = clickhouse_connect.get_client(
    host=os.environ["CLICKHOUSE_HOST"],
    port=int(os.environ["CLICKHOUSE_PORT"]),
    username=os.environ["CLICKHOUSE_USER"],
    password=os.environ["CLICKHOUSE_PASSWORD"],
    secure=os.environ.get("CLICKHOUSE_SECURE", "true").lower() == "true",
)

print(f"Polling ClickHouse for session_id={session_id} (up to 30 s)…")
deadline = time.time() + 30
found = False
while time.time() < deadline:
    rows = ch.query(
        "SELECT event_id, event_type, actor, ingested_at "
        "FROM provenance_events "
        "WHERE JSONExtractString(payload, 'session_id') = %(sid)s",
        parameters={"sid": session_id},
    ).result_rows
    if rows:
        print(f"  ✓ Found {len(rows)} row(s): {rows[0]}")
        found = True
        break
    time.sleep(2)

if not found:
    print("  ✗ Row not found within 30 s")
    raise SystemExit(1)

print("Acceptance criterion MET.")
