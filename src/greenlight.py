"""
Greenlight slot definitions and Supabase persistence.

docs/02_greenlight.md §2  — slot set (12 required, 2 optional)
docs/02_greenlight.md §9  — exit predicate
docs/02_greenlight.md §4  — commitment state machine
docs/11_supabase.md §2.2  — bible_slots schema
docs/05_orchestration.md §3.4 — dual-write pattern (Supabase first, then Confluent)

S01 and S12 are retired. S09, S13, S15 are pure-rule. No slot validation
lives here — that is Tasks 21 and 22.
"""

import json
import logging
from typing import Any

from src.supabase_client import get_client as get_supabase
from src.confluent_producer import publish_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Slot catalogue
# ---------------------------------------------------------------------------

# Ordered list matches the interrogation order Artie uses.
# (slot_id, label, required)
SLOT_CATALOGUE: list[tuple[str, str, bool]] = [
    ("S13", "Working Title",                      True),
    ("S02", "Protagonist",                        True),
    ("S03", "Protagonist Want",                   True),
    ("S04", "Protagonist Flaw",                   True),
    ("S05", "Antagonism",                         True),
    ("S06", "Thematic Proposition",               True),
    ("S07", "Status Quo Baseline",                True),
    ("S08", "Arena",                              True),
    ("S09", "Genre",                              True),
    ("S10", "Ending Shape Hypothesis",            True),
    ("S14", "Principal Characters",               True),
    ("S15", "Target Scene Count",                 True),
    ("S11", "World Rules",                        False),   # optional
    ("TP1", "Inciting Incident",                  False),   # optional
]

REQUIRED_SLOTS: list[str] = [s for s, _, req in SLOT_CATALOGUE if req]
ALL_SLOTS:      list[str] = [s for s, _, _   in SLOT_CATALOGUE]
SLOT_LABELS:    dict[str, str] = {s: label for s, label, _ in SLOT_CATALOGUE}

# Exit predicate: all 12 required slots must be filled (§9)
EXIT_SLOTS: frozenset[str] = frozenset(REQUIRED_SLOTS)


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def load_bible_slots(project_id: str) -> dict[str, dict]:
    """
    Return all bible_slots rows for project_id as {slot_id: row}.
    """
    sb = get_supabase()
    rows = (
        sb.table("bible_slots")
        .select("slot_id,value,is_filled,input_conf,reask_count")
        .eq("project_id", project_id)
        .execute()
        .data
    )
    return {r["slot_id"]: r for r in rows}


def upsert_slot(
    project_id: str,
    slot_id: str,
    value: Any,
    *,
    input_conf: str = "VALIDATED",
    bible_version_id: int = 0,
) -> None:
    """
    Upsert one slot value into bible_slots (Supabase first, then Confluent).

    docs/11_supabase.md §2.2 — bible_slots schema
    docs/05_orchestration.md §3.4 — dual-write: Supabase first, Confluent second
    docs/02_greenlight.md §10 — versioning rule applies only to revisions;
                                 first fills do not each create a new version.
    """
    sb = get_supabase()
    sb.table("bible_slots").upsert(
        {
            "project_id": project_id,
            "slot_id":    slot_id,
            "value":      json.dumps(value) if not isinstance(value, str) else value,
            "is_filled":  True,
            "input_conf": input_conf,
            "updated_at": "now()",
        },
        on_conflict="project_id,slot_id",
    ).execute()

    # Confluent — provenance (SLOT_ANSWERED)
    publish_event(
        event_type="SLOT_ANSWERED",
        actor="human",
        payload={
            "slot_id":    slot_id,
            "slot_label": SLOT_LABELS.get(slot_id, slot_id),
            "input_conf": input_conf,
        },
        project_id=project_id,
        bible_version_id=bible_version_id,
    )
    logger.info("Slot %s upserted for project %s", slot_id, project_id)


def unfilled_required_slots(slots: dict[str, dict]) -> list[str]:
    """Return required slot IDs that are not yet filled."""
    return [s for s in REQUIRED_SLOTS if not slots.get(s, {}).get("is_filled")]


def exit_predicate_met(slots: dict[str, dict]) -> bool:
    """True when all 12 required slots are filled (docs/02_greenlight.md §9)."""
    return all(slots.get(s, {}).get("is_filled") for s in REQUIRED_SLOTS)


def check_and_apply_commitment(project_id: str, slots: dict[str, dict]) -> bool:
    """
    Check the SKEPTICAL → COMMITTED transition predicate and apply it if met.

    Transition condition (docs/02_greenlight.md §4):
        all 12 required slots is_filled = TRUE
        AND count(required slots WHERE input_conf = 'VALIDATED') >= 10

    Returns True if commitment was just applied, False otherwise.
    The transition is one-way — it never revokes commitment.
    """
    if not exit_predicate_met(slots):
        return False

    validated = sum(
        1 for s in REQUIRED_SLOTS
        if slots.get(s, {}).get("input_conf") == "VALIDATED"
    )
    if validated < 10:
        return False

    sb = get_supabase()
    result = (
        sb.table("projects")
        .select("commitment_state")
        .eq("project_id", project_id)
        .single()
        .execute()
    )
    if result.data and result.data["commitment_state"] == "SKEPTICAL":
        sb.table("projects").update(
            {"commitment_state": "COMMITTED"}
        ).eq("project_id", project_id).execute()

        publish_event(
            event_type="COMMITMENT_CHANGED",
            actor="system",
            payload={
                "from_state":          "SKEPTICAL",
                "to_state":            "COMMITTED",
                "validated_slot_count": validated,
            },
            project_id=project_id,
        )
        logger.info("Project %s transitioned to COMMITTED", project_id)
        return True

    return False
