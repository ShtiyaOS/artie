"""
Blueprint production — six actions on commitment.

docs/02_greenlight.md §6 — what the blueprint produces:
  1. Title page formatted and populated (S13, writer of record, date) as a
     Fountain title-page block.
  2. Roster seeded from S14 into the characters table, source = 'BLUEPRINT'.
  3. Arena seeded from S08 into the locations table, source = 'BLUEPRINT'.
  4. Scene 1 created in scenes with position_id=1, sequence_order=1,
     status='RIG_OPEN'.
  5. Blueprint view — the twelve slots as a readable document.
  6. Commitment announced in character (BLUEPRINT_PRODUCED event).

S14 may already contain the protagonist from S02 auto-seed.  The characters
table has a unique constraint on (project_id, name); upsert on_conflict=ignore
so re-seeding is safe.

Inserting rows through application code is allowed per standing rules.
"""

import json
import logging
from datetime import date
from typing import Any

from src.supabase_client import get_client as get_supabase
from src.confluent_producer import publish_event
from src.greenlight import load_bible_slots, SLOT_CATALOGUE, SLOT_LABELS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Title page — Fountain title-page block
# ---------------------------------------------------------------------------

def build_title_page(
    *,
    title: str,
    writer_name: str,
    written_date: str | None = None,
) -> str:
    """
    Return a Fountain title-page block.

    Fountain title-page format (fountain.io/syntax#title-page):
      Key: Value
      Key: Value
      (blank line to end the block)

    docs/02_greenlight.md §6 item 1.
    """
    today = written_date or date.today().isoformat()
    return (
        f"Title: {title}\n"
        f"Credit: Written by\n"
        f"Author: {writer_name}\n"
        f"Draft date: {today}\n"
    )


# ---------------------------------------------------------------------------
# 2. Roster seed — characters table from S14
# ---------------------------------------------------------------------------

def seed_roster(project_id: str, s14_value: Any) -> list[dict]:
    """
    Upsert principal characters from S14 into the characters table.

    Returns the list of dicts that were attempted.  The unique constraint
    on (project_id, name) means duplicate names are ignored gracefully
    via on_conflict='ignore'.

    docs/02_greenlight.md §6 item 2.
    docs/11_supabase.md §2.7 — characters schema.
    """
    characters: list[dict] = _parse_list(s14_value)
    if not characters:
        logger.info("S14 is empty; roster seed skipped for project %s", project_id)
        return []

    sb = get_supabase()
    rows = []
    for char in characters:
        name = (char.get("name") or "").strip()
        role = (char.get("role") or "PRINCIPAL").upper()
        description = (char.get("description") or "").strip()
        if not name:
            continue
        rows.append({
            "project_id":  project_id,
            "name":        name,
            "role":        role,
            "description": description or None,
            "source":      "BLUEPRINT",
        })

    if rows:
        # on_conflict='ignore' maps to ignoreDuplicates=True in supabase-py
        sb.table("characters").upsert(
            rows,
            on_conflict="project_id,name",
            ignore_duplicates=True,
        ).execute()
        logger.info(
            "Roster seeded: %d character(s) for project %s", len(rows), project_id
        )
    return rows


# ---------------------------------------------------------------------------
# 3. Arena seed — locations table from S08
# ---------------------------------------------------------------------------

def seed_arena(project_id: str, s08_value: Any) -> list[dict]:
    """
    Upsert the arena from S08 into the locations table.

    S08 is the Arena slot (docs/02_greenlight.md §2).  Its value is a
    text description or a structured dict.  We extract a name:
      - dict with 'name' key → use name
      - dict with 'setting' key → use setting
      - plain string → use the string (truncated to 200 chars)

    docs/02_greenlight.md §6 item 3.
    docs/11_supabase.md §2.8 — locations schema.
    """
    name = _arena_name(s08_value)
    if not name:
        logger.info("S08 yields no arena name; location seed skipped for project %s", project_id)
        return []

    sb = get_supabase()
    row = {
        "project_id": project_id,
        "name":       name,
        "source":     "BLUEPRINT",
    }
    sb.table("locations").upsert(
        [row],
        on_conflict="project_id,name",
        ignore_duplicates=True,
    ).execute()
    logger.info("Arena seeded: %r for project %s", name, project_id)
    return [row]


def _arena_name(value: Any) -> str:
    """Extract a location name string from S08's value."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            parsed = value
    else:
        parsed = value

    if isinstance(parsed, dict):
        name = (
            parsed.get("name")
            or parsed.get("setting")
            or parsed.get("location")
            or parsed.get("arena")
            or ""
        )
        return str(name).strip()[:200]
    if isinstance(parsed, str):
        return parsed.strip()[:200]
    return ""


# ---------------------------------------------------------------------------
# 4. Scene 1 — create opening scene row
# ---------------------------------------------------------------------------

def create_scene_one(project_id: str) -> str | None:
    """
    Insert scene 1 with position_id=1, sequence_order=1, status='RIG_OPEN'.

    Idempotent: if sequence_order=1 already exists for this project the
    existing scene_id is returned without a second insert.

    docs/02_greenlight.md §6 item 4.
    docs/11_supabase.md §2.3 — scenes schema.
    """
    sb = get_supabase()

    # Guard: return existing scene_id if scene 1 already exists.
    existing = (
        sb.table("scenes")
        .select("scene_id")
        .eq("project_id", project_id)
        .eq("sequence_order", 1)
        .execute()
        .data
    )
    if existing:
        scene_id = existing[0]["scene_id"]
        logger.info(
            "Scene 1 already exists (%s) for project %s", scene_id, project_id
        )
        return scene_id

    result = (
        sb.table("scenes")
        .insert({
            "project_id":    project_id,
            "position_id":   1,
            "sequence_order": 1,
            "status":        "RIG_OPEN",
        })
        .execute()
    )
    scene_id = result.data[0]["scene_id"] if result.data else None
    logger.info("Scene 1 created (%s) for project %s", scene_id, project_id)
    return scene_id


# ---------------------------------------------------------------------------
# 5. Blueprint view — twelve slots as readable text
# ---------------------------------------------------------------------------

def build_blueprint_view(slots: dict[str, dict]) -> str:
    """
    Return the twelve required slots as a readable document.

    docs/02_greenlight.md §6 item 5.
    """
    lines = ["# Blueprint\n"]
    for slot_id, label, required in SLOT_CATALOGUE:
        if not required:
            continue
        row = slots.get(slot_id, {})
        value = row.get("value", "—")
        conf = row.get("input_conf", "")
        conf_note = f" *(provisional)*" if conf == "PROVISIONAL" else ""
        lines.append(f"**{slot_id} — {label}**{conf_note}")
        lines.append(f"{_format_slot_value(value)}\n")
    return "\n".join(lines)


def _format_slot_value(value: Any) -> str:
    """Pretty-print a slot value for the blueprint view."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value.strip()
    else:
        parsed = value

    if isinstance(parsed, list):
        return "\n".join(
            f"  - {json.dumps(item) if not isinstance(item, str) else item}"
            for item in parsed
        )
    if isinstance(parsed, dict):
        return "\n".join(f"  {k}: {v}" for k, v in parsed.items())
    return str(parsed).strip()


# ---------------------------------------------------------------------------
# 6. Commitment announcement — BLUEPRINT_PRODUCED event
# ---------------------------------------------------------------------------

def announce_commitment(
    project_id: str,
    *,
    title: str,
    scene_id: str | None,
    character_count: int,
    location_count: int,
) -> None:
    """
    Publish the BLUEPRINT_PRODUCED provenance event.

    docs/02_greenlight.md §6 item 6.
    """
    publish_event(
        event_type="BLUEPRINT_PRODUCED",
        actor="system",
        payload={
            "title":           title,
            "scene_1_id":      scene_id,
            "character_count": character_count,
            "location_count":  location_count,
        },
        project_id=project_id,
    )
    logger.info("BLUEPRINT_PRODUCED announced for project %s", project_id)


# ---------------------------------------------------------------------------
# Orchestrator — all six steps in sequence
# ---------------------------------------------------------------------------

def produce_blueprint(
    project_id: str,
    *,
    writer_name: str = "Unknown",
    written_date: str | None = None,
) -> dict[str, Any]:
    """
    Execute all six blueprint production steps.

    Called by the conversation engine immediately after commitment is applied.
    Returns a summary dict consumed by the API layer.

    Args:
        project_id:   The project UUID.
        writer_name:  The writer's display name (from the session / auth layer).
        written_date: ISO date string; defaults to today.

    Returns a dict with keys:
        title_page     str   — Fountain title-page block
        blueprint_view str   — Twelve-slot readable document
        scene_1_id     str | None
        characters     list  — rows attempted
        locations      list  — rows attempted
    """
    slots = load_bible_slots(project_id)

    # --- 1. Title page ---
    s13 = slots.get("S13", {})
    title = s13.get("value") or "Untitled"
    if isinstance(title, str):
        try:
            title = json.loads(title)
        except (json.JSONDecodeError, TypeError):
            pass
    title = str(title).strip() or "Untitled"

    title_page = build_title_page(
        title=title,
        writer_name=writer_name,
        written_date=written_date,
    )

    # --- 2. Roster seed ---
    s14 = slots.get("S14", {})
    characters = seed_roster(project_id, s14.get("value"))

    # --- 3. Arena seed ---
    s08 = slots.get("S08", {})
    locations = seed_arena(project_id, s08.get("value"))

    # --- 4. Scene 1 ---
    scene_1_id = create_scene_one(project_id)

    # --- 5. Blueprint view ---
    blueprint_view = build_blueprint_view(slots)

    # --- 6. Announce ---
    announce_commitment(
        project_id,
        title=title,
        scene_id=scene_1_id,
        character_count=len(characters),
        location_count=len(locations),
    )

    return {
        "title_page":     title_page,
        "blueprint_view": blueprint_view,
        "scene_1_id":     scene_1_id,
        "characters":     characters,
        "locations":      locations,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_list(value: Any) -> list[dict]:
    """Parse a slot value that should be a list of dicts."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []
