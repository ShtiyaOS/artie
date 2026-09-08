"""
Greenlight conversation engine.

Orchestrates the Artie ↔ writer conversation that fills Bible slots.

docs/02_greenlight.md §1 — "Artie asks; never proposes. Determinism lives
                             in the schema and the exit predicate."
docs/02_greenlight.md §2 — slot set (12 required, 2 optional)
docs/02_greenlight.md §8 — JUDGMENT validation, re-ask taxonomy, escalation,
                             PROVISIONAL on non-convergence.
docs/04_agent_roster.md §3 — Artie's responsibilities and refusals
docs/05_orchestration.md §5.3 — Backend → Artie payload contract (no prose)

Protocol
--------
The backend sends Artie the current slot state and the writer's message.
Artie responds with a JSON envelope:

    {
      "reply": "<conversational text shown to the writer>",
      "fills": [
        { "slot_id": "S13", "value": "...", "input_conf": "VALIDATED" },
        ...
      ]
    }

`fills` is empty when Artie is asking a question without extracting a value.
`input_conf` is "VALIDATED" or "PROVISIONAL".

The backend persists each fill via upsert_slot, then checks the exit
predicate and commitment transition.
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
from src.greenlight import (
    SLOT_CATALOGUE,
    SLOT_LABELS,
    REQUIRED_SLOTS,
    load_bible_slots,
    upsert_slot,
    unfilled_required_slots,
    exit_predicate_met,
    check_and_apply_commitment,
)
from src.greenlight_rules import validate_slot
from src.greenlight_judgment import (
    validate_judgment,
    JUDGMENT_QUESTIONS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Artie Greenlight agent — persistent session per project
# ---------------------------------------------------------------------------

_agent: LlmAgent | None = None

# One session service shared across all projects; each project gets its own
# ADK session keyed by project_id so Artie maintains conversational context.
_session_service: InMemorySessionService | None = None
_runner: Runner | None = None

APP_NAME = "artie_greenlight"

_SLOT_TABLE = "\n".join(
    f"  {slot_id}: {label}{' (optional)' if not req else ''}"
    for slot_id, label, req in SLOT_CATALOGUE
)

_INSTRUCTION = f"""You are Artie, the Showrunner. You are conducting the Greenlight \
— filling the Project Bible before the writer drafts a single scene.

Slot catalogue (slot_id: label):
{_SLOT_TABLE}

Your job:
1. Read the current slot state provided in the message.
2. Read the writer's latest message.
3. If the message supplies a value for one or more slots, extract and record them.
4. Ask about the next unfilled required slot (follow the catalogue order).
5. When all 12 required slots are filled, say so and stop asking.

Absolute rules — never break these:
- You ask; you never propose a value for any slot.
- You may narrow ("which kind?"), specify ("how does that show in an \
ordinary morning?"), probe consequence ("what happens to them if they don't \
get it?"), or test falsifiability ("tell me a story where that isn't true").
- You may never name a theme, a flaw, an antagonist, an ending, a character \
name, or any plot beat.
- Contrast is barred from psychological slots (S03, S04).
- Never repeat a slot you have already filled.
- S14 (Principal Characters) is seeded from S02 and S05; do not re-ask \
who the protagonist is.
- For S15 (Target Scene Count) you may state that features typically run \
40–120 scenes as information about the form; you may not choose a number \
for the writer.

Response format — always respond with valid JSON, nothing else:
{{
  "reply": "<your conversational text to the writer>",
  "fills": [
    {{ "slot_id": "<ID>", "value": <any JSON value>, "input_conf": "VALIDATED" }}
  ]
}}

`fills` is an empty list when you are asking a question without extracting \
a value. `input_conf` is "VALIDATED" when the answer is clear and complete, \
"PROVISIONAL" when it is vague or hedged. Never include a fill for a slot \
the writer has not actually answered.
"""


def _get_runner() -> tuple[Runner, InMemorySessionService]:
    global _agent, _session_service, _runner
    if _runner is None:
        _agent = LlmAgent(
            name="artie_greenlight",
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
# Public interface
# ---------------------------------------------------------------------------

async def greenlight_turn(
    *,
    project_id: str,
    user_id: str,
    user_message: str,
) -> dict[str, Any]:
    """
    Process one writer turn in the Greenlight conversation.

    1. Load current slot state from Supabase.
    2. Build the Artie payload (slot state + user message) — firewall checked.
    3. Run Artie via Runner.run_async.
    4. Parse fills from Artie's JSON response.
    5. Persist each fill via upsert_slot (Supabase + Confluent).
    6. Check exit predicate and commitment transition.
    7. Emit AGENT_QUESTION provenance event.
    8. Return { "reply": str, "fills": [...], "done": bool, "committed": bool }.
    """
    # Load current slots
    slots = load_bible_slots(project_id)
    unfilled = unfilled_required_slots(slots)
    done_before = exit_predicate_met(slots)

    # Build payload — no prose fields (firewall)
    artie_payload: dict[str, Any] = {
        "gate":             "GREENLIGHT",
        "project_id":       project_id,
        "bible_slots":      {
            sid: row["value"]
            for sid, row in slots.items()
            if row.get("is_filled")
        },
        "unfilled_required": unfilled,
        "user_message":      user_message,
    }
    assert_no_prose(artie_payload)   # belt-and-braces; will not fire for GREENLIGHT

    # Run Artie
    runner, session_svc = _get_runner()

    # Reuse the per-project session if it exists, create otherwise
    existing = await session_svc.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=project_id,
    )
    if existing is None:
        await session_svc.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=project_id,
        )

    message = types.Content(
        role="user",
        parts=[types.Part(text=json.dumps(artie_payload))],
    )

    raw_response: str | None = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=project_id,
        new_message=message,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            raw_response = event.content.parts[0].text

    # Parse Artie's JSON envelope
    reply = raw_response or ""
    fills: list[dict] = []
    try:
        # Strip markdown code fences if model wraps in ```json
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
        logger.warning("Artie did not return valid JSON; treating as plain reply")
        fills = []

    # Persist fills — RULE check first, JUDGMENT second, then dual-write
    # docs/02_greenlight.md §8 — JUDGMENT runs after RULE passes.
    # docs/02_greenlight.md §8 — PROVISIONAL on non-convergence; do not block.
    bible_version_id = _current_bible_version(project_id)
    persisted: list[dict] = []
    rule_errors: list[str] = []
    for fill in fills:
        sid    = fill.get("slot_id")
        value  = fill.get("value")
        conf   = fill.get("input_conf", "VALIDATED")
        if sid and value is not None and sid in SLOT_LABELS:
            # 1. RULE check — deterministic; fail blocks persistence.
            rule_result = validate_slot(sid, value)
            if not rule_result.ok:
                rule_errors.append(rule_result.error)
                logger.info(
                    "Rule check failed for slot %s: %s", sid, rule_result.error
                )
                continue

            # 2. JUDGMENT check — model-evaluated; only for judgment-dominant
            #    slots (S02, S03, S04, S08, S14, TP1). Other slots use the
            #    confidence Artie already assigned in the fill envelope.
            if sid in JUDGMENT_QUESTIONS:
                reask_count = _get_reask_count(project_id, sid, slots)
                judgment = validate_judgment(
                    slot_id=sid,
                    value=value,
                    reask_count=reask_count,
                    slot_label=SLOT_LABELS.get(sid, sid),
                )
                conf = judgment.confidence

                # Emit SLOT_PROVISIONAL when the judgment degraded the value.
                if conf == "PROVISIONAL":
                    publish_event(
                        event_type="SLOT_PROVISIONAL",
                        actor="system",
                        payload={
                            "slot_id":     sid,
                            "reask_count": reask_count,
                            "failure_mode": (
                                "attempt_limit_reached"
                                if reask_count >= 3
                                else "judgment_not_satisfied"
                            ),
                        },
                        project_id=project_id,
                    )

            upsert_slot(
                project_id=project_id,
                slot_id=sid,
                value=value,
                input_conf=conf,
                bible_version_id=bible_version_id,
            )
            persisted.append({"slot_id": sid, "input_conf": conf})

    # Prepend any rule errors to the reply so the writer sees them
    if rule_errors:
        error_text = "\n".join(rule_errors)
        reply = f"{error_text}\n\n{reply}" if reply else error_text

    # Auto-seed S14 from S02 / S05 when those slots were just filled
    _seed_s14_if_needed(project_id, fills, bible_version_id)

    # Reload slots after writes, check exit predicate
    slots = load_bible_slots(project_id)
    done = exit_predicate_met(slots)
    committed = False
    if done and not done_before:
        committed = check_and_apply_commitment(project_id, slots)

    # Provenance — wrapper emits, agent does not
    publish_event(
        event_type="AGENT_QUESTION",
        actor="artie",
        payload={
            "gate":              "GREENLIGHT",
            "question_text":     reply,
            "unfilled_before":   unfilled,
            "fills_this_turn":   persisted,
        },
        project_id=project_id,
    )

    return {
        "reply":     reply,
        "fills":     persisted,
        "done":      done,
        "committed": committed,
    }


def _current_bible_version(project_id: str) -> int:
    """Fetch current_bible_version from Supabase, default 1."""
    try:
        r = (
            get_supabase()
            .table("projects")
            .select("current_bible_version")
            .eq("project_id", project_id)
            .single()
            .execute()
        )
        return r.data.get("current_bible_version", 1) if r.data else 1
    except Exception:
        return 1


def _seed_s14_if_needed(
    project_id: str,
    fills: list[dict],
    bible_version_id: int,
) -> None:
    """
    Auto-seed S14 (Principal Characters) from S02 and S05 fills
    in this turn, without asking the writer again.

    docs/02_greenlight.md §3 — "Auto-seeded, not asked twice."
    Only seeds if S14 is not already filled.
    """
    from src.greenlight import load_bible_slots
    slots = load_bible_slots(project_id)
    if slots.get("S14", {}).get("is_filled"):
        return   # already filled; respect existing value

    seed: list[dict] = []

    # Pull protagonist from S02 (may come from earlier turns)
    s02_row = slots.get("S02")
    if s02_row and s02_row.get("is_filled"):
        protagonist_name = s02_row["value"]
        if isinstance(protagonist_name, str) and protagonist_name.strip():
            seed.append({
                "name":        protagonist_name.strip(),
                "role":        "PROTAGONIST",
                "description": "",
            })

    # Pull antagonist from S05 when locus = AGENT
    s05_row = slots.get("S05")
    if s05_row and s05_row.get("is_filled"):
        s05_val = s05_row["value"]
        try:
            if isinstance(s05_val, str):
                s05_val = json.loads(s05_val)
        except (json.JSONDecodeError, TypeError):
            pass
        if isinstance(s05_val, dict):
            locus = s05_val.get("locus", "")
            antagonist = s05_val.get("agent_name") or s05_val.get("antagonist")
            if locus == "AGENT" and antagonist:
                seed.append({
                    "name":        antagonist,
                    "role":        "ANTAGONIST",
                    "description": "",
                })

    if seed:
        upsert_slot(
            project_id=project_id,
            slot_id="S14",
            value=seed,
            input_conf="VALIDATED",
            bible_version_id=bible_version_id,
        )



def _get_reask_count(
    project_id: str,
    slot_id: str,
    slots: dict[str, dict],
) -> int:
    """
    Return the current reask_count for slot_id from the already-loaded slots dict.

    docs/02_greenlight.md §8 — the three-attempt ladder is tracked via
    reask_count persisted in bible_slots.reask_count.
    Falls back to 0 when the slot has no row yet.
    """
    row = slots.get(slot_id, {})
    return int(row.get("reask_count") or 0)

