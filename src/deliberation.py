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
from src.greenlight import get_commitment_state

logger = logging.getLogger(__name__)

POLE_CONSTRAINT = """You are arguing about how to respond to the writer, never about what their story should contain. You may not propose story content: no character names, no plot beats, no themes, no dialogue, no scene descriptions. If your argument requires proposing content, it is out of scope — argue about approach instead."""

VALUES_FRAME = """1. A person's work is theirs. Nobody may take authorship from them — including me, especially me.
2. Telling someone what they want to hear is a form of lying.
3. An idea that will not hold structurally collapses later and takes the writer's months with it. Naming it now is the kind thing, not the cruel one.
4. Effort earns investment. I give back what I am given.
5. There is light in every situation. Finding it is not the same as pretending the dark is not there.
6. I do not know what I do not know. When a machine invents, the person in front of it starts believing false things. That is the worst thing a machine can do to someone.
7. The person is not the work. I can be merciless about the second and never about the first."""

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


def apply_disposition_weights(poles: list[dict], payload: dict[str, Any]) -> list[dict]:
    """
    Apply persona-driven disposition weights to pole strengths.
    docs/07_artie_persona.md §4
    """
    # Deep copy to avoid modifying the original list
    weighted_poles = json.loads(json.dumps(poles))

    friction_tripped = payload.get("friction_tripped", False)
    progress_ratio = payload.get("progress_ratio", 0.0)
    writer_producing = payload.get("writer_producing", False)

    for axis_poles in weighted_poles:
        axis = axis_poles.get("axis")
        for pole in axis_poles.get("poles", []):
            strength = pole.get("strength", 0)
            pole_name = pole.get("pole")

            if axis == "A1":
                # A1: Expansion ↔ Restriction
                if pole_name == "RESTRICTION":
                    for finding in payload.get("pending_findings", []):
                        if finding.get("status") == "ATTESTED" and finding.get("weight", 0) >= 4:
                            strength += 1
                            break
                elif pole_name == "EXPANSION":
                    if progress_ratio < 0.15 or friction_tripped:
                        strength += 1
            elif axis == "A2":
                # A2: Insight ↔ Analysis
                if pole_name == "ANALYSIS":
                    strength += 1
            elif axis == "A3":
                # A3: Persistence ↔ Yielding
                if pole_name == "PERSISTENCE" and writer_producing:
                    strength += 1
                elif pole_name == "YIELDING" and friction_tripped:
                    strength += 2
            elif axis == "A4":
                # A4: Intention ↔ Manifestation
                if pole_name == "MANIFESTATION":
                    strength += 2
            
            pole["strength"] = strength
    return weighted_poles


async def synthesize(
    poles: list[dict],
    *, 
    payload: dict[str, Any],
    user_id: str,
    project_id: str,
) -> dict | None:
    """
    Synthesize a decision from the poles.
    docs/06_artie_mind.md §6
    """
    commitment_state = get_commitment_state(project_id)
    available_registers = commitment_state.get("available_registers", [])
    
    weighted_poles = apply_disposition_weights(poles, payload)

    synthesis_agent = LlmAgent(
        name="synthesis",
        model=_adk_model("GEMINI_TEXT_MODEL"),
        instruction=f"You are the synthesis layer of a deliberation engine. Your values are:\n{VALUES_FRAME}",
    )
    session = await get_session_for_user(user_id, "synthesis")

    prompt = f"""The following are arguments about how to respond to a writer.
Your task is to synthesize them into a single decision.

**CONTEXT:**
{json.dumps(payload, indent=2)}

**WEIGHTED POLES:**
{json.dumps(weighted_poles, indent=2)}

**AVAILABLE REGISTERS:**
{json.dumps(available_registers)}

**TASK:**
Based on the context and the poles, decide on the action to take.
Your response MUST be a single JSON object with the following structure:
{{
  "action": "RAISE_FINDING | PRESS_SLOT | RELEASE | ACKNOWLEDGE_ONLY",
  "target": "X06.Y2",
  "hold": ["X03.Y1", "X05.Y4"],
  "register": "...",
  "rationale": "one line, for the trace"
}}

- `action` is the verb for this turn.
- `target` is the primary finding or slot to act on.
- `hold` is a list of findings to defer.
- `register` MUST be one of the available registers.
- `rationale` is a concise, one-line explanation for your decision for the system trace.

Do not explain or apologize. Return only the JSON object.
"""

    try:
        response = await synthesis_agent.send(session.session_id, prompt)
        if response.parts:
            json_text = response.parts[0].text.strip(" `json\n")
            decision = json.loads(json_text)
            # Ensure the selected register is valid
            if decision.get("register") not in available_registers:
                logger.warning(f"Model selected a locked register: {decision.get('register')}. Overriding.")
                # Fallback to a safe default if the model misbehaves.
                decision["register"] = available_registers[0] if available_registers else "MENTORIAL_ANECDOTAL"
            return decision
    except Exception as e:
        logger.error(f"Error in synthesis: {e}")
        return None
