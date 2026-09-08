"""
Artie backend — Cloud Run entry point.

Topology: flat event router. The backend receives events and invokes the
appropriate agent via Runner.run_async. Agents are peers; Artie is never
the parent of Supervisor or Director. See docs/05_orchestration.md §1.
"""

import os
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.confluent_producer import publish_event

app = FastAPI(title="artie-backend", docs_url=None, redoc_url=None)


# ---------------------------------------------------------------------------
# Health check — required by Cloud Run
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Session — state events (docs/09_provenance_ledger.md §3.3)
# ---------------------------------------------------------------------------

@app.post("/session/open")
async def session_open(request: Request):
    """
    Publish SESSION_OPENED to authorship.events.

    Accepts optional JSON body:
      { "project_id": "<uuid>", "slug_line": "<text>" }

    Both fields are optional; defaults are generated/empty when absent.
    """
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    session_id = str(uuid.uuid4())
    project_id = body.get("project_id") or str(uuid.uuid4())
    slug_line = body.get("slug_line", "")

    publish_event(
        event_type="SESSION_OPENED",
        actor="system",
        payload={"session_id": session_id, "slug_line": slug_line},
        project_id=project_id,
    )

    return JSONResponse(
        {"status": "accepted", "session_id": session_id, "project_id": project_id},
        status_code=202,
    )


# ---------------------------------------------------------------------------
# Event router — receives Confluent event payloads forwarded by the backend
# consumer and dispatches to the correct agent.
#
# Agent invocations are implemented in later tasks (18+). Stubs are
# registered here so the router has a place to grow without structural
# changes.
# ---------------------------------------------------------------------------

@app.post("/events")
async def receive_event(request: Request):
    """
    Accepts a JSON event envelope (docs/05_orchestration.md §2) and routes it.

    Populated incrementally by Tasks 15–18; returns 202 for any recognized
    event_type and 400 for unknown types.
    """
    body = await request.json()
    event_type = body.get("event_type")

    # Route map is extended as tasks are implemented.
    HANDLERS: dict[str, str] = {
        # Task 15+: "SESSION_OPENED": handle_session_opened,
    }

    if event_type not in HANDLERS:
        return JSONResponse({"error": f"unknown event_type: {event_type}"}, status_code=400)

    # handler = HANDLERS[event_type]
    # await handler(body)
    return JSONResponse({"status": "accepted"}, status_code=202)
