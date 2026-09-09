"""
The Director — visualization agent wrapper.

docs/04_agent_roster.md §5   — responsibilities, isolation rule, model
docs/05_orchestration.md §1  — flat topology, peer of Artie and Supervisor
docs/05_orchestration.md §5.4 — Backend → Director payload contract
docs/13_director_assets.md §5,8 — Image generation and failure handling.

The Director is a SequentialAgent pipeline (per docs/05_orchestration.md §1):
  prompt construction → image generation → assumption note

Isolation rule (docs/04_agent_roster.md §5): the Director reads Action lines only —
no dialogue, no Bible, no Rig slots. The payload contract enforces this.

Provenance events emitted:
- FRAME_PROMPT_CONSTRUCTED: emitted by `invoke()`
- FRAME_GENERATED: emitted by `generate_frame()`
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, Coroutine, Tuple

from google import genai
from google.adk.agents import LlmAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner

from src.agents.runner import _adk_model, invoke_agent
import uuid
from src import gcs_client
from src import supabase_client


logger = logging.getLogger(__name__)

APP_NAME = "director"

# --------------------------------------------------------------------------
# Image Generation
# --------------------------------------------------------------------------

async def generate_frame(
    *,
    prompt: str,
    user_id: str,
    session_service: InMemorySessionService,
    project_id: str | None = None,
    scene_id: str | None = None,
    bible_version_id: int = 0,
    is_demo_frame: bool = False,
) -> Tuple[bytes | None, str]:
    """
    Sends the prompt to the image model and returns the image bytes.

    Emits FRAME_GENERATED event for all outcomes.
    """
    image_bytes = None
    finish_reason = "UNKNOWN"
    extra_provenance = {}

    try:
        # Per user instruction, instantiate client and call client.models.generate_content
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        model_name = os.environ["GEMINI_IMAGE_MODEL"]

        # Per docs/13_director_assets.md §5
        generation_prompt = f"{prompt}, 16:9 aspect ratio, {'2K' if is_demo_frame else '1K'} resolution"
        
        # Running the sync call in an executor to avoid blocking the event loop.
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            contents=generation_prompt,
        )
        
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
            finish_reason = f"BLOCK_REASON_{response.prompt_feedback.block_reason.name}"
            extra_provenance["block_reason"] = response.prompt_feedback.block_reason.name
        
        elif response.candidates:
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason.name
            extra_provenance["finish_reason_raw"] = candidate.finish_reason.value

            if finish_reason == "STOP":
                for part in candidate.content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        image_bytes = part.inline_data.data
                        break
        
    except Exception as e:
        logger.error(f"Image generation failed: {e}", exc_info=True)
        finish_reason = "GENERATION_ERROR"
        extra_provenance["error_message"] = str(e)

    # Per docs/13_director_assets.md §8: "Every outcome emits FRAME_GENERATED"
    session = await session_service.get_session(APP_NAME, user_id)
    await session.emit_event(
        "FRAME_GENERATED",
        actor="director",
        project_id=project_id,
        scene_id=scene_id,
        bible_version_id=bible_version_id,
        extra_data={
            "prompt": prompt,
            "finish_reason": finish_reason,
            **extra_provenance
        },
    )

    return image_bytes, finish_reason


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
    assumption_notes.append(f'Moment selected: \"{action_text}\"')

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

_session_service: InMemorySessionService | None = None

def _get_session_service() -> InMemorySessionService:
    global _session_service
    if _session_service is None:
        _session_service = InMemorySessionService()
    return _session_service

async def invoke(
    *,
    payload: dict[str, Any],
    user_id: str,
    project_id: str,
    scene_id: str,
    bible_version_id: int = 0,
) -> dict[str, Any] | None:
    """
    Invoke the Director to generate a frame and store it.
    """
    prompt_data = await _construct_prompt(payload)
    prompt = prompt_data["prompt"]
    assumption_note = prompt_data["assumption_note"]

    session_service = _get_session_service()
    
    # Emit FRAME_PROMPT_CONSTRUCTED event
    session = await session_service.get_session(APP_NAME, user_id)
    await session.emit_event(
        "FRAME_PROMPT_CONSTRUCTED",
        actor="director",
        project_id=project_id,
        scene_id=scene_id,
        bible_version_id=bible_version_id,
        extra_data={
            "action_line_count": len(payload.get("action_lines", [])),
            "character_ref_count": len(payload.get("character_refs", [])),
            "constructed_prompt": prompt,
            "assumption_note": assumption_note,
        },
    )

    image_bytes, finish_reason = await generate_frame(
        prompt=prompt,
        user_id=user_id,
        session_service=session_service,
        project_id=project_id,
        scene_id=scene_id,
        bible_version_id=bible_version_id,
    )

    if image_bytes:
        asset_id = str(uuid.uuid4())
        gcs_uri = gcs_client.upload_asset(
            image_bytes=image_bytes,
            project_id=project_id,
            scene_id=scene_id,
            asset_id=asset_id,
        )
        asset_record = supabase_client.create_asset_record(
            scene_id=scene_id,
            gcs_uri=gcs_uri,
            model=os.environ["GEMINI_IMAGE_MODEL"],
            prompt=prompt,
            assumption_note=assumption_note,
            finish_reason=finish_reason,
        )
        return asset_record
    else:
        return {"error": "Image generation failed", "finish_reason": finish_reason}
