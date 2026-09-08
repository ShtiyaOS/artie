"""
Scene Rig slot definitions and Supabase persistence.

docs/03_scene_rig.md §1  — what the Rig is (resets each scene)
docs/03_scene_rig.md §2  — slot set (7 required)
docs/03_scene_rig.md §4  — exit predicate (RULE checks only; accept-first)
docs/03_scene_rig.md §6  — carry-over rules
docs/11_supabase.md §2.5 — scene_rig_slots schema
docs/11_supabase.md §2.7 — characters (roster)
docs/11_supabase.md §2.8 — locations (arena)

Carry-over rules (§6):
  - Roster (N02), Arena (N06)  → accrete silently into autocomplete
  - Genre from Bible (S09)     → persists; never re-declared in the Rig
  - N01                        → pre-fills from prior scene's position or next
                                 in sequence; freely overwritten
  - N03, N04, N05, N07         → reset fully every scene, always
"""

import json
import logging
from typing import Any

from src.supabase_client import get_client as get_supabase
from src.confluent_producer import publish_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# N04 Obstacle — locus enum
# docs/03_scene_rig.md §2 (N04 field)
# ---------------------------------------------------------------------------

OBSTACLE_LOCUS_VALUES: frozenset[str] = frozenset({
    "AGENT",        # another person or group actively opposing the want
    "SYSTEMIC",     # institution, rule, structure
    "ENVIRONMENTAL",# physical or spatial constraint
    "INTERNAL",     # protagonist's own psychology or limitation
    "TEMPORAL",     # deadline, countdown, time pressure
})

# ---------------------------------------------------------------------------
# Slot catalogue
# ---------------------------------------------------------------------------

# (slot_id, label, required)
SLOT_CATALOGUE: list[tuple[str, str, bool]] = [
    ("N01", "Narrative Position",   True),
    ("N02", "Alignment Character",  True),
    ("N03", "Active Want",          True),
    ("N04", "Obstacle",             True),
    ("N05", "Scene Frame",          True),
    ("N06", "Location",             True),
    ("N07", "Temporal Urgency",     True),
]

REQUIRED_SLOTS: list[str] = [s for s, _, req in SLOT_CATALOGUE if req]
ALL_SLOTS:      list[str] = [s for s, _, _   in SLOT_CATALOGUE]
SLOT_LABELS:    dict[str, str] = {s: label for s, label, _ in SLOT_CATALOGUE}

# Narrative Position enum — X01 through X12
POSITION_VALUES: frozenset[str] = frozenset(f"X{i:02d}" for i in range(1, 13))

# Exit predicate: all 7 required slots must be filled (§4)
EXIT_SLOTS: frozenset[str] = frozenset(REQUIRED_SLOTS)


# ---------------------------------------------------------------------------
# Supabase helpers — scene_rig_slots
# ---------------------------------------------------------------------------

def load_rig_slots(scene_id: str) -> dict[str, dict]:
    """
    Return all scene_rig_slots rows for scene_id as {slot_id: row}.
    """
    sb = get_supabase()
    rows = (
        sb.table("scene_rig_slots")
        .select("slot_id,value,is_filled,input_conf,reask_count")
        .eq("scene_id", scene_id)
        .execute()
        .data
    )
    return {r["slot_id"]: r for r in rows}


def upsert_rig_slot(
    scene_id: str,
    slot_id: str,
    value: Any,
    *,
    input_conf: str = "VALIDATED",
    project_id: str = "",
) -> None:
    """
    Upsert one slot value into scene_rig_slots (Supabase first, then Confluent).

    docs/11_supabase.md §2.5 — scene_rig_slots schema
    docs/05_orchestration.md §3.4 — dual-write: Supabase first, Confluent second
    """
    sb = get_supabase()
    sb.table("scene_rig_slots").upsert(
        {
            "scene_id":  scene_id,
            "slot_id":   slot_id,
            "value":     json.dumps(value) if not isinstance(value, str) else value,
            "is_filled": True,
            "input_conf": input_conf,
            "updated_at": "now()",
        },
        on_conflict="scene_id,slot_id",
    ).execute()

    # Confluent — provenance (SLOT_ANSWERED)
    publish_event(
        event_type="SLOT_ANSWERED",
        actor="human",
        payload={
            "gate":       "SCENE_RIG",
            "slot_id":    slot_id,
            "slot_label": SLOT_LABELS.get(slot_id, slot_id),
            "input_conf": input_conf,
        },
        project_id=project_id,
    )
    logger.info("Rig slot %s upserted for scene %s", slot_id, scene_id)


def unfilled_required_slots(slots: dict[str, dict]) -> list[str]:
    """Return required slot IDs that are not yet filled."""
    return [s for s in REQUIRED_SLOTS if not slots.get(s, {}).get("is_filled")]


def exit_predicate_met(slots: dict[str, dict]) -> bool:
    """True when all 7 required slots are filled (docs/03_scene_rig.md §4)."""
    return all(slots.get(s, {}).get("is_filled") for s in REQUIRED_SLOTS)


# ---------------------------------------------------------------------------
# Carry-over rules — docs/03_scene_rig.md §6
# ---------------------------------------------------------------------------

def compute_prefills(scene_id: str, project_id: str) -> dict[str, Any]:
    """
    Compute pre-fill values for N01 at Scene Rig open time.

    N01 pre-fills from the prior scene's position or the next in sequence.
    N03, N04, N05, N07 reset fully — never pre-filled.
    N02, N06 accrete — no pre-fill needed; roster/arena autocomplete is separate.

    Returns a dict of {slot_id: value} for slots that should be pre-filled.
    Only N01 is included when a prior value is available.
    """
    sb = get_supabase()

    # Find the current scene's sequence_order and any prior scene.
    try:
        scene_row = (
            sb.table("scenes")
            .select("sequence_order")
            .eq("scene_id", scene_id)
            .single()
            .execute()
        )
        if not scene_row.data:
            return {}

        seq_order = scene_row.data["sequence_order"]

        # Find the immediately preceding scene in this project.
        prior_rows = (
            sb.table("scenes")
            .select("scene_id,position_id")
            .eq("project_id", project_id)
            .lt("sequence_order", seq_order)
            .order("sequence_order", desc=True)
            .limit(1)
            .execute()
        )
        prefills: dict[str, Any] = {}
        if prior_rows.data:
            prior = prior_rows.data[0]
            prior_pos = prior.get("position_id")
            if prior_pos:
                # position_id is stored as smallint; convert to X01-X12 string
                pos_str = f"X{int(prior_pos):02d}"
                if pos_str in POSITION_VALUES:
                    prefills["N01"] = pos_str
        return prefills

    except Exception:
        logger.debug("compute_prefills: could not load prior scene; returning empty")
        return {}


# ---------------------------------------------------------------------------
# Roster (characters) accretion — docs/03_scene_rig.md §2 (N02)
# ---------------------------------------------------------------------------

def resolve_or_create_character(
    project_id: str,
    name: str,
) -> str:
    """
    Resolve an existing character by name, or insert a new one.

    Returns the character_id (UUID string).
    The writer is never shown the full list unless they ask.
    """
    sb = get_supabase()
    name = name.strip()

    # Try to find existing character (case-insensitive on name).
    existing = (
        sb.table("characters")
        .select("character_id")
        .eq("project_id", project_id)
        .ilike("name", name)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]["character_id"]

    # Insert new character.
    result = (
        sb.table("characters")
        .insert({
            "project_id":  project_id,
            "name":        name,
            "role":        "SECONDARY",
            "description": "",
            "source":      "SCENE_RIG",
        })
        .execute()
    )
    return result.data[0]["character_id"]


# ---------------------------------------------------------------------------
# Arena (locations) accretion — docs/03_scene_rig.md §2 (N06)
# ---------------------------------------------------------------------------

def resolve_or_create_location(
    project_id: str,
    name: str,
) -> str:
    """
    Resolve an existing location by name, or insert a new one.

    Returns the location_id (UUID string).
    The writer is never shown the full list unless they ask.
    """
    sb = get_supabase()
    name = name.strip()

    existing = (
        sb.table("locations")
        .select("location_id")
        .eq("project_id", project_id)
        .ilike("name", name)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]["location_id"]

    result = (
        sb.table("locations")
        .insert({
            "project_id": project_id,
            "name":       name,
            "source":     "SCENE_RIG",
        })
        .execute()
    )
    return result.data[0]["location_id"]


# ---------------------------------------------------------------------------
# Genre — reads from bible_slots (persists from Greenlight; never re-declared)
# ---------------------------------------------------------------------------

def get_project_genre(project_id: str) -> str | None:
    """
    Return the genre string from the Project Bible (S09), or None if not set.

    docs/03_scene_rig.md §5 — Genre persists from the Bible; writer never
    re-declares it in the Rig.
    """
    try:
        sb = get_supabase()
        row = (
            sb.table("bible_slots")
            .select("value")
            .eq("project_id", project_id)
            .eq("slot_id", "S09")
            .single()
            .execute()
        )
        if row.data:
            val = row.data.get("value")
            if isinstance(val, str):
                # Stored as JSON string in JSONB — may be quoted
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
            return val if isinstance(val, str) else None
    except Exception:
        pass
    return None
