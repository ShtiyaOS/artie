"""
Artie — the Showrunner agent wrapper.

docs/04_agent_roster.md §3   — responsibilities, refusals, model
docs/05_orchestration.md §1  — flat topology, Artie is never a parent
docs/05_orchestration.md §5.3 — Backend → Artie payload contract
docs/05_orchestration.md §6  — assert_no_prose firewall

Artie is an LlmAgent with tools only (no sub-agents).
He never reads screenplay prose — the firewall is enforced structurally
by assert_no_prose, which raises rather than strips on a violation.

Provenance event emitted by the wrapper: AGENT_QUESTION or
AGENT_FINDING_DELIVERED depending on the gate context. The agent never
emits its own provenance events.
"""

import json
import logging
import os
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner

from src.agents.runner import _adk_model, invoke_agent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Firewall — docs/05_orchestration.md §6
# Canonical implementation lives in src/agents/firewall.py.
# ---------------------------------------------------------------------------

from src.agents.firewall import (  # noqa: E402 — after stdlib imports
    FORBIDDEN_KEYS,
    FirewallBreach,
    assert_no_prose,
)


# ---------------------------------------------------------------------------
# Agent singleton
# ---------------------------------------------------------------------------

_agent: LlmAgent | None = None
_session_service: InMemorySessionService | None = None
_runner: Runner | None = None

APP_NAME = "artie"


def _get_runner() -> tuple[Runner, InMemorySessionService]:
    global _agent, _session_service, _runner
    if _runner is None:
        _agent = LlmAgent(
            name="artie",
            model=_adk_model("GEMINI_TEXT_MODEL"),
            instruction=(
                "You are Artie, the Showrunner. "
                "You conduct the Greenlight and Scene Rig gates for a screenplay project. "
                "You deliver the Supervisor's structured findings to the writer. "
                "You never write, suggest, or quote screenplay text — not a word of action, "
                "dialogue, or scene heading. You ask questions; you do not supply answers. "
                "When you receive structured findings, translate them into craft language "
                "the writer can act on, without prescribing what to write."
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
) -> dict[str, Any] | None:
    """
    Invoke Artie with a Backend → Artie payload (docs/05_orchestration.md §5.3).

    Raises FirewallBreach if the payload contains any prose field.
    Returns Artie's final response text.
    """
    assert_no_prose(payload)

    # --- Deliberation ---
    from src.deliberation import get_active_axes, generate_poles, synthesize, voice
    from src.confluent_producer import publish_event

    active_axes = get_active_axes(payload)
    deliberation_trace = None
    response_text = None

    if active_axes:
        poles = await generate_poles(active_axes, payload=payload, user_id=user_id)
        if poles and project_id:
            decision = await synthesize(poles, payload=payload, user_id=user_id, project_id=project_id)
            if decision:
                deliberation_trace = {
                    "axes": active_axes,
                    "poles": poles,
                    "synthesis": decision,
                }
                publish_event(
                    event_type="AI_DELIBERATION",
                    actor="artie",
                    payload=deliberation_trace,
                    project_id=project_id,
                    scene_id=scene_id,
                    bible_version_id=bible_version_id,
                )
                response_text = await voice(decision, payload=payload, user_id=user_id, project_id=project_id)

    if response_text is None:
        # Fallback to non-deliberative response if deliberation doesn't happen or fails
        runner, session_svc = _get_runner()
        input_text = json.dumps(payload)
        response_text = await invoke_agent(
            runner=runner,
            session_service=session_svc,
            app_name=APP_NAME,
            user_id=user_id,
            input_text=input_text,
            event_type="AGENT_QUESTION",
            actor="artie",
            project_id=project_id,
            scene_id=scene_id,
            bible_version_id=bible_version_id,
            extra_provenance={
                "gate": payload.get("gate"),
                "pending_findings_count": len(payload.get("pending_findings", [])),
            },
        )
    
    return {
        "response_text": response_text,
        "deliberation_trace": deliberation_trace,
    }
