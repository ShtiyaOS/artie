"""
The Script Supervisor — diagnosis agent wrapper.

docs/04_agent_roster.md §4   — responsibilities, output contract, model
docs/05_orchestration.md §1  — flat topology, peer of Artie and Director
docs/05_orchestration.md §5.1 — Backend → Supervisor payload contract
docs/05_orchestration.md §5.2 — Supervisor → Backend output contract

The Supervisor is a SequentialAgent pipeline (per docs/05_orchestration.md §1):
  canon check → cell judgments → verdict assembly

Placeholder: the pipeline steps are stubbed as a single LlmAgent that
returns structured JSON in the Supervisor output contract format.
Full SequentialAgent pipeline is implemented in later tasks.

Provenance event emitted by the wrapper: SCENE_DIAGNOSED.
The agent never emits its own provenance events.

Output contract (docs/04_agent_roster.md §4):
{
  "scene_id": "...",
  "position_id": int,
  "bible_version_id": int,
  "cell_verdicts": [...],    -- absent on continuity invocation
  "canon_findings": [...],   -- absent on continuity invocation
  "continuity_findings": [...] -- present only on check_continuity
}
"""

import json
import logging
import os
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner

from src.agents.runner import _adk_model, _build_message
from src.confluent_producer import publish_event


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent singleton
# ---------------------------------------------------------------------------

_agent: LlmAgent | None = None
_session_service: InMemorySessionService | None = None
_runner: Runner | None = None

APP_NAME = "supervisor"


def _get_runner() -> tuple[Runner, InMemorySessionService]:
    global _agent, _session_service, _runner
    if _runner is None:
        _agent = LlmAgent(
            name="supervisor",
            model=_adk_model("GEMINI_TEXT_MODEL"),
            instruction=(
                "You are the Script Supervisor. "
                "You receive a scene, the Project Bible, and a set of diagnostic cells. "
                "For each cell, emit SATISFIED, GAP, or NA with input_confidence. "
                "For world rules (S11), emit canon findings: rule_id, rule_type, "
                "status (VIOLATED or UNTRIGGERED), and detail. "
                "Respond with structured JSON matching the output contract exactly. "
                "For this task, return a stub JSON: {\"cell_verdicts\": []}. "
                "Never write prose, suggestions, rewrites, or corrections. "
                "Never address the writer. Speak to the backend only."
            ),
        )
        _session_service = InMemorySessionService()
        _runner = Runner(
            agent=_agent,
            app_name=APP_NAME,
            session_service=_session_service,
        )
    return _runner, _session_service


# ---------------------------------------------------------------------------
# Public invocation interface
# ---------------------------------------------------------------------------

async def invoke(
    *,
    payload: dict[str, Any],
    user_id: str,
    project_id: str | None = None,
    scene_id: str | None = None,
    bible_version_id: int = 0,
) -> str | None:
    """
    Invoke the Supervisor with a Backend → Supervisor payload
    (docs/05_orchestration.md §5.1).

    This implementation manually replicates the logic of invoke_agent in order
    to capture the event_id from publish_event and return it as diagnosis_id.

    Returns a JSON string: { "diagnosis_id": "...", "findings": { ... } }
    """
    runner, session_svc = _get_runner()
    input_text = json.dumps(payload)

    session = await session_svc.create_session(app_name=APP_NAME, user_id=user_id)
    message = _build_message(input_text)

    # Get agent response
    final_text: str | None = None
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

    # Publish provenance
    provenance_payload: dict[str, Any] = {
        "response_text": final_text,
        "position_id": payload.get("position_id"),
        "cell_count": len(payload.get("cells", [])),
    }

    diagnosis_id = publish_event(
        event_type="SCENE_DIAGNOSED",
        actor="supervisor",
        payload=provenance_payload,
        project_id=project_id,
        scene_id=scene_id,
        bible_version_id=bible_version_id,
    )
    
    # Per the prompt, the agent returns stubbed JSON, so we parse it.
    findings = json.loads(final_text) if final_text else {}

    # Assemble final response for the API
    return json.dumps({
        "diagnosis_id": diagnosis_id,
        "findings": findings,
    })
