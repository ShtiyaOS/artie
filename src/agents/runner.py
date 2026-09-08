"""
Shared agent runner infrastructure.

Every agent invocation goes through `invoke_agent`:
  1. Calls Runner.run_async with the synthetic message
  2. Collects the final response text
  3. Emits the corresponding provenance event (the agent never does this itself)

Each agent gets its own Runner bound to its own InMemorySessionService.
Sessions are per-invocation (ephemeral); durable state lives in Supabase.

docs/05_orchestration.md §1 — flat topology, backend orchestrates
docs/09_provenance_ledger.md §3.2 — agent events stored in full
"""

import asyncio
import json
import logging
import os
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.confluent_producer import publish_event

logger = logging.getLogger(__name__)


def _adk_model(env_key: str) -> str:
    """
    Return the ADK-compatible model name for the given env var.

    ADK's LLMRegistry matches 'gemini-.*' — the 'models/' prefix used in
    the Gemini API is stripped here once, centrally.
    """
    return os.environ[env_key].removeprefix("models/")


def _build_message(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


async def invoke_agent(
    *,
    runner: Runner,
    session_service: InMemorySessionService,
    app_name: str,
    user_id: str,
    input_text: str,
    event_type: str,
    actor: str,
    project_id: str | None = None,
    scene_id: str | None = None,
    bible_version_id: int = 0,
    extra_provenance: dict[str, Any] | None = None,
) -> str | None:
    """
    Run one agent invocation and emit the provenance event.

    Returns the final response text, or None if the agent produced no output.
    Raises on runner error — callers decide whether to retry.

    Provenance is emitted after a successful run; on error the caller's
    exception propagates before publish_event is reached, so no misleading
    event is recorded.
    """
    session = await session_service.create_session(
        app_name=app_name, user_id=user_id
    )
    message = _build_message(input_text)

    final_text: str | None = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

    # Provenance — emitted by the wrapper, never by the agent (§09 rule)
    provenance_payload: dict[str, Any] = {"response_text": final_text}
    if extra_provenance:
        provenance_payload.update(extra_provenance)

    publish_event(
        event_type=event_type,
        actor=actor,
        payload=provenance_payload,
        project_id=project_id,
        scene_id=scene_id,
        bible_version_id=bible_version_id,
    )

    return final_text


def run_agent(
    *,
    runner: Runner,
    session_service: InMemorySessionService,
    app_name: str,
    user_id: str,
    input_text: str,
    event_type: str,
    actor: str,
    project_id: str | None = None,
    scene_id: str | None = None,
    bible_version_id: int = 0,
    extra_provenance: dict[str, Any] | None = None,
) -> str | None:
    """Synchronous wrapper around invoke_agent for non-async callers."""
    return asyncio.run(
        invoke_agent(
            runner=runner,
            session_service=session_service,
            app_name=app_name,
            user_id=user_id,
            input_text=input_text,
            event_type=event_type,
            actor=actor,
            project_id=project_id,
            scene_id=scene_id,
            bible_version_id=bible_version_id,
            extra_provenance=extra_provenance,
        )
    )
