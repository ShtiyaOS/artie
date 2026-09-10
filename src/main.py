"""
Artie backend — Cloud Run entry point.

Topology: flat event router. The backend receives events and invokes the
appropriate agent via Runner.run_async. Agents are peers; Artie is never
the parent of Supervisor or Director. See docs/05_orchestration.md §1.
"""

import json
import logging
import os
import threading
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.agents import artie
from src.blueprint import create_scene_one
from src.clickhouse_client import get_cell_definitions
from src.confluent_producer import publish_event
from src.supabase_client import get_client as get_supabase


logger = logging.getLogger(__name__)

app = FastAPI(title="artie-backend", docs_url=None, redoc_url=None)

# Static files (editor UI, test images, etc.)
_static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Editor workbench API
from src.api.editor import router as editor_router  # noqa: E402
app.include_router(editor_router)


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
# Editor UI — serves the workbench HTML page
# ---------------------------------------------------------------------------

@app.get("/editor")
async def editor_ui():
    """Serve the editor workbench HTML page."""
    path = os.path.join(os.path.dirname(__file__), "..", "static", "editor.html")
    return FileResponse(path, media_type="text/html")


# --------------------------------------------------------------------------
# Demo mode
# ---------------------------------------------------------------------------

@app.get("/demo")
async def demo():
    """
    Find or create the demo project, ensuring it has a scene, a take, and
    seeded components. Returns the IDs needed to load the editor.
    Idempotent.
    """
    db = get_supabase()

    # 1. Find or create the project.
    project_title = "Demo — The Long Way Back"
    project_res = db.table("projects").select("project_id").eq("working_title", project_title).limit(1).execute()

    if project_res.data:
        project_id = project_res.data[0]["project_id"]
    else:
        new_project_res = db.table("projects").insert({
            "working_title": project_title,
            "target_scene_count": 60,
            "current_bible_version": 1,
        }).execute()
        project_id = new_project_res.data[0]["project_id"]

    # 2. Find or create scene 1.
    scene_id = create_scene_one(project_id)

    # 3. Find or create a take.
    take_res = db.table("takes").select("take_id").eq("scene_id", scene_id).limit(1).execute()
    if take_res.data:
        take_id = take_res.data[0]["take_id"]
    else:
        new_take_res = db.table("takes").insert({
            "scene_id": scene_id,
            "take_number": 1,
        }).execute()
        take_id = new_take_res.data[0]["take_id"]
        
        # Seed components for the new take.
        components_to_seed = [
            {"take_id": take_id, "sequence_order": 1, "comp_type": "SCENE_HEADING", "content": "INT. DINER - NIGHT"},
            {"take_id": take_id, "sequence_order": 2, "comp_type": "ACTION", "content": "A man sits alone with cold coffee."},
            {"take_id": take_id, "sequence_order": 3, "comp_type": "CHARACTER", "content": "MARLA"},
            {"take_id": take_id, "sequence_order": 4, "comp_type": "DIALOGUE", "content": "You said you'd stop coming here."},
        ]
        db.table("script_components").insert(components_to_seed).execute()

    return JSONResponse({
        "project_id": project_id,
        "scene_id": scene_id,
        "take_id": take_id,
    })


# --------------------------------------------------------------------------
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

async def handle_scene_diagnosed(event: dict[str, Any]):
    """
    Handles a SCENE_DIAGNOSED event from the Supervisor.

    This is the "backend boundary" where prose is stripped.
    docs/05_orchestration.md §5.3
    """
    logger.info("Handling SCENE_DIAGNOSED event for scene %s", event.get("scene_id"))
    
    supervisor_payload = event.get("payload", {})

    # The payload from the supervisor via the event might be a JSON string.
    if isinstance(supervisor_payload, str):
        try:
            supervisor_payload = json.loads(supervisor_payload)
        except json.JSONDecodeError:
            logger.error("Failed to decode supervisor payload: %s", supervisor_payload)
            return

    # In Task 37, the supervisor response is wrapped in a 'findings' object.
    # The actual verdicts are inside response_text, which is another JSON string.
    response_text = supervisor_payload.get("response_text")
    if not response_text:
        logger.error("No 'response_text' in SCENE_DIAGNOSED payload.")
        return
        
    try:
        findings = json.loads(response_text)
    except json.JSONDecodeError:
        logger.error("Failed to decode 'response_text' from supervisor: %s", response_text)
        return

    verdicts = findings.get("cell_verdicts", [])
    if not verdicts:
        logger.info("No verdicts found in SCENE_DIAGNOSED event.")
        return

    # 1. Fetch cell definitions from ClickHouse
    cell_id_nums = [v["cell_id_num"] for v in verdicts]
    if not cell_id_nums:
        return
    cell_defs = get_cell_definitions(cell_id_nums)

    # 2. Transform verdicts into findings, stripping prose.
    CONFIDENCE_MAP = {"ATTESTED": 1, "ANCHORED": 2, "EXTRAPOLATED": 3}
    CONFIDENCE_MAP_INV = {v: k for k, v in CONFIDENCE_MAP.items()}

    def get_display_confidence(cell_confidence: str, input_confidence: str) -> str:
        if input_confidence == "PROVISIONAL":
            level = CONFIDENCE_MAP.get(cell_confidence, 3)
            new_level = min(level + 1, 3)
            return CONFIDENCE_MAP_INV.get(new_level, "EXTRAPOLATED")
        return cell_confidence

    pending_findings = []
    for verdict in verdicts:
        cell_id_num = verdict["cell_id_num"]
        cell_def = cell_defs.get(cell_id_num)
        if not cell_def:
            logger.warning("No cell definition found for cell_id_num %d", cell_id_num)
            continue
        
        cell_confidence = cell_def.get("confidence", "EXTRAPOLATED")
        input_confidence = verdict.get("input_confidence", "PROVISIONAL")

        pending_findings.append({
            "cell_id": cell_def["cell_id"],
            "verdict": verdict["verdict"],
            "cell_confidence": cell_confidence,
            "input_confidence": input_confidence,
            "display_confidence": get_display_confidence(cell_confidence, input_confidence),
            "priority_weight": cell_def["priority_weight"],
            "failure_signature": cell_def.get("failure_signature", f"Signature for {cell_def['cell_id']} not found."),
        })

    # 3. Construct payload for Artie.
    artie_payload = {
        "gate": "REVIEW",
        "bible_slots": {},
        "rig_slots": {},
        "pending_findings": pending_findings,
        "canon_findings": findings.get("canon_findings", []),
        "coverage_summary": {},
        "user_message": None, # This is a system event, not a user turn.
    }

    # 4. Invoke Artie.
    await artie.invoke(
        payload=artie_payload,
        user_id="system", # The event is from the system, not directly from a user.
        project_id=event.get("project_id"),
        scene_id=event.get("scene_id"),
        bible_version_id=event.get("bible_version_id", 0),
    )


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
    HANDLERS: dict[str, Any] = {
        "SCENE_DIAGNOSED": handle_scene_diagnosed,
    }

    handler = HANDLERS.get(event_type)
    if not handler:
        logger.debug("Ignoring event type: %s", event_type)
        return JSONResponse({"status": "ignored", "event_type": event_type}, status_code=200)

    await handler(body)
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


def _current_bible_version(project_id: str) -> int:
    """Fetch current_bible_version from Supabase, default 1."""
    try:
        r = (
            get_supabase()
            .table("projects")
            .select("current_bible_version")
            .eq("project_id", project_id)
            .single()
            .execute()
        )
        return r.data.get("current_bible_version", 1) if r.data else 1
    except Exception:
        return 1

@app.get("/project/{project_id}/gaps")
async def get_ranked_gaps(project_id: str, bible_version_id: int | None = None):
    """
    Retrieve the ranked gaps list for a project.

    Governed by docs/10_clickhouse.md §5.3.
    """
    from src.clickhouse_client import get_ranked_gaps as get_gaps_from_ch
    
    version = bible_version_id if bible_version_id is not None else _current_bible_version(project_id)
    
    # Environment guard for ClickHouse
    if not os.environ.get("CLICKHOUSE_HOST"):
        logger.warning("CLICKHOUSE_HOST not set; returning empty gaps list.")
        return JSONResponse([])

    gaps = get_gaps_from_ch(project_id, version)
    return JSONResponse(gaps)


@app.get("/project/{project_id}/heatmap")
async def get_heatmap(project_id: str, bible_version_id: int | None = None):
    """
    Retrieve the coverage heatmap for a project.

    Governed by docs/10_clickhouse.md §5.2.
    """
    from src.clickhouse_client import get_coverage_heatmap
    
    version = bible_version_id if bible_version_id is not None else _current_bible_version(project_id)
    
    # Environment guard for ClickHouse
    if not os.environ.get("CLICKHOUSE_HOST"):
        logger.warning("CLICKHOUSE_HOST not set; returning empty heatmap.")
        return JSONResponse([])

    heatmap = get_coverage_heatmap(project_id, version)
    return JSONResponse(heatmap)


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

    if response is None:
        return JSONResponse({"error": "agent invocation failed"}, status_code=500)

    return JSONResponse(response, status_code=200)


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

    if not project_id or not scene_id:
        return JSONResponse({"error": "project_id and scene_id are required"}, status_code=400)

    response = await director_invoke(
        payload=payload,
        user_id=user_id,
        project_id=project_id,
        scene_id=scene_id,
        bible_version_id=bible_version_id,
    )
    
    if response and response.get("error"):
        return JSONResponse(response, status_code=500)

    return JSONResponse(response)


# ---------------------------------------------------------------------------
# Scene Rig conversation — docs/03_scene_rig.md §1
# ---------------------------------------------------------------------------

@app.post("/scene_rig/{scene_id}/turn")
async def scene_rig_turn(scene_id: str, request: Request):
    """
    One writer turn in the Scene Rig conversation.

    Body: { "project_id": "<str>", "user_id": "<str>", "message": "<str>" }
    Returns: { "reply": str, "fills": [...], "done": bool }
    """
    from src.scene_rig_conversation import scene_rig_turn as _rig_turn

    body = await request.json()
    project_id = body.get("project_id", "")
    user_id    = body.get("user_id", "anonymous")
    message    = body.get("message", "")

    result = await _rig_turn(
        scene_id=scene_id,
        project_id=project_id,
        user_id=user_id,
        user_message=message,
    )
    return JSONResponse(result, status_code=200)


# ---------------------------------------------------------------------------
# Greenlight conversation — docs/02_greenlight.md §1
# ---------------------------------------------------------------------------

@app.post("/greenlight/{project_id}/turn")
async def greenlight_turn(project_id: str, request: Request):
    """
    One writer turn in the Greenlight conversation.

    Body: { "user_id": "<str>", "message": "<str>" }
    Returns: { "reply": str, "fills": [...], "done": bool, "committed": bool }
    """
    from src.greenlight_conversation import greenlight_turn as _gl_turn

    body = await request.json()
    user_id = body.get("user_id", "anonymous")
    message = body.get("message", "")

    result = await _gl_turn(
        project_id=project_id,
        user_id=user_id,
        user_message=message,
    )
    return JSONResponse(result, status_code=200)
