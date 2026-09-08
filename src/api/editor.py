"""
Editor workbench API.

Provides endpoints for:
  - Creating / retrieving takes (docs/14_editor.md §6)
  - Reading and writing script_components (docs/11_supabase.md §2.6)
  - Exporting a take as Fountain text (docs/14_editor.md §2)

All writes go to Supabase.  Component text is the writer's exclusively —
no generated text ever enters these tables through this module.
"""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from src.supabase_client import get_client as get_supabase
from src.fountain.emit import emit_fountain

router = APIRouter()


# ---------------------------------------------------------------------------
# Takes
# ---------------------------------------------------------------------------

@router.post("/scene/{scene_id}/takes")
async def create_take(scene_id: str) -> JSONResponse:
    """
    Create a new take for a scene.

    Determines the next take_number by counting existing takes.
    The new take is not submitted (submitted_at = NULL, is_final_cut = False).

    Returns: { "take_id": str, "take_number": int }
    """
    db = get_supabase()

    # Count existing takes to determine the next take_number.
    existing = (
        db.table("takes")
        .select("take_number")
        .eq("scene_id", scene_id)
        .order("take_number", desc=True)
        .limit(1)
        .execute()
    )
    next_number = (existing.data[0]["take_number"] + 1) if existing.data else 1

    result = (
        db.table("takes")
        .insert({
            "scene_id": scene_id,
            "take_number": next_number,
            "is_final_cut": False,
        })
        .execute()
    )
    row = result.data[0]
    return JSONResponse(
        {"take_id": row["take_id"], "take_number": row["take_number"]},
        status_code=201,
    )


@router.get("/scene/{scene_id}/takes")
async def list_takes(scene_id: str) -> JSONResponse:
    """
    List all takes for a scene, ordered by take_number ascending.

    Returns: [ { take_id, take_number, is_final_cut, submitted_at, created_at } ]
    """
    db = get_supabase()
    result = (
        db.table("takes")
        .select("take_id, take_number, is_final_cut, submitted_at, created_at")
        .eq("scene_id", scene_id)
        .order("take_number")
        .execute()
    )
    return JSONResponse(result.data)


@router.get("/takes/{take_id}")
async def get_take(take_id: str) -> JSONResponse:
    """
    Retrieve a single take by take_id.

    Returns 404 when the take does not exist.
    """
    db = get_supabase()
    result = (
        db.table("takes")
        .select("*")
        .eq("take_id", take_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return JSONResponse({"error": "take not found"}, status_code=404)
    return JSONResponse(result.data[0])


# ---------------------------------------------------------------------------
# Script components
# ---------------------------------------------------------------------------

VALID_COMP_TYPES = {
    "SCENE_HEADING", "ACTION", "CHARACTER", "DIALOGUE",
    "PARENTHETICAL", "TRANSITION", "NOTE",
}


@router.get("/takes/{take_id}/components")
async def list_components(take_id: str) -> JSONResponse:
    """
    List all script components for a take, ordered by sequence_order.

    Returns: [ { component_id, sequence_order, comp_type, content } ]
    """
    db = get_supabase()
    result = (
        db.table("script_components")
        .select("component_id, sequence_order, comp_type, content, updated_at")
        .eq("take_id", take_id)
        .order("sequence_order")
        .execute()
    )
    return JSONResponse(result.data)


@router.post("/takes/{take_id}/components")
async def create_component(take_id: str, request: Request) -> JSONResponse:
    """
    Create a new script component in a take.

    Body:
      {
        "comp_type":      "ACTION" | "SCENE_HEADING" | ... (required),
        "content":        "<writer text>" (required, may be empty string),
        "sequence_order": <int> (required)
      }

    Returns: { component_id, sequence_order, comp_type, content }
    """
    body: dict[str, Any] = await request.json()

    comp_type = body.get("comp_type", "").upper()
    if comp_type not in VALID_COMP_TYPES:
        return JSONResponse(
            {"error": f"invalid comp_type: {comp_type!r}"},
            status_code=400,
        )

    content = body.get("content", "")
    sequence_order = body.get("sequence_order")
    if sequence_order is None:
        return JSONResponse({"error": "sequence_order is required"}, status_code=400)

    content_hash = hashlib.sha256(content.encode()).hexdigest() if content else None

    db = get_supabase()
    result = (
        db.table("script_components")
        .insert({
            "take_id": take_id,
            "sequence_order": int(sequence_order),
            "comp_type": comp_type,
            "content": content,
            "content_hash": content_hash,
        })
        .execute()
    )
    row = result.data[0]
    return JSONResponse(
        {
            "component_id": row["component_id"],
            "sequence_order": row["sequence_order"],
            "comp_type": row["comp_type"],
            "content": row["content"],
        },
        status_code=201,
    )


@router.put("/components/{component_id}")
async def update_component(component_id: str, request: Request) -> JSONResponse:
    """
    Update the content and/or comp_type of an existing script component.

    Body (all fields optional):
      { "content": "<writer text>", "comp_type": "<type>" }

    Returns: { component_id, sequence_order, comp_type, content }
    """
    body: dict[str, Any] = await request.json()
    updates: dict[str, Any] = {}

    if "comp_type" in body:
        comp_type = body["comp_type"].upper()
        if comp_type not in VALID_COMP_TYPES:
            return JSONResponse(
                {"error": f"invalid comp_type: {comp_type!r}"},
                status_code=400,
            )
        updates["comp_type"] = comp_type

    if "content" in body:
        content = body["content"]
        updates["content"] = content
        updates["content_hash"] = (
            hashlib.sha256(content.encode()).hexdigest() if content else None
        )

    if not updates:
        return JSONResponse({"error": "no updatable fields provided"}, status_code=400)

    db = get_supabase()
    result = (
        db.table("script_components")
        .update(updates)
        .eq("component_id", component_id)
        .execute()
    )
    if not result.data:
        return JSONResponse({"error": "component not found"}, status_code=404)
    row = result.data[0]
    return JSONResponse({
        "component_id": row["component_id"],
        "sequence_order": row["sequence_order"],
        "comp_type": row["comp_type"],
        "content": row["content"],
    })


@router.delete("/components/{component_id}")
async def delete_component(component_id: str) -> JSONResponse:
    """
    Delete a script component by component_id.

    Returns 204 on success, 404 when the component does not exist.
    """
    db = get_supabase()
    result = (
        db.table("script_components")
        .delete()
        .eq("component_id", component_id)
        .execute()
    )
    if not result.data:
        return JSONResponse({"error": "component not found"}, status_code=404)
    return JSONResponse({"status": "deleted"}, status_code=200)


# ---------------------------------------------------------------------------
# Fountain export
# ---------------------------------------------------------------------------

@router.get("/takes/{take_id}/fountain")
async def export_fountain(take_id: str) -> PlainTextResponse:
    """
    Export all components of a take as a Fountain-formatted plain-text document.

    Components are sorted by sequence_order.  Forcing characters are always
    emitted (docs/14_editor.md §2).

    Returns: text/plain; charset=utf-8
    """
    db = get_supabase()
    result = (
        db.table("script_components")
        .select("comp_type, content, sequence_order")
        .eq("take_id", take_id)
        .order("sequence_order")
        .execute()
    )
    fountain_text = emit_fountain(result.data)
    return PlainTextResponse(fountain_text, media_type="text/plain; charset=utf-8")
