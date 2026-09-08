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
# ---------------------------------------------------------------------------

FORBIDDEN_KEYS = {
    "scene_text", "script", "prose", "evidence",
    "action_lines", "dialogue", "draft", "content",
}


class FirewallBreach(ValueError):
    """Raised when a prose field reaches Artie's payload."""


def assert_no_prose(payload: dict, path: str = "") -> None:
    """
    Walk the payload recursively and raise FirewallBreach if any key from
    FORBIDDEN_KEYS is present.

    Must raise, never sanitize — silent stripping lets the wiring drift
    undetected (docs/05_orchestration.md §6).
    """
    for k, v in payload.items():
        here = f"{path}.{k}" if path else k
        if k in FORBIDDEN_KEYS:
            raise FirewallBreach(
                f"Prose field '{here}' reached Artie's payload"
            )
        if isinstance(v, dict):
            assert_no_prose(v, here)
        if isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    assert_no_prose(item, f"{here}[{i}]")


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
) -> str | None:
    """
    Invoke Artie with a Backend → Artie payload (docs/05_orchestration.md §5.3).

    Raises FirewallBreach if the payload contains any prose field.
    Returns Artie's final response text.
    """
    assert_no_prose(payload)

    runner, session_svc = _get_runner()
    input_text = json.dumps(payload)

    return await invoke_agent(
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
