"""
Artie's Deliberation Engine.

docs/06_artie_mind.md
"""

import asyncio
import json
import logging
from typing import Any, Coroutine

from google.adk.agents import LlmAgent

from src.agents.runner import _adk_model, get_session_for_user

logger = logging.getLogger(__name__)

POLE_CONSTRAINT = """You are arguing about how to respond to the writer, never about what their story should contain. You may not propose story content: no character names, no plot beats, no themes, no dialogue, no scene descriptions. If your argument requires proposing content, it is out of scope — argue about approach instead."""

AXES = {
    "A1": "EXPANSION ↔ RESTRICTION",
    "A2": "INSIGHT ↔ ANALYSIS",
    "A3": "PERSISTENCE ↔ YIELDING",
    "A4": "INTENTION ↔ MANIFESTATION",
}


def get_active_axes(payload: dict[str, Any]) -> list[str]:
    """
    Determine which deliberation axes are active based on the payload.

    docs/06_artie_mind.md §3 & §4
    """
    active = []
    
    # A1: EXPANSION ↔ RESTRICTION
    if payload.get("pending_findings"):
        active.append("A1")
        
    # A2: INSIGHT ↔ ANALYSIS
    # This trigger is more nuanced. For now, we'll assume any new slot value might trigger it.
    # A more sophisticated check might be needed in the future.
    if payload.get("gate") == "GREENLIGHT" and payload.get("slot_id"):
        active.append("A2")

    # A3: PERSISTENCE ↔ YIELDING
    # These are based on counters that we don't have yet.
    # We will leave this out for now and add it in a future task.

    # A4: INTENTION ↔ MANIFESTATION
    if any(f.get("status") == "ANCHORED" for f in payload.get("pending_findings", [])):
        if "A1" not in active: # An anchored finding implies pending findings.
            active.append("A1")
        active.append("A4")

    # Cap at two axes, strongest first.
    # Per docs/06_artie_mind.md#4, ANCHORED findings (A4) and friction counters (A3) are strongest.
    if len(active) > 2:
        if "A4" in active and "A1" in active:
            return ["A1", "A4"]
        # Fallback to the first two for now. A more sophisticated priority system may be needed.
        return active[:2]
        
    return active


async def generate_poles(
    axes: list[str],
    *, 
    payload: dict[str, Any],
    user_id: str,
) -> list[dict]:
    """
    Generate opposed poles for each active axis.

    docs/06_artie_mind.md §5
    """
    if not axes:
        return []

    tasks = [
        _generate_one_axis(axis, payload=payload, user_id=user_id) for axis in axes
    ]
    results = await asyncio.gather(*tasks)
    return [res for res in results if res]


async def _generate_one_axis(
    axis: str, 
    *, 
    payload: dict[str, Any],
    user_id: str,
) -> dict | None:
    """
    Generate the two poles for a single axis.
    """
    pole_agent = LlmAgent(
        name=f"pole_{axis}",
        model=_adk_model("GEMINI_TEXT_MODEL"),
        instruction="You are one side of an argument about how to give feedback to a writer.",
    )
    session = await get_session_for_user(user_id, f"pole_{axis}")

    prompt = f"""{POLE_CONSTRAINT}\n\nYour axis of argument is {axis}: {AXES.get(axis, "")}.\n\nThe current context is:\n{json.dumps(payload, indent=2)}\n\nGenerate the two opposing poles for this axis as a JSON object with the structure described in `docs/06_artie_mind.md`."""

    try:
        response = await pole_agent.send(session.session_id, prompt)
        if response.parts:
            # Assuming the model returns a single block of JSON.
            json_text = response.parts[0].text.strip(" `json\n")
            return json.loads(json_text)
    except Exception as e:
        logger.error(f"Error generating poles for axis {axis}: {e}")
        return None
    return None
