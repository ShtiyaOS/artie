"""
Scene Rig conversation engine.

Orchestrates the Artie ↔ writer conversation that fills Scene Rig slots.

docs/03_scene_rig.md §1 — "short interrogation run before every scene, resetting each time"
docs/03_scene_rig.md §2 — slot set (7 required)
docs/03_scene_rig.md §4 — exit predicate: RULE checks only; accept-first;
                            JUDGMENT runs asynchronously after the writer
                            enters the drafting surface — never a wall before it.
                            See src/scene_rig_rules.py for the RULE implementations.
docs/03_scene_rig.md §6 — carry-over rules (N01 pre-fills; N03/N04/N05/N07 reset fully)
docs/04_agent_roster.md §3 — Artie's responsibilities and refusals
docs/05_orchestration.md §5.3 — Backend → Artie payload contract (no prose)

Protocol
--------
Same JSON envelope as the Greenlight:

    {
      "reply": "<conversational text shown to the writer>",
      "fills": [
        { "slot_id": "N03", "value": "...", "input_conf": "VALIDATED" },
        ...
      ]
    }

`fills` is empty when Artie is asking a question without extracting a value.
`input_conf` is "VALIDATED" or "PROVISIONAL".

Exit predicate (§4)
-------------------
RULE checks only:
  N01 ∈ X01–X12
  N02 resolves or instantiates (non-empty name)
  N03 non-empty
  N04.locus ∈ enum AND N04.text non-empty
  N05.entry_state non-empty AND N05.value_at_stake non-empty
  N06 resolves or instantiates (non-empty name)
  N07 non-empty

JUDGMENT runs asynchronously after the writer enters the drafting surface.
Failures surface as a nudge after the scene, never as a wall before it.
"""

import json
import logging
import os
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.agents.runner import _adk_model
from src.agents.firewall import assert_no_prose, FirewallBreach
from src.confluent_producer import publish_event
from src.supabase_client import get_client as get_supabase
from src.scene_rig import (
    SLOT_CATALOGUE,
    SLOT_LABELS,
    REQUIRED_SLOTS,
    POSITION_VALUES,
    OBSTACLE_LOCUS_VALUES,
    load_rig_slots,
    upsert_rig_slot,
    unfilled_required_slots,
    exit_predicate_met,
    compute_prefills,
    resolve_or_create_character,
    resolve_or_create_location,
    get_project_genre,
)
from src.scene_rig_rules import validate_rig_slot as _validate_rig_slot_rule

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Artie Scene Rig agent — persistent session per scene
# ---------------------------------------------------------------------------

_agent: LlmAgent | None = None
_session_service: InMemorySessionService | None = None
_runner: Runner | None = None

APP_NAME = "artie_scene_rig"

_SLOT_TABLE = "\n".join(
    f"  {slot_id}: {label}"
    for slot_id, label, _ in SLOT_CATALOGUE
)

_POSITION_LIST = ", ".join(sorted(POSITION_VALUES))
_LOCUS_LIST    = ", ".join(sorted(OBSTACLE_LOCUS_VALUES))

_INSTRUCTION = f"""You are Artie, the Showrunner. You are conducting the Scene Rig \
— filling seven slots before the writer drafts the current scene.

Slot catalogue (slot_id: label):
{_SLOT_TABLE}

Slot details:
  N01 Narrative Position — one of: {_POSITION_LIST}
  N02 Alignment Character — the name of a character (existing or new); ONE character only.
  N03 Active Want — text; the specific, actionable goal for THIS scene.
  N04 Obstacle — object with two fields:
        locus: one of {_LOCUS_LIST}
        text: the specific counter-force
  N05 Scene Frame — object with two fields:
        entry_state: the condition, relationship, or standing as the scene opens (feeds Y1)
        value_at_stake: what may be lost, gained, or irrevocably altered (feeds Y2)
  N06 Location — the name of a place (existing or new).
  N07 Temporal Urgency — text; the trigger or deadline forcing the action now.

Absolute rules — never break these:
- You ask; you never propose a value for any slot.
- You may narrow, specify, probe consequence, or test falsifiability.
- You may NEVER ask the writer to declare an outcome. entry_state is where
  the scene STARTS, not where it ends. value_at_stake is a RISK, not a result.
- Never pre-fill N03, N04, N05, or N07 from a prior scene — these reset fully.
- N01 may arrive pre-filled; ask the writer to confirm or change it.
- For N02 and N06 you never show the full roster or location list unless the
  writer explicitly asks. You accept any name — existing or new.
- One alignment character per scene (N02). One location per scene (N06).
- Never repeat a slot you have already filled.
- When all 7 slots are filled, say so and stop asking.

Response format — always respond with valid JSON, nothing else:
{{
  "reply": "<your conversational text to the writer>",
  "fills": [
    {{ "slot_id": "<ID>", "value": <any JSON value>, "input_conf": "VALIDATED" }}
  ]
}}

`fills` is an empty list when you are asking a question without extracting a value.
`input_conf` is "VALIDATED" when the answer is clear and complete, "PROVISIONAL"
when it is vague or hedged. Never include a fill for a slot the writer has not
actually answered.
"""


def _get_runner() -> tuple[Runner, InMemorySessionService]:
    global _agent, _session_service, _runner
    if _runner is None:
        _agent = LlmAgent(
            name="artie_scene_rig",
            model=_adk_model("GEMINI_TEXT_MODEL"),
            instruction=_INSTRUCTION,
        )
        _session_service = InMemorySessionService()
        _runner = Runner(
            agent=_agent,
            app_name=APP_NAME,
            session_service=_session_service,
        )
    return _runner, _session_service


# ---------------------------------------------------------------------------
# RULE checks — deterministic; no model call (docs/03_scene_rig.md §4)
# Delegates to scene_rig_rules.validate_rig_slot.
# Retained as a thin shim so callers that imported _validate_rig_slot from
# this module continue to work unchanged.
# ---------------------------------------------------------------------------

def _validate_rig_slot(slot_id: str, value: Any) -> tuple[bool, str]:
    """
    Deterministic RULE check for a Scene Rig slot.

    Returns (ok, error_message).  error_message is empty when ok is True.
    docs/03_scene_rig.md §3 (RULE column), §4 (exit predicate).

    Delegates to src.scene_rig_rules.validate_rig_slot (the canonical
    implementation introduced by Task 26).
    """
    result = _validate_rig_slot_rule(slot_id, value)
    return result.ok, result.error


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def scene_rig_turn(
    *,
    scene_id: str,
    project_id: str,
    user_id: str,
    user_message: str,
) -> dict[str, Any]:
    """
    Process one writer turn in the Scene Rig conversation.

    1. Load current rig slot state from Supabase.
    2. Compute N01 pre-fill if this is the first turn.
    3. Build the Artie payload (slot state + user message) — firewall checked.
    4. Run Artie via Runner.run_async.
    5. Parse fills from Artie's JSON response.
    6. RULE-validate each fill.
    7. Persist valid fills via upsert_rig_slot (Supabase + Confluent).
    8. Accrete N02 into characters table; N06 into locations table.
    9. Check exit predicate; transition scene status when met.
    10. Emit AGENT_QUESTION provenance event.
    11. Return { "reply": str, "fills": [...], "done": bool }.
    """
    # Load current rig slots
    slots = load_rig_slots(scene_id)
    unfilled = unfilled_required_slots(slots)
    done_before = exit_predicate_met(slots)

    # Compute pre-fills on first turn (N01 only; others reset fully)
    prefills = compute_prefills(scene_id, project_id) if not slots else {}

    # Genre from Bible — shown as context; not a slot in the Rig
    genre = get_project_genre(project_id)

    # Build payload — no prose fields (firewall)
    artie_payload: dict[str, Any] = {
        "gate":             "SCENE_RIG",
        "scene_id":         scene_id,
        "project_id":       project_id,
        "rig_slots":        {
            sid: row["value"]
            for sid, row in slots.items()
            if row.get("is_filled")
        },
        "unfilled_required": unfilled,
        "prefills":          prefills,
        "user_message":      user_message,
    }
    if genre:
        artie_payload["genre"] = genre

    assert_no_prose(artie_payload)

    # Run Artie
    runner, session_svc = _get_runner()

    existing = await session_svc.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=scene_id,
    )
    if existing is None:
        await session_svc.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=scene_id,
        )

    message = types.Content(
        role="user",
        parts=[types.Part(text=json.dumps(artie_payload))],
    )

    raw_response: str | None = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=scene_id,
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            raw_response = event.content.parts[0].text

    # Parse Artie's JSON envelope
    reply = raw_response or ""
    fills: list[dict] = []
    try:
        text = (raw_response or "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        reply = parsed.get("reply", raw_response or "")
        fills = parsed.get("fills", [])
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Artie did not return valid JSON in scene_rig_turn; treating as plain reply")
        fills = []

    # Validate and persist fills
    persisted: list[dict] = []
    rule_errors: list[str] = []

    for fill in fills:
        sid   = fill.get("slot_id")
        value = fill.get("value")
        conf  = fill.get("input_conf", "VALIDATED")

        if not sid or value is None or sid not in SLOT_LABELS:
            continue

        # RULE check — deterministic; failure blocks persistence
        ok, error = _validate_rig_slot(sid, value)
        if not ok:
            rule_errors.append(error)
            logger.info("Rig rule check failed for slot %s: %s", sid, error)
            continue

        # N02 — accrete into characters table
        if sid == "N02":
            char_name = value.strip() if isinstance(value, str) else str(value).strip()
            char_id = resolve_or_create_character(project_id, char_name)
            # Store as {"name": ..., "character_id": ...} so downstream has both
            value = {"name": char_name, "character_id": char_id}

        # N06 — accrete into locations table
        elif sid == "N06":
            loc_name = value.strip() if isinstance(value, str) else str(value).strip()
            loc_id = resolve_or_create_location(project_id, loc_name)
            value = {"name": loc_name, "location_id": loc_id}

        upsert_rig_slot(
            scene_id=scene_id,
            slot_id=sid,
            value=value,
            input_conf=conf,
            project_id=project_id,
        )
        persisted.append({"slot_id": sid, "input_conf": conf})

        # N01 — update scenes.position_id when filled
        if sid == "N01":
            _update_scene_position(scene_id, value)

    # Prepend rule errors to the reply
    if rule_errors:
        error_text = "\n".join(rule_errors)
        reply = f"{error_text}\n\n{reply}" if reply else error_text

    # Reload slots after writes, check exit predicate
    slots = load_rig_slots(scene_id)
    done = exit_predicate_met(slots)

    # Transition scene status to DRAFTING when Rig clears
    if done and not done_before:
        _transition_scene_to_drafting(scene_id)

    # Provenance
    publish_event(
        event_type="AGENT_QUESTION",
        actor="artie",
        payload={
            "gate":             "SCENE_RIG",
            "question_text":    reply,
            "unfilled_before":  unfilled,
            "fills_this_turn":  persisted,
        },
        project_id=project_id,
    )

    return {
        "reply":  reply,
        "fills":  persisted,
        "done":   done,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update_scene_position(scene_id: str, n01_value: Any) -> None:
    """
    Write the numeric position to scenes.position_id from N01.

    N01 is stored as "X01"–"X12"; position_id is smallint.
    """
    try:
        if isinstance(n01_value, dict):
            pos_str = n01_value.get("value") or ""
        elif isinstance(n01_value, str):
            pos_str = n01_value
        else:
            return
        pos_str = pos_str.strip()
        if not pos_str.startswith("X"):
            return
        pos_int = int(pos_str[1:])
        sb = get_supabase()
        sb.table("scenes").update(
            {"position_id": pos_int}
        ).eq("scene_id", scene_id).execute()
    except Exception:
        logger.debug("_update_scene_position: failed to update position_id for %s", scene_id)


def _transition_scene_to_drafting(scene_id: str) -> None:
    """
    Advance scenes.status from RIG_OPEN to DRAFTING.

    docs/11_supabase.md §2.3 — scene_status enum: RIG_OPEN → DRAFTING → COMPLETE
    Only transitions if currently RIG_OPEN (idempotent).
    """
    try:
        sb = get_supabase()
        sb.table("scenes").update(
            {"status": "DRAFTING"}
        ).eq("scene_id", scene_id).eq("status", "RIG_OPEN").execute()
        logger.info("Scene %s transitioned to DRAFTING", scene_id)
    except Exception:
        logger.debug("_transition_scene_to_drafting: failed for %s", scene_id)
