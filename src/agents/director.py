"""
The Director — visualization agent wrapper.

docs/04_agent_roster.md §5   — responsibilities, isolation rule, model
docs/05_orchestration.md §1  — flat topology, peer of Artie and Supervisor
docs/05_orchestration.md §5.4 — Backend → Director payload contract

The Director is a SequentialAgent pipeline (per docs/05_orchestration.md §1):
  prompt construction → image generation → assumption note

Isolation rule (docs/04_agent_roster.md §5): the Director reads Action lines only —
no dialogue, no Bible, no Rig slots. The payload contract enforces this.

Provenance event emitted by the wrapper: FRAME_PROMPT_CONSTRUCTED.
FRAME_GENERATED is emitted when the image pipeline runs (later task).
The agent never emits its own provenance events.
"""

import json
import logging
import os
import re
from typing import Any, Coroutine

from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner

from src.agents.runner import _adk_model, invoke_agent

logger = logging.getLogger(__name__)

APP_NAME = "director"

# --------------------------------------------------------------------------
# Prompt Construction Pipeline
# --------------------------------------------------------------------------

def _parse_scene_heading(scene_heading: str) -> dict[str, str]:
    """Parses a scene heading like 'INT. LOCATION - TIME' into a dict."""
    scene_heading = scene_heading.upper()
    interiority = "interior"
    if "EXT." in scene_heading:
        interiority = "exterior"

    location_match = re.search(r'(INT|EXT)\.\s*([^\-]+) -\s*(.*)', scene_heading)
    if location_match:
        location = location_match.group(2).strip()
        time_of_day = location_match.group(3).strip()
    else: # Handle simple headings like "INT. APARTMENT"
        location_match = re.search(r'(INT|EXT)\.\s*(.*)', scene_heading)
        location = location_match.group(2).strip() if location_match else "Unknown"
        time_of_day = "DAY" # Default

    return {"interiority": interiority, "location": location, "time_of_day": time_of_day}

def _normalize_capitalization(text: str) -> str:
    """Converts ALL-CAPS words to title case, otherwise leaves as is."""
    return ' '.join([word.title() if word.isupper() and len(word) > 1 else word for word in text.split()])

async def _call_llm_for_step(instruction: str, text: str) -> str:
    """Helper to call a one-shot LLM for a pipeline step."""
    agent = LlmAgent(
        name="director_step",
        model=_adk_model("GEMINI_TEXT_MODEL"),
        instruction=instruction
    )
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="director_step_runner",
        session_service=session_service,
    )
    # The user_id is ephemeral for these internal calls.
    return await invoke_agent(
        runner=runner,
        session_service=session_service,
        app_name="director_step_runner",
        user_id="director_pipeline",
        input_text=text,
        event_type="DIRECTOR_PIPELINE_STEP", # Internal event, not for provenance
        actor="director",
    ) or ""

async def _construct_prompt(payload: dict[str, Any]) -> dict[str, str]:
    """
    Constructs the image prompt and assumption note via the six-step pipeline.
    """
    action_lines = payload.get("action_lines", [])
    scene_heading_str = payload.get("scene_heading", "")
    assumption_notes = []

    # 1. Extract
    scene_heading_data = _parse_scene_heading(scene_heading_str)
    action_text = " ".join(action_lines)

    # 2. Normalize capitalization
    action_text = _normalize_capitalization(action_text)
    assumption_notes.append("Capitalization normalized.")

    # 3. Select the moment
    instruction_select_moment = "You are given a piece of action from a screenplay. Select the single most important, photographable moment from the text. Output only the description of that single moment."
    action_text = await _call_llm_for_step(instruction_select_moment, action_text)
    assumption_notes.append(f"Moment selected: \"{action_text}\"")

    # 4. Drop interiority
    instruction_drop_interiority = "You are given a piece of action from a screenplay. Remove any unfilmable interior thoughts or feelings. Output only the filmable action."
    action_text = await _call_llm_for_step(instruction_drop_interiority, action_text)
    assumption_notes.append("Interiority (thoughts/feelings) removed.")

    # 5. Apply fixed baseline framing
    baseline_framing = "cinematic still, natural framing, 35mm lens equivalent, lighting consistent with the described time and location, no text, lettering, captions, or writing anywhere in the image"
    
    # 6. Restrain violence
    instruction_restrain_violence = "You are given a piece of action from a screenplay. If it contains graphic violence, rewrite it to be less graphic and suggestive, suitable for a general audience. If there is no violence, return the original text."
    action_text = await _call_llm_for_step(instruction_restrain_violence, action_text)
    assumption_notes.append("Violent content restrained if present.")
    
    prompt = f"{action_text}, in a {scene_heading_data['location']}, {scene_heading_data['interiority']}, {scene_heading_data['time_of_day']}. {baseline_framing}"

    return {"prompt": prompt, "assumption_note": " ".join(assumption_notes)}

# --------------------------------------------------------------------------
# Public invocation interface
# --------------------------------------------------------------------------

_agent: LlmAgent | None = None
_session_service: InMemorySessionService | None = None
_runner: Runner | None = None

def _get_runner() -> tuple[Runner, InMemorySessionService]:
    global _agent, _session_service, _runner
    if _runner is None:
        _agent = LlmAgent(
            name="director",
            model=_adk_model("GEMINI_TEXT_MODEL"),
            instruction=(
                "You are the final step in a prompt construction pipeline. "
                "You will receive a fully formed image prompt and an assumption note in a JSON object. "
                "Your task is to return this JSON object verbatim. "
                "Do not add, remove, or change anything."
            ),
        )
        _session_service = InMemorySessionService()
        _runner = Runner(
            agent=_agent,
            app_name=APP_NAME,
            session_service=_session_service,
        )
    return _runner, _session_service

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
      scene_heading: str        — The scene heading
      character_refs: list[dict] — optional, canonical_frame_uri per character

    Returns the Director's JSON response text (prompt + assumption_note).
    Provenance event FRAME_PROMPT_CONSTRUCTED is emitted by the wrapper.
    """
    prompt_data = await _construct_prompt(payload)
    input_text = json.dumps(prompt_data)
    
    runner, session_svc = _get_runner()

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
            "constructed_prompt": prompt_data["prompt"],
            "assumption_note": prompt_data["assumption_note"],
        },
    )
