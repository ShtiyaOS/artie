"""
Scene Rig asynchronous JUDGMENT validation.

docs/03_scene_rig.md §3  — JUDGMENT questions, verbatim per slot
docs/03_scene_rig.md §4  — JUDGMENT runs after the writer enters the drafting
                             surface; never a wall before it.
                             A slot failing async judgment is marked PROVISIONAL.
docs/05_orchestration.md §8 — SLOT_JUDGMENT_FAILED enters a per-project queue;
                               delivered at the next scene-completion event.

Slots with JUDGMENT questions (§3 table):
  N02 — Does this name a distinct agent capable of anchoring focalization?
  N03 — Is this a specific actionable objective rather than a passive emotional state?
  N04 — Does this describe a tangible force directly countering N03?
  N05 — (1) Does entry_state describe a condition at the scene's opening rather
             than its outcome?
         (2) Does value_at_stake state a risk rather than a result?
  N06 — Does this describe a spatial environment capable of containing the action?
  N07 — Does this articulate a trigger or deadline forcing the action to occur now
         rather than later?

Pure-rule slot with no JUDGMENT:
  N01 — no JUDGMENT question (value ∈ enum; deterministic).

Public interface
----------------
  run_rig_judgment(scene_id, project_id) -> None
    Evaluates every filled judgment-bearing slot.
    Marks PROVISIONAL in scene_rig_slots and enqueues SLOT_JUDGMENT_FAILED
    in agent_queue for any slot that fails.
    Never blocks the writer; must be called after transition to DRAFTING.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from google.genai import Client

from src.supabase_client import get_client as get_supabase
from src.confluent_producer import publish_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JUDGMENT questions — verbatim per docs/03_scene_rig.md §3
# N01 is pure-rule (value ∈ enum); no JUDGMENT question.
# ---------------------------------------------------------------------------

RIG_JUDGMENT_QUESTIONS: dict[str, str | list[str]] = {
    # N02 Alignment Character
    "N02": (
        "Does this name a distinct agent capable of anchoring focalization?"
    ),
    # N03 Active Want — judgment-dominant
    "N03": (
        "Is this a specific actionable objective rather than a passive "
        "emotional state?"
    ),
    # N04 Obstacle — referentially gated, semantically judged
    "N04": (
        "Does this describe a tangible force directly countering N03?"
    ),
    # N05 Scene Frame — two questions (docs/03_scene_rig.md §3)
    # (1) entry_state: intent not outcome
    # (2) value_at_stake: risk not result (catches execution leaking into intent)
    "N05": [
        "Does entry_state describe a condition at the scene's opening rather "
        "than its outcome?",
        "Does value_at_stake state a risk rather than a result?",
    ],
    # N06 Location — referentially gated, semantically judged
    "N06": (
        "Does this describe a spatial environment capable of containing "
        "the action?"
    ),
    # N07 Temporal Urgency — judgment-dominant
    "N07": (
        "Does this articulate a trigger or deadline forcing the action to "
        "occur now rather than later?"
    ),
}

# Slots that bear judgment questions (N01 excluded — pure rule only)
JUDGMENT_SLOT_IDS: frozenset[str] = frozenset(RIG_JUDGMENT_QUESTIONS)


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------

def _judgment_model() -> str:
    return os.environ.get("GEMINI_TEXT_MODEL", "models/gemini-3.5-flash")


def _call_judgment(slot_id: str, slot_label: str, value: Any, question: str) -> bool:
    """
    Call the model with a single JUDGMENT question.

    Returns True (satisfied) or False (failed).
    Fails open (returns True) if the model call raises.

    docs/03_scene_rig.md §4 — JUDGMENT is async; failures mark PROVISIONAL
    and enqueue; they do not block.
    """
    value_text = json.dumps(value) if not isinstance(value, str) else value

    prompt = f"""You are evaluating a Scene Rig slot for a screenplay project.

Slot: {slot_id} — {slot_label}
JUDGMENT question: {question}
Writer's answer: {value_text}

Evaluate the answer against the JUDGMENT question.
A satisfactory answer is specific, concrete, and concerns intent rather than outcome.
An unsatisfactory answer is vague, describes a result rather than a risk, or
states an outcome rather than a starting condition.

Respond with valid JSON only:
{{
  "satisfied": true | false,
  "reason": "<one sentence>"
}}
"""
    try:
        client = Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        response = client.models.generate_content(
            model=_judgment_model(),
            contents=prompt,
        )
        raw = (response.text or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()
        parsed = json.loads(raw)
        return bool(parsed.get("satisfied", False))
    except Exception as exc:
        # Fail open — do not block the writer.
        logger.warning(
            "Rig JUDGMENT call failed for slot %s: %s; treating as satisfied",
            slot_id, exc,
        )
        return True


# ---------------------------------------------------------------------------
# Per-slot judgment dispatch
# ---------------------------------------------------------------------------

def _evaluate_slot(slot_id: str, slot_label: str, value: Any) -> bool:
    """
    Evaluate all JUDGMENT questions for one slot.

    Returns True when all questions are satisfied, False when any fails.

    N05 has two questions (entry_state and value_at_stake); both must pass.
    All other slots have one question.
    """
    questions = RIG_JUDGMENT_QUESTIONS.get(slot_id)
    if questions is None:
        return True  # no JUDGMENT question — pass unconditionally

    if isinstance(questions, list):
        # N05: two questions; fail if either fails
        for q in questions:
            if not _call_judgment(slot_id, slot_label, value, q):
                return False
        return True
    else:
        return _call_judgment(slot_id, slot_label, value, questions)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _mark_provisional(scene_id: str, slot_id: str) -> None:
    """
    Update scene_rig_slots.input_conf to PROVISIONAL for a failed slot.

    docs/03_scene_rig.md §4: "A slot failing async judgment is marked PROVISIONAL,
    exactly as at the Greenlight."
    """
    try:
        sb = get_supabase()
        sb.table("scene_rig_slots").update(
            {"input_conf": "PROVISIONAL"}
        ).eq("scene_id", scene_id).eq("slot_id", slot_id).execute()
        logger.info(
            "Rig slot %s marked PROVISIONAL for scene %s", slot_id, scene_id
        )
    except Exception as exc:
        logger.warning(
            "Failed to mark slot %s PROVISIONAL for scene %s: %s",
            slot_id, scene_id, exc,
        )


def _enqueue_judgment_failed(
    project_id: str,
    scene_id: str,
    slot_id: str,
    slot_label: str,
) -> None:
    """
    Insert a SLOT_JUDGMENT_FAILED row into agent_queue.

    docs/05_orchestration.md §8 — per-project queue; delivered at the next
    scene-completion event; never interrupts a drafting writer.
    """
    try:
        sb = get_supabase()
        sb.table("agent_queue").insert(
            {
                "project_id": project_id,
                "scene_id":   scene_id,
                "item_type":  "SLOT_JUDGMENT_FAILED",
                "payload":    json.dumps({
                    "slot_id":    slot_id,
                    "slot_label": slot_label,
                    "failure_mode": "judgment_not_satisfied",
                }),
            }
        ).execute()
        logger.info(
            "SLOT_JUDGMENT_FAILED enqueued for slot %s scene %s project %s",
            slot_id, scene_id, project_id,
        )
    except Exception as exc:
        logger.warning(
            "Failed to enqueue SLOT_JUDGMENT_FAILED for slot %s: %s",
            slot_id, exc,
        )

    # Confluent provenance
    try:
        publish_event(
            event_type="SLOT_JUDGMENT_FAILED",
            actor="system",
            payload={
                "slot_id":    slot_id,
                "slot_label": slot_label,
                "failure_mode": "judgment_not_satisfied",
            },
            project_id=project_id,
            scene_id=scene_id,
        )
    except Exception as exc:
        logger.warning(
            "Failed to publish SLOT_JUDGMENT_FAILED event for slot %s: %s",
            slot_id, exc,
        )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def run_rig_judgment(scene_id: str, project_id: str) -> None:
    """
    Run asynchronous JUDGMENT validation for all filled Scene Rig slots.

    Called after the writer transitions to DRAFTING (exit predicate met).
    Never blocks the writer — this runs after the gate clears.

    For each judgment-bearing slot (N02-N07) that is filled:
      1. Evaluate the JUDGMENT question(s) against the stored value.
      2. If failed: mark PROVISIONAL in scene_rig_slots and enqueue
         SLOT_JUDGMENT_FAILED in agent_queue.

    docs/03_scene_rig.md §4
    docs/05_orchestration.md §8
    """
    from src.scene_rig import load_rig_slots, SLOT_LABELS

    slots = load_rig_slots(scene_id)

    for slot_id in sorted(JUDGMENT_SLOT_IDS):
        row = slots.get(slot_id)
        if not row or not row.get("is_filled"):
            continue

        raw_value = row.get("value")
        # Values are stored as JSON strings in Supabase JSONB
        if isinstance(raw_value, str):
            try:
                value = json.loads(raw_value)
            except (json.JSONDecodeError, TypeError):
                value = raw_value
        else:
            value = raw_value

        slot_label = SLOT_LABELS.get(slot_id, slot_id)
        satisfied = _evaluate_slot(slot_id, slot_label, value)

        if not satisfied:
            _mark_provisional(scene_id, slot_id)
            _enqueue_judgment_failed(project_id, scene_id, slot_id, slot_label)
