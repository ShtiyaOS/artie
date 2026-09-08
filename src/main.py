"""
Artie backend — Cloud Run entry point.

Topology: flat event router. The backend receives events and invokes the
appropriate agent via Runner.run_async. Agents are peers; Artie is never
the parent of Supervisor or Director. See docs/05_orchestration.md §1.
"""

import logging
import os
import threading
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.confluent_producer import publish_event
from src.supabase_client import get_client as get_supabase

logger = logging.getLogger(__name__)

app = FastAPI(title="artie-backend", docs_url=None, redoc_url=None)


# ---------------------------------------------------------------------------
# Provenance consumer — runs in a background thread alongside the API server.
# docs/09_provenance_ledger.md §8
# ---------------------------------------------------------------------------

@app.on_event("startup")
def _start_provenance_consumer():
    """Start the Confluent → ClickHouse consumer in a daemon thread."""
    # Guard: skip if any required env var is absent (e.g. local dev without CH)
    required = [
        "CONFLUENT_BOOTSTRAP_SERVERS",
        "CONFLUENT_API_KEY",
        "CONFLUENT_API_SECRET",
        "CONFLUENT_TOPIC",
        "CLICKHOUSE_HOST",
        "CLICKHOUSE_PASSWORD",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        logger.warning(
            "Provenance consumer NOT started — missing env vars: %s", missing
        )
        return

    from src.provenance_consumer import run as consumer_run

    t = threading.Thread(target=consumer_run, name="provenance-consumer", daemon=True)
    t.start()
    logger.info("Provenance consumer thread started")


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


# ---------------------------------------------------------------------------
# Projects — Supabase read (docs/11_supabase.md §2.1, §3)
# ---------------------------------------------------------------------------

@app.get("/project/{project_id}")
async def get_project(project_id: str):
    """
    Retrieve a project row from Supabase by project_id.

    Returns 404 when the project does not exist.
    """
    result = (
        get_supabase()
        .table("projects")
        .select("*")
        .eq("project_id", project_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return JSONResponse({"error": "project not found"}, status_code=404)
    return JSONResponse(result.data[0])


# ---------------------------------------------------------------------------
# Agent invocation endpoints — docs/05_orchestration.md §1
# Each agent is a peer; the backend orchestrates, never Artie.
# ---------------------------------------------------------------------------

@app.post("/invoke/artie")
async def invoke_artie(request: Request):
    """
    Invoke Artie with a Backend → Artie payload (docs/05_orchestration.md §5.3).

    Body: { "payload": {...}, "user_id": "...", "project_id": "...",
            "scene_id": "...", "bible_version_id": int }

    Raises 422 if the payload contains prose fields (firewall breach).
    """
    from src.agents.artie import invoke as artie_invoke, FirewallBreach

    body = await request.json()
    payload = body.get("payload", {})
    user_id = body.get("user_id", "anonymous")
    project_id = body.get("project_id")
    scene_id = body.get("scene_id")
    bible_version_id = int(body.get("bible_version_id", 0))

    try:
        response = await artie_invoke(
            payload=payload,
            user_id=user_id,
            project_id=project_id,
            scene_id=scene_id,
            bible_version_id=bible_version_id,
        )
    except FirewallBreach as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    return JSONResponse({"response": response}, status_code=200)


@app.post("/invoke/supervisor")
async def invoke_supervisor(request: Request):
    """
    Invoke the Supervisor with a Backend → Supervisor payload
    (docs/05_orchestration.md §5.1).

    Body: { "payload": {...}, "user_id": "...", "project_id": "...",
            "scene_id": "...", "bible_version_id": int }
    """
    from src.agents.supervisor import invoke as supervisor_invoke

    body = await request.json()
    payload = body.get("payload", {})
    user_id = body.get("user_id", "anonymous")
    project_id = body.get("project_id")
    scene_id = body.get("scene_id")
    bible_version_id = int(body.get("bible_version_id", 0))

    response = await supervisor_invoke(
        payload=payload,
        user_id=user_id,
        project_id=project_id,
        scene_id=scene_id,
        bible_version_id=bible_version_id,
    )
    return JSONResponse({"response": response}, status_code=200)


@app.post("/invoke/director")
async def invoke_director(request: Request):
    """
    Invoke the Director with a Backend → Director payload
    (docs/05_orchestration.md §5.4).

    Body: { "payload": { "action_lines": [...], "character_refs": [...] },
            "user_id": "...", "project_id": "...", "scene_id": "..." }
    """
    from src.agents.director import invoke as director_invoke

    body = await request.json()
    payload = body.get("payload", {})
    user_id = body.get("user_id", "anonymous")
    project_id = body.get("project_id")
    scene_id = body.get("scene_id")
    bible_version_id = int(body.get("bible_version_id", 0))

    response = await director_invoke(
        payload=payload,
        user_id=user_id,
        project_id=project_id,
        scene_id=scene_id,
        bible_version_id=bible_version_id,
    )
    return JSONResponse({"response": response}, status_code=200)
