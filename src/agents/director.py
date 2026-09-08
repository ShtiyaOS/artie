"""
The Director — visualization agent wrapper.

docs/04_agent_roster.md §5   — responsibilities, isolation rule, model
docs/05_orchestration.md §1  — flat topology, peer of Artie and Supervisor
docs/05_orchestration.md §5.4 — Backend → Director payload contract

The Director is a SequentialAgent pipeline (per docs/05_orchestration.md §1):
  prompt construction → image generation → assumption note

Placeholder: the pipeline steps are stubbed as a single LlmAgent that
constructs the image prompt and assumption note without calling the image
model. Full image generation pipeline is implemented in later tasks.

Isolation rule (docs/04_agent_roster.md §5): the Director reads Action lines only —
no dialogue, no Bible, no Rig slots. The payload contract enforces this.

Provenance event emitted by the wrapper: FRAME_PROMPT_CONSTRUCTED.
FRAME_GENERATED is emitted when the image pipeline runs (later task).
The agent never emits its own provenance events.
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
# Agent singleton
# ---------------------------------------------------------------------------

_agent: LlmAgent | None = None
_session_service: InMemorySessionService | None = None
_runner: Runner | None = None

APP_NAME = "director"


def _get_runner() -> tuple[Runner, InMemorySessionService]:
    global _agent, _session_service, _runner
    if _runner is None:
        _agent = LlmAgent(
            name="director",
            model=_adk_model("GEMINI_TEXT_MODEL"),
            instruction=(
                "You are the Director. "
                "You receive Action lines from a screenplay scene. "
                "You construct a detailed image prompt for a storyboard frame. "
                "Apply these transformations: strip screenplay formatting and lowercase the action; "
                "instruct no text or lettering in the image; add shot size, angle, lens, lighting, "
                "time of day, and 'cinematic' framing; select a single photographable instant; "
                "externalize any interiority; restrain violent content. "
                "After the prompt, write a brief assumption note explaining what the model "
                "will fill in where the description ran out — be specific about invented details. "
                "Respond with JSON: {\"prompt\": \"...\", \"assumption_note\": \"...\"}. "
                "You have no knowledge of the Project Bible, Rig slots, or anything "
                "outside the Action lines provided."
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
    Invoke the Director with a Backend → Director payload
    (docs/05_orchestration.md §5.4).

    Payload must contain:
      action_lines: list[str]   — Action elements only, no dialogue
      character_refs: list[dict] — optional, canonical_frame_uri per character

    Returns the Director's JSON response text (prompt + assumption_note).
    Provenance event FRAME_PROMPT_CONSTRUCTED is emitted by the wrapper.
    """
    runner, session_svc = _get_runner()
    input_text = json.dumps(payload)

    return await invoke_agent(
        runner=runner,
        session_service=session_svc,
        app_name=APP_NAME,
        user_id=user_id,
        input_text=input_text,
        event_type="FRAME_PROMPT_CONSTRUCTED",
        actor="director",
        project_id=project_id,
        scene_id=scene_id,
        bible_version_id=bible_version_id,
        extra_provenance={
            "action_line_count": len(payload.get("action_lines", [])),
            "character_ref_count": len(payload.get("character_refs", [])),
        },
    )
